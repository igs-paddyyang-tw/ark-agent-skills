"""qt_config / qt_lint 守門測試：範本 odds 通過 lint；規格骨架 null 阻斷；provenance 缺失阻斷；決議填值放行。"""
from __future__ import annotations
import json, pathlib, shutil, subprocess, sys
import pytest

yaml = pytest.importorskip("yaml")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FIX = SCRIPTS / "tests" / "fixtures"


def run(script, *args) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def template_dir(tmp: pathlib.Path) -> pathlib.Path:
    d = tmp / "tpl"; (d / "odds").mkdir(parents=True)
    shutil.copy(FIX / "odds_1.0.0.template.json", d / "odds" / "odds_1.0.0.json")
    shutil.copy(FIX / "qt-config.template.yaml", d / "qt-config.yaml")
    return d


def test_lint_template_passes(tmp_path):
    d = template_dir(tmp_path)
    r = run("qt_lint.py", "--dir", str(d)); assert r["success"] and r["data"]["status"] == "PASS", r


def test_lint_blocks_unsourced_value_and_bad_symbol(tmp_path):
    d = template_dir(tmp_path)
    qc = yaml.safe_load((d / "qt-config.yaml").read_text(encoding="utf-8")); del qc["provenance"]["extra_odds.free_game_num"]
    (d / "qt-config.yaml").write_text(yaml.safe_dump(qc, allow_unicode=True), encoding="utf-8")
    j = json.loads((d / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8")); j["main_game_reel_data"][0][0][0] = 99
    (d / "odds" / "odds_1.0.0.json").write_text(json.dumps(j), encoding="utf-8")
    r = run("qt_lint.py", "--dir", str(d)); assert not r["success"] and r["rc"] == 3
    rules = {e["rule"] for e in r["data"]["first_errors"]}
    assert "QT-PROV" in rules and "QT-SYM" in rules


def _gdd(tmp: pathlib.Path) -> pathlib.Path:
    g = tmp / "gdd"; g.mkdir()
    (g / "gdd.yaml").write_text(yaml.safe_dump({"short_title": "Demo", "spec": [{"k": "盤面", "v": "3×5（主遊戲）"}]}, allow_unicode=True), encoding="utf-8")
    (g / "symbols.yaml").write_text(yaml.safe_dump({"symbols": [
        {"code": "M1", "sym_id": 11, "odds": [250, 60, 20]}, {"code": "A", "sym_id": 21, "odds": [10, 8, 5]},
        {"code": "WILD", "sym_id": 1}, {"code": "SC紅", "sym_id": 4}, {"code": "Kaiji", "sym_id": 8, "role": "performance"}]}, allow_unicode=True), encoding="utf-8")
    return g


def test_config_from_gdd_then_null_blocks(tmp_path):
    out = tmp_path / "qt"
    r = run("qt_config.py", "--out", str(out), "--gdd", str(_gdd(tmp_path))); assert r["success"], r
    d = r["data"]; assert d["reels"] == 5 and d["rows"] == 3 and d["symbols"] == 4 and d["odds_filled"] == 2
    j = json.loads((out / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8"))
    # ISSUE-QT-001：線賠符號 M1 進 odds 表；WILD(無 group、無 odds、code=W) 經 code 兜底判非線賠，不進 odds 表
    assert j["extra_odds"]["odds"]["11"] == [0, 0, 20, 60, 250]
    assert "1" not in j["extra_odds"]["odds"], "WILD 不該進 odds 表（ISSUE-QT-001）"
    assert "4" not in j["extra_odds"]["odds"], "SC 不該進 odds 表（ISSUE-QT-001）"
    assert j["main_game_reel_data"] is None
    qc = yaml.safe_load((out / "qt-config.yaml").read_text(encoding="utf-8"))
    assert qc["structure"]["wild_id"] == 1 and qc["structure"]["scatter_id"] == 4 and qc["provenance"]["extra_odds.odds.11"].startswith("gdd.symbols")
    # QT-NULL 仍擋：extra_odds 的 gates/weights 等真缺口是 null（非 WILD/SC 的假缺口）
    l = run("qt_lint.py", "--dir", str(out)); assert not l["success"]
    assert any(e["rule"] == "QT-NULL" for e in l["data"]["first_errors"])


def test_config_decisions_fill_with_provenance(tmp_path):
    out = tmp_path / "qt"
    dec = tmp_path / "decisions.yaml"
    dec.write_text(yaml.safe_dump({"decisions": [
        {"decision_id": "D007", "topic": "free_spin.count_awarded", "decision": "accept", "value": 8},
        {"decision_id": "D008", "topic": "scatter.trigger_count", "decision": "modify", "value": 3},
        {"decision_id": "D009", "topic": "reel.rows", "decision": "defer", "value": None}]}), encoding="utf-8")
    cs = tmp_path / "config-spec.yaml"
    cs.write_text(yaml.safe_dump({"parameters": [{"name": "reel.columns", "value": None, "competitor_reference": {"value": 5, "evidence": ["E001"]}},
                                                 {"name": "reel.rows", "value": None, "competitor_reference": {"value": 4, "evidence": ["E001"]}}]}), encoding="utf-8")
    r = run("qt_config.py", "--out", str(out), "--config-spec", str(cs), "--decisions", str(dec)); assert r["success"], r
    j = json.loads((out / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8"))
    qc = yaml.safe_load((out / "qt-config.yaml").read_text(encoding="utf-8"))
    assert j["extra_odds"]["free_game_num"] == 8 and j["extra_odds"]["enter_free_game_gate"] == 3
    assert qc["provenance"]["extra_odds.free_game_num"] == "D007" and qc["structure"]["reels"] == 5 and qc["structure"]["rows"] == 4
    assert qc["provenance"]["structure.rows"].startswith("competitor_reference")   # 結構可由 OBSERVED 定案（P-002）
