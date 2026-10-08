"""ps_probspec(qt 模式) / ps_lint：六段齊全、數字可回溯、null → 待決議、人工區保留、STALE / 外來數字 / 無來源值被擋。"""
from __future__ import annotations
import json, pathlib, re, shutil, subprocess, sys
import pytest

yaml = pytest.importorskip("yaml")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FIX = SCRIPTS / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import ps_lint  # noqa: E402


def run(script, *args, cwd=None) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, encoding="utf-8", cwd=cwd)
    assert r.stdout.strip(), r.stderr[-800:]
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def qt_dir(tmp: pathlib.Path, with_report=True) -> pathlib.Path:
    d = tmp / "quicktest" / "tpl"; (d / "odds").mkdir(parents=True)
    shutil.copy(FIX / "odds_1.0.0.template.json", d / "odds" / "odds_1.0.0.json")
    shutil.copy(FIX / "qt-config.template.yaml", d / "qt-config.yaml")
    shutil.copy(FIX / "quicktest.golden.yaml", d / "quicktest.yaml")
    if with_report:
        (d / "qt-report").mkdir(); shutil.copy(FIX / "rtp-report.golden.json", d / "qt-report" / "rtp-report.json")
    return d


def gen(tmp, d, *extra) -> pathlib.Path:
    r = run("ps_probspec.py", "--qt", str(d), "--out", str(tmp / "prob"), "--slug", "tpl", "--date", "2026-10-01", *extra, cwd=tmp)
    assert r["success"], r
    return pathlib.Path(r["data"]["md"]) if pathlib.Path(r["data"]["md"]).is_absolute() else tmp / r["data"]["md"]


def test_sections_numbers_and_lint_pass(tmp_path):
    d = qt_dir(tmp_path)
    md = gen(tmp_path, d)
    text = md.read_text(encoding="utf-8")
    heads = [l[3:] for l in text.splitlines() if l.startswith("## ")]
    assert heads[:6] == ps_lint.SECTIONS
    assert "59.45%" in text and "rejected" in text          # 數據資料來自 rtp-report
    assert "template:odds_1.0.0.json" in text                 # provenance 欄
    rep = ps_lint.lint(md.parent)
    assert rep["summary"]["errors"] == 0, rep["violations"]
    assert (md.parent / "prob-spec.html").exists() and "content-src: prob-spec.md" in (md.parent / "prob-spec.html").read_text(encoding="utf-8")


def test_deterministic(tmp_path):
    d = qt_dir(tmp_path)
    a = gen(tmp_path, d).read_bytes()
    b = gen(tmp_path, d).read_bytes()
    assert a == b


def test_no_report_and_null_pending(tmp_path):
    d = qt_dir(tmp_path, with_report=False)
    odds = json.loads((d / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8"))
    odds["extra_odds"]["free_game_num"] = None
    (d / "odds" / "odds_1.0.0.json").write_text(json.dumps(odds), encoding="utf-8")
    md = gen(tmp_path, d)
    text = md.read_text(encoding="utf-8")
    assert "未快測" in text and "| 免費遊戲手數 | 待決議 |" in text
    assert ps_lint.lint(md.parent)["summary"]["errors"] == 0


def test_human_block_preserved(tmp_path):
    d = qt_dir(tmp_path)
    md = gen(tmp_path, d)
    t = md.read_text(encoding="utf-8")
    t = t.replace("（待機率人員填寫：特色觸發與進行方式、與競品差異、設計意圖）", "三轉軸經典機，Scatter 集 3 顆進 FG（來源：規格書 §2）。")
    md.write_text(t, encoding="utf-8")
    gen(tmp_path, d)
    t2 = md.read_text(encoding="utf-8")
    assert "三轉軸經典機" in t2
    rep = ps_lint.lint(md.parent)
    assert rep["summary"]["errors"] == 0
    assert any(v["rule"] == "PS-HUMAN" for v in rep["violations"])   # 人工區含數字 → warn


def test_lint_counterexamples(tmp_path):
    d = qt_dir(tmp_path)
    md = gen(tmp_path, d)
    # 外來數字
    t = md.read_text(encoding="utf-8")
    md.write_text(t.replace("## 6. 隱性規則", "- 免費遊戲平均 7777 倍。\n\n## 6. 隱性規則"), encoding="utf-8")
    assert any(v["rule"] == "PS-NUM" for v in ps_lint.lint(md.parent)["violations"])
    # 有值無來源
    md.write_text(t.replace("| 免費遊戲手數 | 10 手 | template:odds_1.0.0.json |", "| 免費遊戲手數 | 10 手 | — |"), encoding="utf-8")
    assert any(v["rule"] == "PS-PROV" for v in ps_lint.lint(md.parent)["violations"])
    # 來源變了 → STALE
    md.write_text(t, encoding="utf-8")
    odds = json.loads((d / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8")); odds["extra_odds"]["max_win"] = 20000
    (d / "odds" / "odds_1.0.0.json").write_text(json.dumps(odds), encoding="utf-8")
    assert any(v["rule"] == "PS-STALE" for v in ps_lint.lint(md.parent)["violations"])


def test_html_empty_shell_blocked(tmp_path):
    """PS-HTML-EMPTY：過戳記的 html 若只有佔位、未渲染六段 → 應被擋；完整 html 不誤報。"""
    d = qt_dir(tmp_path)
    md = gen(tmp_path, d)
    html_p = md.parent / "prob-spec.html"
    # 正例：ps_probspec 產出的完整 html 不應觸發 PS-HTML-EMPTY
    rep = ps_lint.lint(md.parent)
    assert not any(v["rule"] == "PS-HTML-EMPTY" for v in rep["violations"]), "完整 html 不應被判空殼"
    # 反例：過戳記但內容是空殼（只有正確 content-src 戳記 + 一句話）→ 應 PS-HTML-EMPTY error
    sha = ps_lint.C.sha16(md)
    html_p.write_text(
        f'<!DOCTYPE html><!-- content-src: prob-spec.md sha256:{sha} -->'
        '<html><body><h1>標題</h1><p>內容請見 md 檔案</p></body></html>',
        encoding="utf-8")
    viols = ps_lint.lint(md.parent)["violations"]
    empties = [v for v in viols if v["rule"] == "PS-HTML-EMPTY" and v["severity"] == "error"]
    assert empties, "空殼 html 應被 PS-HTML-EMPTY 擋（error）"


def test_probtable_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    d = qt_dir(tmp_path)
    md = gen(tmp_path, d)
    r = run("ps_probtable.py", "--dir", str(md.parent), cwd=tmp_path)
    assert r["success"], r
    x = md.parent / "prob-spec.xlsx"
    wb = openpyxl.load_workbook(x)
    assert wb.sheetnames[:5] == ["機率規格書製作方針", "規格簡述", "數據資料", "機率流程圖", "參數表"] and "_meta" in wb.sheetnames
    ws = wb["Main Game Strip"]
    formulas = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=COUNTIF(")]
    assert formulas, "輪帶總顆數需為 COUNTIF 活公式"
    assert ps_lint.lint(md.parent)["summary"]["errors"] == 0
    # md 改了 → xlsx 戳記 STALE
    md.write_text(md.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert any(v["rule"] == "PS-STALE" and "xlsx" in v["where"] for v in ps_lint.lint(md.parent)["violations"])


def test_ps_run_dest_no_slug_layer(tmp_path):
    """ps_run --dest 直接落目錄、不加 slug 層；內容 slug 仍正確（還原模式 output/games/<slug>/prob/）。"""
    qt = qt_dir(tmp_path)
    dest = tmp_path / "output" / "games" / "testgame" / "prob"
    r = run("ps_run.py", "--qt", str(qt), "--dest", str(dest), "--slug", "testgame")
    assert r["rc"] == 0, r
    assert (dest / "prob-spec.md").exists(), "產物應直接在 dest"
    assert not (dest / "testgame").exists(), "不應有多餘 slug 層"
    meta = json.loads((dest / "prob-spec.meta.json").read_text(encoding="utf-8"))
    assert meta.get("slug") == "testgame", "內容 slug 應維持真 slug，非落點名"


def test_ps_run_xlsx_view_needs_config(tmp_path):
    """xlsx 模式用 --xlsx-view 卻沒 --config → NEED_CONFIG，不靜默略過。"""
    r = run("ps_run.py", "--xlsx", str(tmp_path / "nonexist.xlsx"), "--xlsx-view")
    assert r.get("code") == "NEED_CONFIG" or "NEED_CONFIG" in str(r), r
