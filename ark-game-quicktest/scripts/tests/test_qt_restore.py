"""2.0.1：舊版 FastTest BASE INFO 直接解析（F-3）、restore-live 第③向、佈局自動探索、qt_target。"""
from __future__ import annotations
import json, pathlib, shutil, subprocess, sys
import pytest

yaml = pytest.importorskip("yaml")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FIX = SCRIPTS / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import qt_report as Q  # noqa: E402


def cli(script, *args) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def test_parse_legacy_base_info():
    rep = Q.parse_report((FIX / "report_legacy.txt").read_text(encoding="utf-8"))
    assert rep["format"] == "fasttest-legacy"
    assert rep["rtp_total"] == pytest.approx(0.999585) and rep["rtp_main"] == pytest.approx(0.390399) and rep["rtp_special"] == pytest.approx(0.609187)
    sg = rep["games"]["SpecialGameTotal"]
    assert sg["freq"] == pytest.approx(223.23) and sg["hitrate"] == pytest.approx(0.00448) and sg["maxmulti"] == pytest.approx(21049.64)
    assert "Main Fea" in rep["games"] and rep["spins"] == 99999996


def make_game(tmp: pathlib.Path) -> pathlib.Path:
    g = tmp / "games" / "demo"
    (g / "quicktest" / "engine").mkdir(parents=True)
    (g / "quicktest" / "config").mkdir()
    (g / "spec").mkdir()
    shutil.copy(FIX / "report_legacy.txt", g / "quicktest" / "engine" / "result.txt")
    cfg = {"Bet_Cost": 132, "FreeGameTypeWeight": [1, 19, 70, 10], "ReviveThreshold": 200}
    cp = g / "quicktest" / "config" / "a-standard.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    import hashlib
    s16 = hashlib.sha256(cp.read_bytes()).hexdigest()[:16]
    cs = {"contract": "1", "kind": "config-spec", "mode": "restore-live", "slug": "demo",
          "sources": {"config": {"path": "../quicktest/config/a-standard.json", "sha256_16": s16}},
          "parameters": [{"name": k, "value": {"$ref": f"../quicktest/config/a-standard.json#/{k}"}, "decision": f"restore-live: {s16}"} for k in cfg]}
    (g / "spec" / "config-spec.yaml").write_text(yaml.safe_dump(cs, allow_unicode=True), encoding="utf-8")
    return g


def gate_of(g: pathlib.Path) -> dict:
    j = cli("qt_report.py", "--report", g / "quicktest" / "engine" / "result.txt", "--out", g / "quicktest" / "qt-report")
    assert j["rc"] == 0, j
    return j["data"]


def test_target_then_discover_confirmed(tmp_path):
    g = make_game(tmp_path)
    t = cli("qt_target.py", "--out", g / "quicktest" / "quicktest.yaml", "--slug", "demo", "--target-rtp", "1.0003",
            "--feel", "SpecialGameTotal=稀有大事件", "--config", g / "quicktest" / "config" / "a-standard.json")
    assert t["rc"] == 0, t
    d = gate_of(g)
    assert d["verdict"] == "confirmed", d
    assert d["format"] == "fasttest-legacy" and sorted(d["inputs"]["discovered"]) == ["config_spec", "targets"]
    assert d["inputs"]["config_spec"].endswith("spec/config-spec.yaml")


def test_restore_sha_drift_rejected(tmp_path):
    g = make_game(tmp_path)
    cli("qt_target.py", "--out", g / "quicktest" / "quicktest.yaml", "--slug", "demo", "--target-rtp", "1.0003")
    cp = g / "quicktest" / "config" / "a-standard.json"
    cp.write_text(cp.read_text(encoding="utf-8").replace("200", "300"), encoding="utf-8")
    d = gate_of(g)
    assert d["verdict"] == "rejected"
    rep = json.loads((g / "quicktest" / "qt-report" / "rtp-report.json").read_text(encoding="utf-8"))
    null = next(c for c in rep["gate"]["checks"] if c["id"] == "null")
    assert null["status"] == "FAIL" and "sha" in null["msg"]


def test_restore_missing_key_and_raw_value(tmp_path):
    g = make_game(tmp_path)
    p = g / "spec" / "config-spec.yaml"
    cs = yaml.safe_load(p.read_text(encoding="utf-8"))
    cs["parameters"] = cs["parameters"][:-1]
    cs["parameters"][0]["value"] = 132
    p.write_text(yaml.safe_dump(cs, allow_unicode=True), encoding="utf-8")
    chk = Q.restore_check(cs, p.parent)
    assert chk["status"] == "FAIL" and "ReviveThreshold" in chk["params"] and "Bet_Cost" in chk["params"]


def test_no_discover_skips(tmp_path):
    g = make_game(tmp_path)
    j = cli("qt_report.py", "--report", g / "quicktest" / "engine" / "result.txt", "--out", tmp_path / "o", "--no-discover")
    assert j["rc"] == 0 and j["data"]["verdict"] == "inconclusive"


def test_qt_target_validation(tmp_path):
    assert cli("qt_target.py", "--out", tmp_path / "q.yaml", "--slug", "demo", "--target-rtp", "100.03")["rc"] == 2   # 百分比誤用
    assert cli("qt_target.py", "--out", tmp_path / "q.yaml", "--slug", "demo", "--target-rtp", "1.0", "--feel", "X=怪")["rc"] == 2
    j = cli("qt_target.py", "--out", tmp_path / "q.yaml", "--slug", "demo", "--target-rtp", "1.0", "--feel", "FreeGame=1/300~1/150")
    assert j["rc"] == 0 and j["data"]["feel"][0]["band"] == [round(1 / 300, 6), round(1 / 150, 6)]
    assert cli("qt_target.py", "--out", tmp_path / "q.yaml", "--slug", "demo", "--target-rtp", "1.0")["rc"] == 3     # 不覆寫
