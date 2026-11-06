"""裝置健康熔斷（2026-10-29）：連續 CONN_FAILED item 即中止 main() 迴圈，
剩餘標 NEEDS_HUMAN、manifest.aborted=True、emit aborted=device_lost。
不碰真機：monkeypatch run_item 回受控 device_lost 序列，驗編排層行為。"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
SKILL = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import aiqa_run as R  # noqa: E402


def _expanded_checklist(tmp_path) -> pathlib.Path:
    """沿用 test_aiqa 的產生法：複製 demo-slot 範本 → expand 成可跑 checklist。"""
    cl = tmp_path / "cl.json"
    shutil.copy(SKILL / "examples" / "demo-slot.checklist.json", cl)
    subprocess.run([sys.executable, str(SCRIPTS / "aiqa_testgen.py"), "expand",
                    "--game", "demo-slot", "--out", str(cl)],
                   capture_output=True, text=True, encoding="utf-8", check=True)
    return cl


def _real_items(cl: pathlib.Path) -> list[str]:
    doc = json.loads(cl.read_text(encoding="utf-8"))
    # 只取會真的 run（非 NA / 非 block）的 item id，確保它們會進 run_item
    return [i["id"] for i in doc["items"] if i.get("tier") != "NA"]


def _run_main(cl, out, monkeypatch, lost_ids: set[str]):
    """跑 main()，但 run_item 對 lost_ids 回 device_lost=True（模擬 adb CONN_FAILED）。"""
    real_ids: dict[str, dict] = {}

    def fake_run_item(item, pack, dev_factory, run_dir, reader, visual, llm, timeout_s, mode="normal"):
        lost = item["id"] in lost_ids
        out_item = {"id": item["id"], "title": item["title"], "category": item.get("category"),
                    "folder": item.get("folder"), "tier": item["tier"],
                    "verdict": "NEEDS_HUMAN" if lost else "PASS",
                    "reason": "執行錯誤：adb failed CONN_FAILED" if lost else None,
                    "reps": [], "baseline": item.get("baseline"), "dir": None,
                    "device_lost": lost}
        real_ids[item["id"]] = out_item
        return out_item

    monkeypatch.setattr(R, "run_item", fake_run_item)
    argv = ["aiqa_run.py", "--checklist", str(cl), "--backend", "fake", "--out", str(out)]
    monkeypatch.setattr(sys, "argv", argv)
    # fake backend 不需真裝置；main() 的 fake 分支自建 dev_factory，run_item 已被攔截。
    # C.emit() 收尾會 sys.exit(0)，正常結束即 SystemExit(0)。
    with pytest.raises(SystemExit) as exc:
        R.main()
    assert exc.value.code == 0


def _load_results(out_root: pathlib.Path):
    run_dir = next(p for p in out_root.rglob("manifest.json")).parent
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))["results"]
    return manifest, results


def test_two_consecutive_lost_aborts(tmp_path, monkeypatch, capsys):
    cl = _expanded_checklist(tmp_path)
    ids = _real_items(cl)
    assert len(ids) >= 4, "需要足夠 item 才能驗中止後剩餘被標記"
    # 讓前兩個會 run 的 item 連續失聯 → 應在第 2 個觸發熔斷
    lost = {ids[0], ids[1]}
    _run_main(cl, tmp_path / "runs", monkeypatch, lost)
    manifest, results = _load_results(tmp_path / "runs")

    assert manifest["aborted"] is True, "連續 2 lost 應標 aborted"
    # 被 run 的前兩個 = NEEDS_HUMAN（device_lost）
    by_id = {r["id"]: r for r in results}
    assert by_id[ids[0]]["verdict"] == "NEEDS_HUMAN"
    assert by_id[ids[1]]["verdict"] == "NEEDS_HUMAN"
    # 第 3 個起（若存在且在 lost 之後）應為「中止後未執行」且 dir=None、reps=[]
    tail = [r for r in results if r["id"] in ids[2:]]
    assert tail, "應有被中止跳過的剩餘 item"
    for r in tail:
        assert r["verdict"] == "NEEDS_HUMAN"
        assert r["reps"] == [] and r["dir"] is None
        assert "device lost" in (r.get("reason") or "")
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["data"]["aborted"] == "device_lost"


def test_single_lost_does_not_abort(tmp_path, monkeypatch, capsys):
    cl = _expanded_checklist(tmp_path)
    ids = _real_items(cl)
    # 只有一個 item 失聯（非連續）→ 不應中止，後續照跑
    lost = {ids[0]}
    _run_main(cl, tmp_path / "runs", monkeypatch, lost)
    manifest, results = _load_results(tmp_path / "runs")
    assert manifest["aborted"] is False, "單一 lost 不應熔斷"
    by_id = {r["id"]: r for r in results}
    assert by_id[ids[0]]["verdict"] == "NEEDS_HUMAN"
    # 後續 item 仍被實際執行（PASS）
    assert by_id[ids[1]]["verdict"] == "PASS"
