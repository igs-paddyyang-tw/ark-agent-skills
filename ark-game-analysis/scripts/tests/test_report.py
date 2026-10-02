"""ga_report 守門測試：deterministic、lint 必過、verdict 規則、finding 規則。"""
from __future__ import annotations
import json, os, pathlib, subprocess, sys
import pytest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))
import ga_report as R  # noqa: E402

yaml = pytest.importorskip("yaml")


def make_run(tmp: pathlib.Path, unknown_items: int = 0, violations: int = 0, visual: int = 5) -> pathlib.Path:
    run = tmp / "20260101-slot-game-test-001"; run.mkdir(parents=True)
    items = []
    for i in range(1, 5):
        unk = i <= unknown_items
        items.append({"id": f"S0{i}", "name": f"item_{i}", "entities": [],
                      "claims": [{"key": f"k{i}.a", "value": None if unk else True,
                                  "provenance": "UNKNOWN" if unk else "OBSERVED",
                                  "evidence": [] if unk else ["E001"], "confidence": "unknown" if unk else "high",
                                  "reasoning": ""}] * 2})
    ga = {"contract": "1", "run_id": run.name, "domain": "slot-game", "pack_version": "1.0", "pack_sha256": "ab" * 32,
          "model": "fake", "items": items,
          "stats": {"claims": 8, "unknown": unknown_items * 2, "entities": 1, "schema_violations": violations}}
    (run / "game-analysis.yaml").write_text(yaml.safe_dump(ga, allow_unicode=True), encoding="utf-8")
    (run / "kb-refs.yaml").write_text(yaml.safe_dump({"contract": "1", "run_id": run.name, "domain": "slot-game", "items": [
        {"item_id": "S01", "tags_used": ["x"], "informative": True, "refs": [{"id": "GKB-1", "title": "t", "score": 1.0, "cross_domain": False}]},
        {"item_id": "S02", "tags_used": ["x"], "informative": True, "refs": []},
    ]}, allow_unicode=True), encoding="utf-8")
    (run / "evidence.jsonl").write_text("\n".join(json.dumps({"evidence_id": f"E{i:03d}", "type": "visual", "t_sec": i}) for i in range(1, visual + 1)) + "\n", encoding="utf-8")
    (run / "manifest.json").write_text(json.dumps({"run_id": run.name, "video": {"sha256": "cd" * 32, "duration": 30.0},
                                                   "stages": {"analyze": {"at": "2026-01-02T03:04:05"}}}), encoding="utf-8")
    (run / "entities.json").write_text(json.dumps({"entities": {"symbol": ["symbol_a"]}, "all_ids": ["symbol_a"]}), encoding="utf-8")
    return run


def run_cli(run: pathlib.Path, *extra) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / "ga_report.py"), "--run", str(run), *extra],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def test_deterministic_and_lint_pass(tmp_path):
    run = make_run(tmp_path, unknown_items=1, violations=2)
    a = run_cli(run); assert a["success"] and a["data"]["lint"] == "PASS", a
    md = pathlib.Path(a["data"]["md"]); h1 = md.read_bytes()
    b = run_cli(run); assert md.read_bytes() == h1, "同輸入重編必須 bit-identical"
    assert md.name == "2026-01-02-game-analysis-20260101-slot-game-test-001.md"  # 日期取 manifest，非今天


def test_verdict_rules(tmp_path):
    assert run_cli(make_run(tmp_path / "a", unknown_items=0))["data"]["verdict"] == "confirmed"
    assert run_cli(make_run(tmp_path / "b", unknown_items=2))["data"]["verdict"] == "inconclusive"   # 50%
    assert run_cli(make_run(tmp_path / "c", unknown_items=4))["data"]["verdict"] == "rejected"       # 100% → P0


def test_finding_rules(tmp_path):
    d = run_cli(make_run(tmp_path, unknown_items=4, violations=1, visual=0))["data"]
    assert d["findings"]["P0"] == 1          # UNKNOWN > 60%
    assert d["findings"]["P1"] == 2          # violations + no visual evidence
    assert d["findings"]["P2"] == 4          # 四個分析項全 UNKNOWN
    md = pathlib.Path(d["md"]).read_text(encoding="utf-8")
    assert "## 機制主張總表" in md and "### S01 item_1" in md


def test_html_pair_ok(tmp_path):
    d = run_cli(make_run(tmp_path), "--html")["data"]
    assert d["pair"] == "OK"
    html = pathlib.Path(d["html"]).read_text(encoding="utf-8")
    assert "<!-- content-src:" in html and "data-theme=\"dark\"" in html


def test_claims_not_rewritten(tmp_path):
    """報告裡每條 claim key 都要原樣出現，且不得憑空多出 spec 沒有的 key。"""
    run = make_run(tmp_path)
    md = pathlib.Path(run_cli(run)["data"]["md"]).read_text(encoding="utf-8")
    ga = yaml.safe_load((run / "game-analysis.yaml").read_text(encoding="utf-8"))
    keys = {c["key"] for it in ga["items"] for c in it["claims"]}
    import re
    found = set(re.findall(r"\| `([a-z0-9_.]+)` \|", md))
    assert found == keys
