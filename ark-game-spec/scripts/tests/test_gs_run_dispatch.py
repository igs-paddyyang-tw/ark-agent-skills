"""ark-game-spec 2.0 總編排 gs_run：--stage video / analyze（含 D-3 補 report）/ draft / all（停在 draft → 帶 decisions 續到 atlas）。
需 ffmpeg（make_fixture）；LLM 用 fake provider。"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
GS = SCRIPTS / "gs_run.py"
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="需要 ffmpeg")


def sh(*args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "ARK_LLM_PROVIDER": "fake", "PYTHONIOENCODING": "utf-8"})
    line = next((ln for ln in reversed(r.stdout.strip().splitlines()) if ln.startswith("{")), "{}")
    return r.returncode, json.loads(line)


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    d = tmp_path_factory.mktemp("gsrun")
    assert sh(SCRIPTS / "tests" / "make_fixture.py", "--out", d / "v.mp4", "--kind", "slot")[0] == 0
    return d


def test_stage_video_analyze_draft(video):
    code, j = sh(GS, "--stage", "video", "--source", video / "v.mp4", "--domain", "slot-game", "--out", video / "runs")
    assert code == 0, j
    run = pathlib.Path(j["data"]["run"])
    assert (run / "evidence.jsonl").exists() and j["data"]["next"].startswith("python scripts/gs_run.py --stage analyze")
    code, j = sh(GS, "--stage", "analyze", "--run", run)
    assert code == 0, j
    assert "report" in j["data"], "D-3：派發器必須補跑 ga_report"
    assert list((run / "report").glob("*-game-analysis-*.md")), "ga_report 應產出 md-report"
    code, j = sh(GS, "--stage", "draft", "--run", run)
    assert code in (0, 3)  # draft 可能有 lint warning → 3
    assert (run / "game-spec.draft.md").exists() and (run / "decisions.template.yaml").exists()


def test_stage_all_stops_at_draft_then_resumes(video, tmp_path):
    code, j = sh(GS, "--stage", "all", "--source", video / "v.mp4", "--domain", "slot-game", "--out", tmp_path / "runs", "--no-report")
    assert code == 0, j
    assert j["meta"].get("stopped_at") == "draft" and "ark-grill-me" in j["data"]["next"]
    run = pathlib.Path(j["data"]["run"])
    t = yaml.safe_load((run / "decisions.template.yaml").read_text(encoding="utf-8"))
    for dd in t["decisions"]:
        dd.update(decision="modify", value="v", reason="r", decided_by="p")
    (run / "decisions.yaml").write_text(yaml.safe_dump(t, allow_unicode=True, sort_keys=False), encoding="utf-8")
    # 續跑：decide → dev → atlas（對同一個 run 用 --stage decide/dev/atlas，等價於 all --decisions 的後半）
    assert sh(GS, "--stage", "decide", "--run", run)[0] == 0
    code, j = sh(GS, "--stage", "dev", "--run", run)
    assert code == 0, j
    assert (run / "dev-spec" / "config-spec.yaml").exists()
    code, j = sh(GS, "--stage", "atlas", "--run", run, "--slug", "demo", "--out", tmp_path / "atlas", "--library", tmp_path / "lib")
    assert code == 0, j
    assert pathlib.Path(j["data"]["site"]).exists()


def test_stage_pack_and_help():
    assert sh(GS, "--stage", "pack", "--all")[0] == 0
    r = subprocess.run([sys.executable, str(GS), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "--stage" in r.stdout
