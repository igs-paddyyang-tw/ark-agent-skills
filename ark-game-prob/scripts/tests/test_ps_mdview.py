"""1.4 md-first View 軌：表格契約分類、三種模式（xlsx / qt / md）同一套渲染、md 模式一鍵、PS-NUM 在 md 模式降級。"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FIX = SCRIPTS / "tests" / "fixtures"
TEMPLATE = SCRIPTS.parent / "assets" / "prob-spec.template.md"
sys.path.insert(0, str(SCRIPTS))
import ps_mdview as M  # noqa: E402
import ps_html as H  # noqa: E402


def run(script, *args, cwd=None) -> dict:
    r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True, encoding="utf-8", cwd=cwd)
    assert r.stdout.strip(), r.stderr[-800:]
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def tbl(head, *rows):
    return {"kind": "table", "head": list(head), "rows": [list(r) for r in rows], "caption": None}


@pytest.mark.parametrize("head,row,expect", [
    (["指標", "值", "來源"], ["總 RTP", "96.49%", "x"], "summary"),
    (["階段", "RTP", "Hit %", "觸發率"], ["主遊戲", "70.29%", "24.58%", "—"], "base"),
    (["符號", "x2", "x3", "x4", "x5", "TOTAL"], ["11", "0%", "1.01%", "0.38%", "0.1%", "1.49%"], "symhit"),
    (["層級", "符號", "x3", "x4", "x5", "來源"], ["High", "M1", "20", "60", "250", "a"], "paytable"),
    (["符號", "sym_id", "名稱", "組", "x1", "x2", "來源"], ["WILD", "1", "w", "special", "待決議", "待決議", "—"], "odds"),
    (["組", "軸", "長度", "M1", "M2"], ["0", "R1", "160", "13", "20"], "strip_counts"),
    (["組", "R1–R5 換帶", "說明", "權重", "理論 Total RTP", "實測 Total RTP"], ["0", "0/0/0/0/0", "x", "40", "242%", "233%"], "reelset_rtp"),
    (["Index", "R1", "R2", "R3", "權重", "來源"], ["0", "0", "0", "1", "40", "a"], "reelsets"),
    (["組合", "R1 用組", "R2 用組", "權重", "來源"], ["0", "0", "1", "1", "D"], "reelsets"),
    (["贏分區間（倍）", "出現 Total", "出現 Main", "RTP Total"], ["x = 0", "59%", "60%", "0%"], "range"),
    (["贏分區間（倍）", "約每幾局", "累計門檻", "累計約每幾局"], ["0 < x < 1", "3.01", "≥ 0", "14.48"], "multiple"),
    (["100 手後剩餘資產", "佔比"], ["x <= 50", "50.24%"], "asset"),
    (["分位", "Total", "Main", "Free", "F_Spin"], ["D 1", "0.0", "0.0", "35.4", "0.0"], "decile"),
    (["組別", "F-1 權重", "理論佔比", "次數", "實際佔比", "FG RTP 貢獻"], ["超強", "1", "1%", "45,052", "1.01%", "9.24%"], "fg_groups"),
    (["項目", "值", "來源"], ["盤面", "3x5", "a"], "kv"),
    (["參數", "值"], ["bonus_reels", "5, 5, 5"], "kv"),
    (["組別", "是", "否", "來源"], ["超強", "100", "0", "a"], "yesno"),
    (["SC 倍數", "SC 權重", "SS 倍數", "SS 權重", "來源"], ["8", "18", "1288", "18", "a"], "dual"),
    (["組別", "0", "1", "2", "3", "權重和", "平均次數", "來源"], ["超強", "100", "0", "0", "0", "100", "0", "a"], "matrix"),
    (["組別", "權重", "備註", "來源"], ["超強", "1", "", "a"], "weights"),
    (["項目", "金幣", "鯉魚", "金龍", "彩龍", "Total", "來源"], ["前兩次抽取", "80", "15", "5", "0", "100", "a"], "series"),
    (["編號", "情況（topic）", "說明（值）", "設計目的", "來源"], ["—", "—", "—", "—", "x"], "generic"),
])
def test_classify(head, row, expect):
    assert M.classify(tbl(head, row)) == expect


def test_tonum_and_cells():
    assert M.tonum("1,234") == 1234 and M.tonum("12.3%") == 12.3 and M.tonum("+0.485 pp") == 0.485 and M.tonum("3 顆") == 3
    assert M.tonum("待決議") is None and M.tonum("—") is None and M.tonum("abc") is None
    assert M.split_cells("| a | b \\| c | d |") == ["a", "b | c", "d"]


def test_parse_md_sections_summary_and_strip_fence():
    md = TEMPLATE.read_text(encoding="utf-8").replace("<遊戲名>", "測試機").replace("<slug>", "demo")
    doc = M.parse_md(md)
    assert [s["id"] for s in doc["sections"] if s["no"]] == ["brief", "data", "flow", "params", "kcards", "hidden"]
    assert M.section(doc, "strips") is not None and doc["fm"]["mode"] == "md" and doc["fm"]["game"] == "測試機"
    kinds = {b["cls"] for s in doc["sections"] for b in s["blocks"] if b["kind"] == "table"}
    assert {"summary", "base", "symhit", "fg_groups", "reelsets", "dual", "yesno", "weights", "matrix", "series", "kv", "paytable", "strip_counts"} <= kinds
    f = M.strip_fences(doc)
    assert f and f[0]["name"] == "主遊戲 組 0" and len(f[0]["reels"]) == 2 and f[0]["reels"][0][4] == "WW"
    assert M.summary_of(doc).get("rtp_total", {}).get("num") is None       # 範本未快測
    assert set(M.human_blocks(doc)) == {"summary", "flow-notes", "param-notes", "competitor", "hidden-rules"}


def test_summary_fallback_from_base_info():
    md = "## 2. 數據資料\n\n| 階段 | RTP | Hit % | 觸發率 | 平均觸發局數 | 平均倍率 | 最大倍率 | 平均局數 |\n|---|---|---|---|---|---|---|---|\n| MainGame | 70.29% | 24.58% | — | — | 2.86 | 592.2 | — |\n| SpecialGameTotal | 26.19% | — | 0.12% | 805.87 | 211.08 | 20,000 | 6.67 |\n| Total | 96.49% | — | — | — | — | 20,000 | — |\n"
    s = M.summary_of(M.parse_md(md))
    assert s["rtp_total"]["num"] == 96.49 and s["rtp_main"]["num"] == 70.29 and s["fg_freq"]["num"] == 805.87 and s["fg_max"]["num"] == 20000


def test_md_mode_one_shot_and_lint_warning_only(tmp_path):
    """沒有 xlsx 也沒有快測：範本 → ps_run --md → html（旗標 / 長條 / 熱度 / 待決議 / 帶面）+ lint PASS（PS-NUM 只警告）。"""
    md = tmp_path / "demo.md"
    md.write_text(TEMPLATE.read_text(encoding="utf-8").replace("<遊戲名>", "測試機").replace("<slug>", "demo").replace("<作者>", "t").replace("<YYYY-MM-DD>", "2026-10-13"), encoding="utf-8")
    r = run("ps_run.py", "--md", md, "--dest", tmp_path / "out", cwd=tmp_path)
    assert r["success"] and r["data"]["mode"] == "md", r
    out = tmp_path / "out"
    meta = json.loads((out / "prob-spec.meta.json").read_text(encoding="utf-8"))
    assert meta["mode"] == "md" and meta["pending_params"] == 8 and meta["derived"] == []
    h = (out / "prob-spec.html").read_text(encoding="utf-8")
    assert "content-src: prob-spec.md sha256:" in h and "未快測" in h
    assert h.count('class="flag') >= 10 and h.count("cellbar") >= 8 and 'class="num heat' in h and 'class="pending"' in h
    assert 'class="sym WW"' in h and "R1 · 10 格" in h and '<span class="tid">表 M-1</span>' in h and 'class="mermaid"' in h
    lint = json.loads((out / "lint-report.json").read_text(encoding="utf-8"))
    assert lint["summary"]["errors"] == 0 and any(v["rule"] == "PS-NUM" and v["severity"] == "warning" for v in lint["violations"])


def test_qt_mode_md_has_contract_blocks_and_same_view(tmp_path):
    """qt 模式：md 帶快測摘要 / 符號命中 / 帶面，html 由同一支 ps_html 渲染出 KPI。"""
    d = tmp_path / "quicktest" / "tpl"
    (d / "odds").mkdir(parents=True); (d / "qt-report").mkdir()
    shutil.copy(FIX / "odds_1.0.0.template.json", d / "odds" / "odds_1.0.0.json")
    shutil.copy(FIX / "qt-config.template.yaml", d / "qt-config.yaml")
    shutil.copy(FIX / "quicktest.golden.yaml", d / "quicktest.yaml")
    shutil.copy(FIX / "rtp-report.golden.json", d / "qt-report" / "rtp-report.json")
    r = run("ps_run.py", "--qt", d, "--dest", tmp_path / "prob", "--slug", "tpl", cwd=tmp_path)
    assert r["success"], r
    text = (tmp_path / "prob" / "prob-spec.md").read_text(encoding="utf-8")
    assert "mode: qt" in text and "### 快測摘要" in text and "| 總 RTP | 59.4492% |" in text and "### 主遊戲符號命中率" in text
    assert "## 輪帶 Strip（附錄）" in text and "```strip" in text
    doc = M.parse_md(text)
    s = M.summary_of(doc)
    assert s["rtp_total"]["num"] == pytest.approx(59.4492) and s["target"]["num"] == 60.0 and s["tol"]["num"] == 0.5
    h = (tmp_path / "prob" / "prob-spec.html").read_text(encoding="utf-8")
    assert re.search(r'kpi-value">59\.45<small>%', h) and "目標 60.00%" in h and 'class="flag' in h and "R1 · " in h
    assert "三向 rtp" in h and 'class="sym ' in h
    lint = json.loads((tmp_path / "prob" / "lint-report.json").read_text(encoding="utf-8"))
    assert lint["summary"]["errors"] == 0, lint["violations"]


def test_xlsx_mode_md_has_contract_blocks(tmp_path):
    sys.path.insert(0, str(SCRIPTS / "tests"))
    import test_ps_pipeline as T
    xlsx = tmp_path / "測試機_機率表_v1.xlsx"
    T.make_xlsx(xlsx)
    r = run("ps_run.py", "--xlsx", xlsx, "--dest", tmp_path / "prob", "--slug", "demo", "--game", "測試機", cwd=tmp_path)
    assert r["success"], r
    text = (tmp_path / "prob" / "prob-spec.md").read_text(encoding="utf-8")
    assert "mode: xlsx" in text and "### 快測摘要" in text and "| Index | R1 |" in text
    doc = M.parse_md(text)
    kinds = {b["cls"] for sec in doc["sections"] for b in sec["blocks"] if b["kind"] == "table"}
    assert {"summary", "base", "reelsets", "weights", "kv", "paytable"} <= kinds
    h = (tmp_path / "prob" / "prob-spec.html").read_text(encoding="utf-8")
    assert "cellbar" in h and 'class="flag' in h and "golden" in h
    lint = json.loads((tmp_path / "prob" / "lint-report.json").read_text(encoding="utf-8"))
    assert lint["summary"]["errors"] == 0, lint["violations"]


def test_render_table_never_raises_on_odd_tables():
    """分類到的表格若欄位不齊，退回通用表而不是炸掉整頁。"""
    bad = {"kind": "table", "head": ["Index", "R1", "R2", "權重"], "rows": [["0", "1"]], "caption": None, "cls": "reelsets"}
    assert "<table" in H.render_table(bad, {})
    assert "<table" in H.render_table({"kind": "table", "head": ["SC 倍數", "SC 權重"], "rows": [], "caption": None, "cls": "dual"}, {})
