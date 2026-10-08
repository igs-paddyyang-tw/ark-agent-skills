"""qt_report 守門測試：golden 報告解析、三向守門、md-report lint、deterministic。"""
from __future__ import annotations
import json, pathlib, subprocess, sys
import pytest

yaml = pytest.importorskip("yaml")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FIX = SCRIPTS / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import qt_report as Q  # noqa: E402

GOLDEN = FIX / "report_1.0.0.txt"
pytestmark = pytest.mark.skipif(not GOLDEN.exists(), reason="golden report fixture 未就位")


def run_cli(*args) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / "qt_report.py"), *args], capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def test_parse_golden():
    rep = Q.parse_report(GOLDEN.read_text(encoding="utf-8"))
    assert rep["version"] == "1.0.0" and rep["spins"] == 100_000_000 and rep["total_bet"] == 500_000_000
    assert abs(rep["rtp_total"] - 0.594492) < 1e-9 and abs(rep["rtp_main"] - 0.335498) < 1e-9
    assert rep["games"]["SpecialGameTotal"]["freq"] == 101.76 and rep["games"]["Total"]["maxmulti"] == 166.8
    assert rep["detail"]["confidence"]["95"] == [0.5938, pytest.approx(0.5952)] and rep["detail"]["pi"] == 1.7458
    assert rep["symbol_hit_rtp"]["11"]["x3"] == pytest.approx(0.051) and rep["reel_set_rtp"][0] == pytest.approx(0.594492) and rep["reel_set_rtp"][1] is None
    assert len(rep["multiple"]) == 19 and rep["multiple"][0]["spins_per_hit"] == 85.8 and rep["multiple"][9]["spins_per_hit"] is None  # +Inf → None
    assert len(rep["special_range"]) == 20 and rep["special_range"][4]["appear"]["free"] == pytest.approx(0.3914)
    assert rep["decile"]["D9"]["free"] == 48.4 and rep["decile"]["Maximum"]["total"] == 166.8
    assert abs(rep["special_trigger_rate"] - 1 / 101.76) < 1e-12


def test_gate_three_way():
    rep = Q.parse_report(GOLDEN.read_text(encoding="utf-8"))
    g = Q.gate(rep, {"target_rtp": 0.60, "feel": [{"game": "SpecialGameTotal", "preset": "標準節奏"}]}, None)
    st = {c["id"]: c["status"] for c in g["checks"]}
    assert st == {"rtp": "FAIL", "feel:SpecialGameTotal": "PASS", "null": "SKIP"} and g["verdict"] == "rejected"
    g2 = Q.gate(rep, {"target_rtp": 0.595, "feel": [{"game": "SpecialGameTotal", "band": [1 / 150, 1 / 80]}]},
                {"parameters": [{"name": "target_rtp", "value": None}]})
    assert g2["verdict"] == "confirmed"
    g3 = Q.gate(rep, {"target_rtp": 0.595}, {"parameters": [{"name": "fg_rate", "value": 0.01}]})
    assert g3["verdict"] == "rejected" and "fg_rate" in [c for c in g3["checks"] if c["id"] == "null"][0]["params"]
    assert Q.gate(rep, {}, None)["verdict"] == "inconclusive"


def test_gate_version_expect():
    """單一版本原則：versions[] 的 expect 對照 verdict（b-variant 破標 expect:fail → rejected 才算符合）。"""
    rep = Q.parse_report(GOLDEN.read_text(encoding="utf-8"))  # rtp≈0.595
    targets = {"feel": [{"game": "SpecialGameTotal", "preset": "標準節奏"}],
               "versions": [
                   {"id": "a-standard", "expect": "pass", "target_rtp": 0.595, "rtp_tolerance": 0.01},
                   {"id": "b-variant", "expect": "fail", "target_rtp": 0.595, "rtp_tolerance": 0.01},
               ]}
    cfg = {"parameters": [{"name": "x", "value": None}]}
    # a-standard：rtp 落在容許 + 三向過 → confirmed → 符合 expect:pass
    ga = Q.gate(rep, targets, cfg, version="a-standard")
    assert ga["verdict"] == "confirmed" and ga["expect_met"] is True, ga
    # b-variant：同報告但 expect:fail → confirmed 不符預期（expect_met=False）
    gb = Q.gate(rep, targets, cfg, version="b-variant")
    assert gb["expect_met"] is False, "b 版期望 fail 卻 confirmed → 不符預期"


def test_gate_itemcard_price_denominator():
    """道具卡 RTP 以售價為分母：FG 平均倍率 / 售價。"""
    rep = {"rtp_total": 0.5, "spins": 1000, "games": {"SpecialGameTotal": {"multi": 80}}}
    targets = {"versions": [{"id": "itemcard", "expect": "pass", "target_rtp": 0.8,
                             "rtp_tolerance": 0.01, "rtp_denominator": "item_price", "item_price": 100}]}
    g = Q.gate(rep, targets, {"parameters": []}, version="itemcard")
    denom = [c for c in g["checks"] if c["id"] == "rtp-denominator"]
    assert denom and "80" in denom[0]["msg"] and "100" in denom[0]["msg"], g
    # 80/100 = 0.8 → 命中 target 0.8 → rtp PASS
    rtp = [c for c in g["checks"] if c["id"] == "rtp"][0]
    assert rtp["status"] == "PASS", rtp


def test_cli_md_lint_and_deterministic(tmp_path):
    out = tmp_path / "qt"
    a = run_cli("--report", str(GOLDEN), "--targets", str(FIX / "quicktest.golden.yaml"), "--out", str(out))
    assert a["success"] and a["data"]["lint"] == "PASS" and a["data"]["verdict"] == "rejected", a
    md = pathlib.Path(a["data"]["md"]); h = md.read_bytes()
    assert md.name == "2026-07-17-quicktest-prob-base-template.md"        # 日期取報告產生時間
    txt = h.decode("utf-8")
    assert "## 驗證報告 (Verification Report)" in txt and "🔴 [FAIL]" in txt and "🟢 [PASS]" in txt and "| 11 |" in txt
    run_cli("--report", str(GOLDEN), "--targets", str(FIX / "quicktest.golden.yaml"), "--out", str(out))
    assert md.read_bytes() == h
    j = json.loads((out / "rtp-report.json").read_text(encoding="utf-8"))
    assert j["gate"]["verdict"] == "rejected" and len(j["award_range"]) == 19


def test_template_caveats_on_golden():
    rep = Q.parse_report(GOLDEN.read_text(encoding="utf-8"))
    ids = {c["finding"] for c in Q.template_caveats(rep)}
    assert ids == {"F-1", "F-5", "F-6", "F-7"}            # golden 1 億手：maxwin +Inf → 無 F-2
    rep["detail"]["maxwin_note"] = "maxwin統計: 48 手出現一次"
    assert "F-2" in {c["finding"] for c in Q.template_caveats(rep)}
    rep["games"]["Ultra"]["freq"] = 300.0                 # 分型統計正常時不誤報
    assert "F-1" not in {c["finding"] for c in Q.template_caveats(rep)}


def _restore_cfg(tmp_path, keys=("Bet_Cost", "RTP")):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "a.json").write_text(json.dumps({"Bet_Cost": 50, "RTP": 0.96}), encoding="utf-8")
    spec = tmp_path / "spec"; spec.mkdir()
    return spec, {"mode": "restore-live", "parameters": [
        {"name": k, "value": {"$ref": f"../config/a.json#/{k}"}, "decision": "restore-live: abc"} for k in keys]}


def test_gate_restore_live_ref_resolvable(tmp_path):
    rep = Q.parse_report(GOLDEN.read_text(encoding="utf-8"))
    spec, cfg = _restore_cfg(tmp_path)
    c = next(x for x in Q.gate(rep, {"target_rtp": 0.595}, cfg, config_spec_dir=spec)["checks"] if x["id"] == "null")
    assert c["status"] == "PASS" and c["mode"] == "restore-live"


def test_gate_restore_live_blocks_formal_pass(tmp_path):
    """反證（F5）：還原模式每鍵都帶 decision —— 舊規則「有 decision 就過」會形式過關；$ref 壞掉／裸值必須 FAIL。"""
    rep = Q.parse_report(GOLDEN.read_text(encoding="utf-8"))
    spec, cfg = _restore_cfg(tmp_path, keys=("Bet_Cost", "NoSuchKey"))
    cfg["parameters"].append({"name": "Desc", "value": "10 組 SC 密度分層權重", "decision": "restore-live: abc"})
    g = Q.gate(rep, {"target_rtp": 0.595}, cfg, config_spec_dir=spec)
    c = next(x for x in g["checks"] if x["id"] == "null")
    assert c["status"] == "FAIL" and c["params"] == ["Desc", "NoSuchKey"] and g["verdict"] == "rejected"
