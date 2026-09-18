"""偵測器召回（≥90%，±0.5 s）與 determinism（events.json / 幀位元組相同）。需 ffmpeg + numpy + Pillow + 同層 ark-game-domains。"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="需要 ffmpeg")


def sh(*args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def recall(truth, got, tol=0.5):
    return sum(1 for t in truth if any(abs(t - g) <= tol for g in got)) / max(1, len(truth))


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    d = tmp_path_factory.mktemp("fx")
    out = {}
    for kind in ("slot", "fast"):
        sh(HERE / "make_fixture.py", "--out", d / f"{kind}.mp4", "--kind", kind)
        out[kind] = (d / f"{kind}.mp4", json.loads((d / f"{kind}.mp4.events.json").read_text()))
    return out


def run_chain(video, domain, out):
    j = sh(SCRIPTS / "vu_run.py", "--source", video, "--domain", domain, "--out", out)
    run = pathlib.Path(j["data"]["run"])
    ev = json.loads((run / "frames" / "events.json").read_text())["events"]
    return run, ev


def test_slot_recall(fixtures, tmp_path):
    video, truth = fixtures["slot"]
    run, ev = run_chain(video, "slot-game", tmp_path / "cva")
    settles = [e["t"] for e in ev if e["label"] == "reel_stop"]
    assert recall(truth["settle"], settles) >= 0.9, settles
    assert recall(truth["scene"], [e["t"] for e in ev if e["label"] == "feature_transition"]) >= 0.9
    assert recall(truth["flash"], [e["t"] for e in ev if e["label"] == "big_win"]) >= 0.9
    assert (run / "evidence.jsonl").exists() and not (run / "evidence.jsonl").stat().st_mode & 0o222


def test_fast_phase_hold(fixtures, tmp_path):
    video, truth = fixtures["fast"]
    _run, ev = run_chain(video, "fast-game", tmp_path / "cva")
    holds = [e for e in ev if e["label"] == "phase_hold" and e["kind"] == "hold_start"]
    assert recall(truth["hold_start"], [h["t"] for h in holds]) >= 0.9
    assert all(2.5 <= h["extra"]["duration_s"] <= 3.5 for h in holds if h["t"] in truth["hold_start"] or any(abs(h["t"] - t) <= 0.5 for t in truth["hold_start"]))
    assert recall(truth["settle"], [e["t"] for e in ev if e["label"] == "result_reveal"]) >= 0.8


def test_determinism(fixtures, tmp_path):
    video, _ = fixtures["slot"]
    r1, ev1 = run_chain(video, "slot-game", tmp_path / "a")
    r2, ev2 = run_chain(video, "slot-game", tmp_path / "b")
    assert ev1 == ev2
    h = lambda r: sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in (r / "frames" / "keyframes").glob("*.jpg"))  # noqa: E731
    assert h(r1) == h(r2)
    strip = lambda r: [{k: v for k, v in json.loads(l).items() if k != "video_sha256"} for l in (r / "evidence.jsonl").read_text().splitlines()]  # noqa: E731
    assert strip(r1) == strip(r2)


def test_budget_hard_max(fixtures, tmp_path):
    video, _ = fixtures["slot"]
    run, _ = run_chain(video, "slot-game", tmp_path / "cva")
    r = subprocess.run([sys.executable, str(SCRIPTS / "vu_keyframes.py"), "--run", str(run), "--max-keyframes", "999"], capture_output=True, text=True)
    assert r.returncode == 9
