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
    # ISSUE-QT-001：線賠符號 M1 進 odds 表；WILD/SC（無 group、無 odds、code=W/SC）經分類判非線賠，不進 odds 表
    assert j["extra_odds"]["odds"]["11"] == [0, 0, 20, 60, 250]
    assert "1" not in j["extra_odds"]["odds"] and "4" not in j["extra_odds"]["odds"]
    assert j["main_game_reel_data"] is None
    qc = yaml.safe_load((out / "qt-config.yaml").read_text(encoding="utf-8"))
    assert qc["structure"]["wild_id"] == 1 and qc["structure"]["scatter_id"] == 4 and qc["provenance"]["extra_odds.odds.11"].startswith("gdd.symbols")
    l = run("qt_lint.py", "--dir", str(out)); assert not l["success"]
    rules = {e["rule"] for e in l["data"]["first_errors"]}
    assert "QT-NULL" in rules and "QT-ENGINE" in rules          # 5 軸、Scatter=4 → 範本不支援（F-3）


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


def _lint_rules(d):
    rep = json.loads((d / "lint-report.json").read_text(encoding="utf-8"))
    return rep, {e["rule"] for e in rep["errors"]}, {w["rule"] for w in rep["warnings"]}


def test_engine_gate_blocks_non_template_structure(tmp_path):
    d = template_dir(tmp_path)
    assert run("qt_lint.py", "--dir", str(d))["success"]                       # 範本本身 PASS（回歸基準）
    qc = yaml.safe_load((d / "qt-config.yaml").read_text(encoding="utf-8"))
    qc["structure"].update({"reels": 5, "pay_mode": "ways", "bet_cost": 88})
    (d / "qt-config.yaml").write_text(yaml.safe_dump(qc, allow_unicode=True), encoding="utf-8")
    r = run("qt_lint.py", "--dir", str(d)); assert not r["success"] and r["rc"] == 3
    rep, errs, _ = _lint_rules(d)
    eng = [e["msg"] for e in rep["errors"] if e["rule"] == "QT-ENGINE"]
    assert len(eng) == 3 and any("checkline" in m for m in eng) and any("ConstBetCost" in m for m in eng)
    qc["engine"] = {"customized": True, "note": "工程師已改 5 軸 ways"}
    (d / "qt-config.yaml").write_text(yaml.safe_dump(qc, allow_unicode=True), encoding="utf-8")
    run("qt_lint.py", "--dir", str(d))
    _, errs, warns = _lint_rules(d)
    assert "QT-ENGINE" not in errs and "QT-ENGINE" in warns                    # 宣告已改 engine → 降為警告


def test_engine_unknown_fields_warn_only(tmp_path):
    d = template_dir(tmp_path)
    qc = yaml.safe_load((d / "qt-config.yaml").read_text(encoding="utf-8"))
    for k in ("pay_mode", "lines", "bet_cost"):
        qc["structure"].pop(k, None)
    (d / "qt-config.yaml").write_text(yaml.safe_dump(qc, allow_unicode=True), encoding="utf-8")
    assert run("qt_lint.py", "--dir", str(d))["success"]
    _, _, warns = _lint_rules(d)
    assert "QT-ENGINE" in warns


def test_cap_blocks_recorder_overflow(tmp_path):
    d = template_dir(tmp_path)
    qc = yaml.safe_load((d / "qt-config.yaml").read_text(encoding="utf-8"))
    qc["structure"]["symbols"].append({"code": "GRAND", "sym_id": 105, "group": "jp"})
    qc["structure"]["symbols"].append({"code": "X31", "sym_id": 31, "group": "special"})
    (d / "qt-config.yaml").write_text(yaml.safe_dump(qc, allow_unicode=True), encoding="utf-8")
    j = json.loads((d / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8"))
    j["extra_odds"]["main_game_reel_index_set"] = [[0, 0, 0]] * 12
    j["extra_odds"]["main_game_reel_set_weight"] = [1] * 12
    j["extra_odds"]["free_game_type_weight"] = [1, 1, 1, 1, 1]
    j["extra_odds"]["free_game_reel_set_weight"] = [[1000]] * 5
    (d / "odds" / "odds_1.0.0.json").write_text(json.dumps(j), encoding="utf-8")
    run("qt_lint.py", "--dir", str(d))
    rep, errs, warns = _lint_rules(d)
    caps = [e["msg"] for e in rep["errors"] if e["rule"] == "QT-CAP"]
    assert any("105" in m for m in caps) and any("12 組合" in m for m in caps) and any("5 型" in m for m in caps)
    assert "QT-SYMID" in warns and any(w["rule"] == "QT-CAP" and "31" in w["msg"] for w in rep["warnings"])


def test_config_reads_paymode_and_betcost_from_gdd(tmp_path):
    g = _gdd(tmp_path)
    gy = yaml.safe_load((g / "gdd.yaml").read_text(encoding="utf-8"))
    gy["spec"] += [{"k": "對獎方式", "v": "50 LINES，由左至右"}, {"k": "收費", "v": "成本 {80}"}]
    (g / "gdd.yaml").write_text(yaml.safe_dump(gy, allow_unicode=True), encoding="utf-8")
    out = tmp_path / "qt"
    r = run("qt_config.py", "--out", str(out), "--gdd", str(g)); assert r["success"], r
    st = yaml.safe_load((out / "qt-config.yaml").read_text(encoding="utf-8"))["structure"]
    assert st["pay_mode"] == "line" and st["lines"] == 50 and st["bet_cost"] == 80
