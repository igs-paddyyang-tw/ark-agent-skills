"""1.1：ps_run --dest（不加 slug 層）與 ps_layout（佈局守門 / LAYOUT.md 自動產生）。"""
from __future__ import annotations

import hashlib
import json
import pathlib

import pytest
import yaml

from test_ps_pipeline import make_xlsx, run  # noqa: E402

openpyxl = pytest.importorskip("openpyxl")

MAP = """rules:
  - {id: bet_cost, xlsx: "board.基本收費", config: Bet_Cost}
  - {id: rs, xlsx: "reelsets.weight", config: MainGameReelSetWeight}
  - {id: odds_M1, xlsx: "paytable.M1", config: Odds.11, config_transform: drop_lead2}
"""


def sha16(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


@pytest.fixture()
def game(tmp_path):
    g = tmp_path / "output" / "games" / "demo"
    (g / "quicktest" / "config").mkdir(parents=True)
    (g / "quicktest" / "qt-report").mkdir()
    (g / "spec").mkdir()
    (g / "docs").mkdir()
    xlsx = tmp_path / "測試機_機率表_v1.xlsx"
    make_xlsx(xlsx)
    cfg = {"Bet_Cost": 100, "MainGameReelSetWeight": [20, 80], "Odds": {"11": [0, 0, 10, 20, 50]}}
    cp = g / "quicktest" / "config" / "a-standard.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    mp = tmp_path / "map.yaml"
    mp.write_text(MAP, encoding="utf-8")
    r = run("ps_run.py", "--xlsx", str(xlsx), "--dest", str(g / "prob"), "--slug", "demo", "--game", "測試機", "--config", str(cp), "--map", str(mp))
    assert r["success"], r
    cs = {"contract": "1", "kind": "config-spec", "mode": "restore-live", "slug": "demo",
          "sources": {"config": {"path": "../quicktest/config/a-standard.json", "sha256_16": sha16(cp)}},
          "parameters": [{"name": k, "value": {"$ref": f"../quicktest/config/a-standard.json#/{k}"}, "decision": "restore-live"} for k in cfg]}
    (g / "spec" / "config-spec.yaml").write_text(yaml.safe_dump(cs, allow_unicode=True), encoding="utf-8")
    (g / "quicktest" / "quicktest.yaml").write_text("target_rtp: 0.96\nrtp_tolerance: 0.005\n", encoding="utf-8")
    rep = {"rtp_total": 0.96, "spins": 1000, "gate": {"verdict": "confirmed", "checks": []}}
    (g / "quicktest" / "qt-report" / "rtp-report.json").write_text(json.dumps(rep), encoding="utf-8")
    return g


def test_dest_has_no_slug_layer(game):
    assert (game / "prob" / "prob-spec.md").exists() and (game / "prob" / "prob-data.json").exists()
    assert not (game / "prob" / "demo").exists()
    assert (game / "prob" / "config-diff.json").exists()


def test_layout_pass_and_md(game):
    r = run("ps_layout.py", "--game", str(game), "--write-md")
    assert r["success"], r
    assert r["data"]["verdict"] == "PASS" and r["data"]["errors"] == 0
    md = (game / "LAYOUT.md").read_text(encoding="utf-8")
    assert "勿手改" in md and "PASS" in md
    rep = json.loads((game / "layout-report.json").read_text(encoding="utf-8"))
    assert rep["facts"]["config_spec_keys"] == "3/3" and rep["facts"]["prob_source_skill"] == "ark-game-prob"


def test_layout_catches_stray_stamp_drift_rtp(game):
    (game / "data" / "prob" / "demo").mkdir(parents=True)                              # 舊佈局殘留
    (game / "docs" / "demo-prob-spec.md").write_text("# 正本\n\nA 版快測 Total RTP **99.99%** vs golden 100.03%\n", encoding="utf-8")
    (game / "docs" / "demo-prob-spec.html").write_text("<!-- content-src: prob-spec.md sha256:0123456789abcdef -->\n<p>x</p>", encoding="utf-8")
    cp = game / "quicktest" / "config" / "a-standard.json"
    cp.write_text(cp.read_text(encoding="utf-8").replace("100", "132"), encoding="utf-8")   # 設定檔改了、config-spec 沒重產
    r = run("ps_layout.py", "--game", str(game))
    assert not r["success"] and r["_rc"] == 3
    rules = {(v["rule"], v["severity"]) for v in r["data"]["violations"]}
    assert ("L-STRAY", "error") in rules and ("L-STAMP", "error") in rules and ("L-SPEC", "error") in rules
    assert ("L-RTP", "warning") in rules


def test_layout_non_skill_prob_and_missing_targets(game):
    md = game / "prob" / "prob-spec.md"
    md.write_text(md.read_text(encoding="utf-8").replace("source_skill: ark-game-prob", "source_skill: gen_probspec"), encoding="utf-8")
    (game / "quicktest" / "quicktest.yaml").unlink()
    r = run("ps_layout.py", "--game", str(game))
    msgs = " ".join(v["message"] for v in r["data"]["violations"])
    assert r["_rc"] == 3 and "不是 ark-game-prob 產物" in msgs and "缺快測目標檔" in msgs


def test_layout_accepts_flat_source_config(game):
    """1.1.1：config-spec 用扁平 `source_config`（而非巢狀 sources.config）也要被 ps_layout 接受。"""
    cp = game / "quicktest" / "config" / "a-standard.json"
    cfg = json.loads(cp.read_text(encoding="utf-8"))
    cs = {"contract": "1", "kind": "config-spec", "mode": "restore-live", "slug": "demo",
          "source_config": {"path": "../quicktest/config/a-standard.json", "sha256_16": sha16(cp)},
          "parameters": [{"name": k, "value": {"$ref": f"../quicktest/config/a-standard.json#/{k}"}, "decision": "restore-live"} for k in cfg]}
    (game / "spec" / "config-spec.yaml").write_text(yaml.safe_dump(cs, allow_unicode=True), encoding="utf-8")
    r = run("ps_layout.py", "--game", str(game))
    assert r["success"], r
    assert r["data"]["verdict"] == "PASS" and r["data"]["errors"] == 0
    rep = json.loads((game / "layout-report.json").read_text(encoding="utf-8"))
    assert rep["facts"]["config_spec_keys"] == "3/3"


def test_layout_lsize_catches_exe_and_multi_config(game):
    """1.2 G-3：二進位檔與多版本設定檔應被 L-SIZE 擋下（error）。"""
    (game / "quicktest" / "FastTest.exe").write_bytes(b"MZ" + b"\x00" * 100)        # 二進位
    (game / "quicktest" / "config" / "b-variant.json").write_text("{}", encoding="utf-8")  # 第 2 份設定檔
    r = run("ps_layout.py", "--game", str(game))
    assert not r["success"] and r["_rc"] == 3
    size_v = [v for v in r["data"]["violations"] if v["rule"] == "L-SIZE" and v["severity"] == "error"]
    msgs = " ".join(v["message"] for v in size_v)
    assert any(".exe" in v["where"] or "FastTest" in v["where"] for v in size_v)
    assert "設定檔" in msgs and "單一版本" in msgs
    rep = json.loads((game / "layout-report.json").read_text(encoding="utf-8"))
    assert rep["facts"]["size"]["exe_count"] == 1 and rep["facts"]["size"]["config_versions"] == 2


def test_layout_lserver_sha_mismatch(game):
    """1.2 G-3：server/handoff.md 宣告的 config sha 與現檔不符 → L-SERVER error。"""
    (game / "server").mkdir()
    cp = game / "quicktest" / "config" / "a-standard.json"
    good = sha16(cp)
    handoff = ("---\n"
               "kind: server-handoff\n"
               "config_sha256_16: \"deadbeefdeadbeef\"\n"           # 故意錯
               f"rtp_report_sha256_16: \"{sha16(game / 'quicktest' / 'qt-report' / 'rtp-report.json')}\"\n"
               "---\n\n# 交付單\n")
    (game / "server" / "handoff.md").write_text(handoff, encoding="utf-8")
    r = run("ps_layout.py", "--game", str(game))
    assert not r["success"] and r["_rc"] == 3
    srv_v = [v for v in r["data"]["violations"] if v["rule"] == "L-SERVER"]
    assert srv_v and "config_sha256_16" in srv_v[0]["message"]
    rep = json.loads((game / "layout-report.json").read_text(encoding="utf-8"))
    assert rep["facts"]["server"]["config_sha256_16"]["actual"] == good


def test_layout_accepts_analysis_and_valid_server(game):
    """1.2 G-3：analysis/① 與合規的 server/handoff.md（sha 相符）存在時仍 PASS。"""
    (game / "analysis").mkdir()
    (game / "analysis" / "game-analysis.md").write_text("# 競品分析\n", encoding="utf-8")
    (game / "server").mkdir()
    cp = game / "quicktest" / "config" / "a-standard.json"
    rr = game / "quicktest" / "qt-report" / "rtp-report.json"
    handoff = ("---\n"
               "kind: server-handoff\n"
               f"config_sha256_16: \"{sha16(cp)}\"\n"
               f"rtp_report_sha256_16: \"{sha16(rr)}\"\n"
               "---\n\n# 交付單\n")
    (game / "server" / "handoff.md").write_text(handoff, encoding="utf-8")
    r = run("ps_layout.py", "--game", str(game))
    assert r["success"], r
    assert r["data"]["verdict"] == "PASS" and r["data"]["errors"] == 0
    rep = json.loads((game / "layout-report.json").read_text(encoding="utf-8"))
    assert rep["facts"]["dirs"]["analysis"] is True and rep["facts"]["dirs"]["server"] is True
    assert rep["facts"]["server"]["handoff"] is True


def test_layout_review_pack(game):
    """契約 v3.3 L-REVIEW：review/ 另計 5 MB、禁影片、清冊過期 warning；review 內大 HTML 不觸發 L-SIZE 500 KB warning。"""
    rv = game / "review"
    (rv / "checks").mkdir(parents=True)
    (rv / "index.html").write_text("<html></html>", encoding="utf-8")
    (rv / "play.html").write_text("x" * 700_000, encoding="utf-8")             # 700 KB：review 內允許
    (rv / "review-manifest.json").write_text(json.dumps({"files": [{"path": "play.html", "sha256_16": "0" * 16}]}), encoding="utf-8")
    r = run("ps_layout.py", "--game", str(game))
    vs = r["data"]["violations"]
    assert not any(v["rule"] == "L-SIZE" and "review" in v["where"] for v in vs)
    assert any(v["rule"] == "L-REVIEW" and v["severity"] == "warning" and "清冊" in v["message"] for v in vs)
    assert not any(v["rule"] == "L-REVIEW" and v["severity"] == "error" for v in vs)
    (rv / "checks" / "demo.mp4").write_bytes(b"\x00" * 10)
    (rv / "big.html").write_text("x" * (5 * 1024 * 1024 + 10), encoding="utf-8")
    r = run("ps_layout.py", "--game", str(game))
    errs = [v for v in r["data"]["violations"] if v["rule"] == "L-REVIEW" and v["severity"] == "error"]
    assert r["_rc"] == 3 and any(".mp4" in v["message"] for v in errs) and any("5120" in v["message"] for v in errs)


def test_layout_v35_stage_html_stamp_and_review_links(game):
    """契約 v3.5：定版家各階段 md 旁的 html 也驗 L-STAMP；review 清冊 links（連到的定版家成品）sha 不符 → L-REVIEW warning。"""
    qr = game / "quicktest" / "qt-report"
    qr.mkdir(parents=True, exist_ok=True)
    (qr / "r.md").write_text("# 快測\n", encoding="utf-8")
    (qr / "r.html").write_text("<html></html>\n<!-- content-src: r.md sha256:0000000000000000 -->\n", encoding="utf-8")
    rv = game / "review"
    rv.mkdir(exist_ok=True)
    (rv / "index.html").write_text("<html></html>", encoding="utf-8")
    (rv / "review-manifest.json").write_text(json.dumps({"files": [], "links": [{"path": "../quicktest/qt-report/r.html", "sha256_16": "0" * 16}]}), encoding="utf-8")
    r = run("ps_layout.py", "--game", str(game))
    vs = r["data"]["violations"]
    assert any(v["rule"] == "L-STAMP" and "r.html" in v["where"] and v["severity"] == "error" for v in vs), vs
    assert any(v["rule"] == "L-REVIEW" and "../quicktest/qt-report/r.html" in v["message"] for v in vs), vs


def test_layout_data_budget_excludes_html(game):
    """契約 v3.5：定版家 1 MB 額度不計 *.html View 軌（比照單檔上限）；非 html 超過才 warning。"""
    d = game / "docs" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(3):
        (d / f"big{i}.html").write_text("x" * 400_000, encoding="utf-8")      # 1.2 MB html：不計
    r = run("ps_layout.py", "--game", str(game))
    assert not any(v["rule"] == "L-SIZE" and v["where"] == "./" for v in r["data"]["violations"])
    for i in range(3):
        (d / f"big{i}.md").write_text("x" * 400_000, encoding="utf-8")        # 1.2 MB md：計入
    r = run("ps_layout.py", "--game", str(game))
    assert any(v["rule"] == "L-SIZE" and v["where"] == "./" and v["severity"] == "warning" for v in r["data"]["violations"])



def _ref(g, sources, files):
    ref = g / "ref"
    ref.mkdir(exist_ok=True)
    (ref / "README.md").write_text("# ref\n## 來源總覽\n## 版本地圖\n## 判讀紀錄\n## 未收清單\n## 待確認\n", encoding="utf-8")
    (ref / "manifest.json").write_text(json.dumps({"slug": "demo", "contract": "3.6", "sources": sources}, ensure_ascii=False), encoding="utf-8")
    for rel, txt in files.items():
        p = ref / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")


def _src(sid, outputs, role="main", status="transcribed", sens="internal"):
    return {"id": sid, "repo": "r", "path": f"{sid}.xlsx", "sha256": "0" * 64, "kind": "prob-table",
            "role": role, "status": status, "sensitivity": sens, "outputs": outputs}


def test_layout_v36_ref_pass(game):
    _ref(game, [_src("v9a", ["ref/prob-table/v9a/"]), _src("old", [], role="history", status="skipped")],
         {"prob-table/v9a/參照表.csv": "a,b\n1,2\n"})
    rep = run("ps_layout.py", "--game", str(game))
    rules = [v["rule"] for v in rep.get("data", {}).get("violations", [])]
    assert "L-REF" not in rules, rep
    lr = json.loads((game / "layout-report.json").read_text(encoding="utf-8"))
    assert lr["facts"]["ref"]["sources"] == 2


def test_layout_v36_ref_catches_orphan_binary_enum_missing(game):
    _ref(game, [_src("v9a", ["ref/prob-table/v9a/", "ref/docs/gone.md"]), _src("bad", [], role="weird", status="skipped")],
         {"prob-table/v9a/a.csv": "x\n", "docs/orphan.md": "x\n", "raw.xlsx": "not really"})
    rep = run("ps_layout.py", "--game", str(game))
    assert not rep["success"]
    msgs = " ".join(v["message"] for v in rep["data"]["violations"] if v["rule"] == "L-REF")
    assert "gone.md" in msgs and "orphan.md" in msgs and "raw.xlsx" in msgs and "role=weird" in msgs


def test_layout_v36_ref_excluded_from_data_budget_and_review_leak(game):
    big = "x" * (600 * 1024)
    _ref(game, [_src("v9a", ["ref/prob-table/v9a/"])], {"prob-table/v9a/big.csv": big, "prob-table/v9a/big2.csv": big})
    (game / "review").mkdir()
    (game / "review" / "index.html").write_text("<html></html>", encoding="utf-8")
    (game / "review" / "review-manifest.json").write_text(json.dumps({"files": [], "links": [{"path": "../ref/live/x.json", "source": "ref/live/x.json"}]}), encoding="utf-8")
    rep = run("ps_layout.py", "--game", str(game))
    v = rep["data"]["violations"]
    assert any(x["rule"] == "L-REF" and "KB >" in x["message"] for x in v)          # ref 另計 > 1 MB → error
    assert any(x["rule"] == "L-REF" and "ref 永不進 review" in x["message"] for x in v)
    assert not any(x["rule"] == "L-SIZE" and "定版家" in x["message"] for x in v)   # ref 不吃定版家 1 MB
