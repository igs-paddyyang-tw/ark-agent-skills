"""aiqa：fake 全鏈（testgen expand → lint → run → report）、bug 注入必抓、不確定必 NEEDS_HUMAN、import 真表、lint 反證、pack lint。"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
SKILL = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import aiqa_common as C  # noqa: E402
import aiqa_oracle as O  # noqa: E402

UPLOADS = pathlib.Path("/mnt/user-data/uploads")


def sh(*args, expect=0):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "ARK_LLM_PROVIDER": "fake", "PYTHONIOENCODING": "utf-8"})
    j = json.loads(r.stdout.strip().splitlines()[-1])
    if expect is not None:
        assert r.returncode == expect, (r.returncode, j, r.stderr[-400:])
    return j


@pytest.fixture(scope="module")
def checklist(tmp_path_factory):
    d = tmp_path_factory.mktemp("cl"); cl = d / "cl.json"
    shutil.copy(SKILL / "examples" / "demo-slot.checklist.json", cl)
    j = sh(SCRIPTS / "aiqa_testgen.py", "expand", "--game", "demo-slot", "--out", cl)
    assert j["data"]["added"] >= 6
    sh(SCRIPTS / "aiqa_testgen.py", "lint", "--checklist", cl, "--game", "demo-slot")
    sh(SCRIPTS / "aiqa_testgen.py", "render", "--checklist", cl, "--out", d / "test-checklist.md")
    assert "執行提詞" in (d / "test-checklist.md").read_text(encoding="utf-8")
    return cl


def run(cl, out, *extra):
    return sh(SCRIPTS / "aiqa_run.py", "--checklist", cl, "--backend", "fake", "--out", out, *extra)["data"]


def test_pack_lint_demo_green():
    j = sh(SCRIPTS / "aiqa_pack.py", "lint", "--game", "demo-slot")
    assert j["data"]["errors"] == []


def test_fake_full_chain_all_pass(checklist, tmp_path):
    d = run(checklist, tmp_path / "runs")
    assert d["counts"]["FAIL"] == 0 and d["counts"]["BLOCK"] == 0 and d["counts"]["PASS"] >= 8, d
    rep = sh(SCRIPTS / "aiqa_report.py", "--run", d["run"])["data"]
    assert rep["false_pass"] == 0 and pathlib.Path(rep["report"]).exists() and pathlib.Path(rep["xlsx"]).exists()
    md = pathlib.Path(rep["report"]).read_text(encoding="utf-8")
    assert "誤 PASS" in md and "依公司分類樹" in md
    ev = list(pathlib.Path(d["run"]).glob("items/DEMO-MG-001/rep-1/roi-win-*.png"))
    assert ev, "PASS 必須有證據截圖"


@pytest.mark.parametrize("bugs,expect", [('{"payout_off_by": 7}', "FAIL"), ('{"multiplier_stuck": true}', "FAIL"), ('{"glitch": true}', "FAIL"), ('{"uncertain_visual": true}', "NEEDS_HUMAN")])
def test_bug_injection_caught(checklist, tmp_path, bugs, expect):
    d = run(checklist, tmp_path / "runs", "--items", "DEMO-MG-001", "--bugs", bugs)
    assert d["counts"][expect] == 1, d


def test_network_timing_item(checklist, tmp_path):
    d = run(checklist, tmp_path / "runs", "--items", "DEMO-SLOT-NETWOR-001")
    assert d["counts"]["PASS"] == 1
    d = run(checklist, tmp_path / "runs2", "--items", "DEMO-SLOT-NETWOR-001", "--bugs", '{"no_6002": true}')
    assert d["counts"]["FAIL"] == 1


def test_uncalibrated_pack_blocked(tmp_path):
    cl = tmp_path / "cl.json"; cl.write_text(json.dumps({"contract": "1", "game": "ghy", "machine": "aztec2", "items": []}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "aiqa_run.py"), "--checklist", str(cl), "--backend", "adb", "--out", str(tmp_path / "r")], capture_output=True, text=True)
    assert r.returncode == 3


@pytest.mark.skipif(not (UPLOADS / "測試項目_金猴爺20260914_v4_6_8_阿茲特克2Slot.xlsx").exists(), reason="需要上傳的測試表")
def test_import_company_xlsx(tmp_path):
    cl = tmp_path / "ghy.json"
    j = sh(SCRIPTS / "aiqa_testgen.py", "import-xlsx", "--xlsx", UPLOADS / "測試項目_金猴爺20260914_v4_6_8_阿茲特克2Slot.xlsx", "--game", "ghy", "--machine", "aztec2", "--out", cl)["data"]
    assert j["added"] == 124 and j["tiers"]["NA"] > 0 and j["tiers"]["T2"] > 0
    doc = json.loads(cl.read_text(encoding="utf-8"))
    scored = next(i for i in doc["items"] if i["title"] == "遊戲計分")
    assert scored["baseline"]["android"] == "pass" and scored["actions"][0] == {"do": "navigate", "to": "main_game"} and scored["unbound_steps"]
    lint = sh(SCRIPTS / "aiqa_testgen.py", "lint", "--checklist", cl, "--game", "ghy", "--machine", "aztec2")["data"]
    assert lint["errors"] == []


def test_checklist_lint_counterexamples(tmp_path):
    import aiqa_testgen as T
    pack = C.load_pack("demo-slot")
    base = json.loads((SKILL / "examples" / "demo-slot.checklist.json").read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(base))
    bad["items"][0]["assertions"][0].pop("expr"); bad["items"][0]["assertions"][1]["oracle"] = "magic"
    bad["items"][0]["actions"][0] = {"do": "tap", "target": "btn:nope"}; bad["items"][1]["assertions"] = []
    rules = {v["rule"] for v in T.lint(bad, pack) if v["severity"] == "error"}
    assert {"CL-EXPR", "CL-ORACLE", "CL-TARGET", "CL-ASSERT"} <= rules


def test_oracle_rules():
    obs = {"win": [100, 0, 60], "multiplier": [2, 1, 2], "v": {"answer": None, "confidence": 0.9}}
    r = O.evaluate([{"id": "A", "oracle": "sequence", "expr": "seq_multiplier(multiplier_list, win_list)"},
                    {"id": "v", "oracle": "visual"}, {"id": "B", "oracle": "ocr_number", "expr": "missing_name > 1"}], obs)
    assert [x["result"] for x in r] == ["PASS", "NEEDS_HUMAN", "NEEDS_HUMAN"]
    assert O.item_verdict([[{"result": "PASS"}], [{"result": "FAIL"}]])["verdict"] == "FLAKY"
    with pytest.raises(ValueError):
        C.safe_eval("__import__('os')", {})
