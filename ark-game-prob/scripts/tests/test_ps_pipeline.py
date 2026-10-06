"""ark-game-prob 端到端測試：合成一本迷你公版機率表 → ps_extract → ps_probspec(xlsx) → ps_html → ps_lint → ps_diff。
不需要真實 xlsx；需要 openpyxl、pyyaml。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
openpyxl = pytest.importorskip("openpyxl")

LOG = """開MAXWIN
Workers: 2, Rounds/Worker: 500, Total: 1000
===== Done in 1.23 sec =====
====================== 版本: 1.0.0 ====================== 2026-10-06 10:00:00.0000
Times:1000  TotalWin:960  TotalBet:1000
********** BASE INFO **********
                 GAME %      Freq   Trigger %      Multi    PlayTimes  RetriRate   MaxMulti
        Main   40.0000%      2.50   40.0000%       1.00            -          -     100.00
        Free   56.0000%    200.00    0.5000%     112.00         1.00      0.00%    5000.00
       Total   96.0000%         -         -          -            -          -          -
********* Reel Set RTP **********
SET  0:     120.0000%
SET  1:      90.0000%
===== RTP 分項 =====
   主遊戲     40.0000%
   免費遊戲     56.0000%
--------------------------------
   總計     96.0000%
===== ReelSet RTP =====
  ReelSet         Spins   TotalRTP     FG_RTP
  0                 200  120.0000%   80.0000%
  1                 800   90.0000%   50.0000%
"""


def make_xlsx(p: pathlib.Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "參數表"
    ws["A2"], ws["C2"], ws["D2"] = "基本資訊", "盤面", "3x5"
    ws["C3"], ws["D3"] = "線數", "All Ways"
    ws["C4"], ws["D4"] = "基本收費", 100
    ws["A6"], ws["C6"] = "Odds表", "Pay table"
    for c, v in zip("CDEFG", ["Description", "Symbol", 3, 4, 5]):
        ws[f"{c}7"] = v
    for r, (sym, o) in enumerate([("M1", (10, 20, 50)), ("FA", (2, 4, 8))], start=8):
        ws[f"C{r}"] = "High Pay Symbols" if sym == "M1" else "Low Pay Symbols"
        ws[f"D{r}"] = sym
        ws[f"E{r}"], ws[f"F{r}"], ws[f"G{r}"] = o
    ws["A12"], ws["C12"] = "表M-1", "Main Game轉輪帶設定"
    for c, v in zip("CDEFGHIJKL", ["Index", "R1", "R2", "R3", "R4", "R5", "Weight", "組合說明", "TOTAL RTP", "FG RTP"]):
        ws[f"{c}13"] = v
    ws.append([])
    rows = [[0, 0, 0, 0, 0, 0, 20, "全 SC 帶", 1.2, 0.8], [1, 0, 0, 0, 0, 1, 80, "R5 換帶", 0.9, 0.5]]
    for i, row in enumerate(rows, start=14):
        for c, v in zip("CDEFGHIJKL", row):
            ws[f"{c}{i}"] = v
    ws["K16"], ws["L16"] = 0.96, 0.56
    ws["I18"] = 100
    ws["A20"], ws["C20"] = "表F-1", "決定強中弱組"
    ws["C22"], ws["D22"] = "組別", "權重"
    for i, (g, w) in enumerate([("超強", 1), ("強", 19), ("中", 70), ("弱", 10)], start=23):
        ws[f"C{i}"], ws[f"D{i}"] = g, w
    ws["A28"], ws["B28"] = "表F-4-1", "超過多少倍有機會觸發復活"
    ws["C29"] = "倍數"
    ws["B30"], ws["C30"] = "Weight", 300
    ws2 = wb.create_sheet("數據資料")
    for i, ln in enumerate(LOG.splitlines(), start=4):
        c = ws2.cell(i, 2, ln)
        c.data_type = "s"  # 以 '=' 開頭的報表行是文字，不是公式
    ws3 = wb.create_sheet("Main Game Strip")
    ws3["B2"] = "Ree1s_0"
    strip = ["M1", "FA", "SC", "M1", "FA"]
    for k in range(1, 6):
        ws3.cell(2, 2 + k, f"R{k}")
        for j, s in enumerate(strip, start=3):
            ws3.cell(j, 2 + k, s)
    ws3.cell(2, 9, "總顆數")
    for k in range(1, 6):
        ws3.cell(2, 9 + k, f"R{k}")
    for j, (lab, n) in enumerate([("M1", 2), ("FA", 2), ("SC", 1), ("Total", 5)], start=3):
        ws3.cell(j, 9, lab)
        for k in range(1, 6):
            ws3.cell(j, 9 + k, n)
    wb.save(p)


def run(script: str, *args: str) -> dict:
    p = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script), *args], capture_output=True, text=True, encoding="utf-8")
    line = next((ln for ln in reversed(p.stdout.strip().splitlines()) if ln.startswith("{")), "{}")
    env = json.loads(line)
    env["_rc"] = p.returncode
    env["_stderr"] = p.stderr
    return env


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    root = tmp_path_factory.mktemp("prob")
    xlsx = root / "測試機_機率表_v1.xlsx"
    make_xlsx(xlsx)
    out = root / "data" / "prob"
    e = run("ps_extract.py", "--xlsx", str(xlsx), "--out", str(out / "demo"), "--slug", "demo", "--game", "測試機")
    assert e["success"], e
    s = run("ps_probspec.py", "--data", str(out / "demo" / "prob-data.json"), "--out", str(out))
    assert s["success"], s
    h = run("ps_html.py", "--dir", str(out / "demo"))
    assert h["success"], h
    return root, out / "demo"


def test_extract_recognizers(pipeline):
    _, d = pipeline
    data = json.loads((d / "prob-data.json").read_text(encoding="utf-8"))
    K = data["known"]
    assert K["board"]["基本收費"] == 100
    assert [p["sym"] for p in K["paytable"]] == ["M1", "FA"]
    assert [s["weight"] for s in K["reelsets"]["sets"]] == [20, 80]
    assert K["reelsets"]["totals"]["TOTAL RTP"] == 0.96 and K["reelsets"]["totals"]["weight_sum"] == 100
    f1 = next(w for w in K["weights"] if w["block"] == "F-1")
    assert [i["weight"] for i in f1["items"]] == [1, 19, 70, 10]
    assert next(s for s in K["scalars"] if s["block"] == "F-4-1")["value"] == 300
    R = data["report"]
    assert R["summary"]["rtp_total"] == 96.0 and R["run"]["total"] == 1000 and R["run"]["flag"] == "開MAXWIN"
    assert [r["total"] for r in R["reel_set_rtp"]] == [120.0, 90.0]
    strips = data["strips"]["main_strip"]["Reels_0"]
    assert [len(r) for r in strips["reels"]] == [5] * 5 and strips["counts"][-1][0] == "Total"


def test_probspec_six_sections_and_lint_pass(pipeline):
    _, d = pipeline
    md = (d / "prob-spec.md").read_text(encoding="utf-8")
    heads = [ln[3:] for ln in md.splitlines() if ln.startswith("## ") and ln[3:4].isdigit()]
    assert heads == ["1. 規格簡述", "2. 數據資料", "3. 機率流程圖", "4. 參數表", "5. 競品資料／手法對應", "6. 隱性規則"]
    assert "verdict: confirmed" in md  # 96.00 vs golden 96.00
    meta = json.loads((d / "prob-spec.meta.json").read_text(encoding="utf-8"))
    assert meta["mode"] == "xlsx" and "prob-data" in meta["sources"]
    lint = run("ps_lint.py", "--dir", str(d))
    assert lint["success"], lint
    assert lint["data"]["errors"] == 0


def test_html_stamp_and_sections(pipeline):
    _, d = pipeline
    html = (d / "prob-spec.html").read_text(encoding="utf-8")
    import hashlib
    sha = hashlib.sha256((d / "prob-spec.md").read_bytes()).hexdigest()[:16]
    assert f"<!-- content-src: prob-spec.md sha256:{sha} -->" in html
    for sid in ("overview", "brief", "data", "flow", "params", "kcards", "hidden", "strips", "appendix"):
        assert f'id="{sid}"' in html
    assert "golden 96.00%" in html and "表 M-1" in html
    assert "<style>" in html and "prefers-color-scheme: dark" in html


def test_human_blocks_preserved_on_regen(pipeline):
    root, d = pipeline
    md_p = d / "prob-spec.md"
    md = md_p.read_text(encoding="utf-8")
    md = md.replace("<!-- human:summary -->\n", "<!-- human:summary -->\n我是機率人員寫的簡述。\n", 1)
    md_p.write_text(md, encoding="utf-8")
    s = run("ps_probspec.py", "--data", str(d / "prob-data.json"), "--out", str(d.parent))
    assert s["success"]
    assert "我是機率人員寫的簡述。" in md_p.read_text(encoding="utf-8")


def test_lint_catches_tampered_number(pipeline):
    root, d = pipeline
    md_p = d / "prob-spec.md"
    orig = md_p.read_text(encoding="utf-8")
    try:
        md_p.write_text(orig.replace("| 超強 | 1 |", "| 超強 | 7 |", 1), encoding="utf-8")
        lint = run("ps_lint.py", "--dir", str(d))
        assert not lint["success"] and lint["_rc"] == 3
        rules = {v["rule"] for v in lint["data"]["violations"]}
        assert "PS-NUM" in rules and "PS-STALE" in rules  # 數字無來源 + html 戳記不符
    finally:
        md_p.write_text(orig, encoding="utf-8")


def test_diff_detects_mismatch(pipeline, tmp_path):
    root, d = pipeline
    cfg = {"Bet_Cost": 100, "Bet_Line": 243, "MainGameReelSetWeight": [20, 80], "FreeGameTypeWeight": [1, 19, 70, 10], "ReviveThreshold": 200,
           "Odds": {"11": [0, 0, 10, 20, 50], "21": [0, 0, 2, 4, 8]}}
    cp = tmp_path / "cfg.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    mp = tmp_path / "map.yaml"
    mp.write_text("""rules:
  - {id: bet_cost, xlsx: "board.基本收費", config: Bet_Cost}
  - {id: bet_line, xlsx: "board.線數", config: Bet_Line, transform: ways_to_lines}
  - {id: rs, xlsx: "reelsets.weight", config: MainGameReelSetWeight}
  - {id: f1, xlsx: "weights[F-1].weight", config: FreeGameTypeWeight}
  - {id: revive, xlsx: "scalars[F-4-1]", config: ReviveThreshold}
  - {id: odds_M1, xlsx: "paytable.M1", config: Odds.11, config_transform: drop_lead2}
  - {id: missing, xlsx: "scalars[F-9]", config: Nope}
""", encoding="utf-8")
    r = run("ps_diff.py", "--data", str(d / "prob-data.json"), "--config", str(cp), "--map", str(mp))
    assert not r["success"] and r["_rc"] == 3
    rows = json.loads((d / "config-diff.json").read_text(encoding="utf-8"))["rows"]
    st = {x["rule"]: x["status"] for x in rows}
    assert st["revive"] == "mismatch" and st["bet_cost"] == "match" and st["odds_M1"] == "match" and st["missing"] == "missing-both"
    assert (d / "config-diff.md").exists()


@pytest.mark.parametrize("script", ["ps_extract.py", "ps_probspec.py", "ps_probspec_xlsx.py", "ps_html.py", "ps_lint.py", "ps_diff.py", "ps_run.py", "ps_probtable.py"])
def test_cli_help(script):
    p = subprocess.run([sys.executable, str(SCRIPTS / script), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
