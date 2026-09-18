"""spec_lint 反證：每條規則至少一個反例會變紅；乾淨 draft 綠。需 ffmpeg + 同層四個 skill（fake provider）。"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
SKILLS = SCRIPTS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import spec_lint  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="需要 ffmpeg")


def sh(*args, env=None):
    import os
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "ARK_LLM_PROVIDER": "fake", **(env or {})})
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("cva")
    code, _ = sh(SKILLS / "ark-video-understanding" / "scripts" / "tests" / "make_fixture.py", "--out", d / "v.mp4", "--kind", "slot")
    assert code == 0
    code, j = sh(SKILLS / "ark-video-understanding" / "scripts" / "vu_run.py", "--source", d / "v.mp4", "--domain", "slot-game", "--out", d / "runs")
    assert code == 0, j
    run = pathlib.Path(j["data"]["run"])
    code, j = sh(SKILLS / "ark-game-analysis" / "scripts" / "ga_run.py", "--run", run)
    assert code == 0, j
    code, j = sh(SCRIPTS / "gs_draft.py", "--run", run)
    assert code == 0, j
    return run


def errors_after(run, mutate):
    md = (run / "game-spec.draft.md").read_text(encoding="utf-8")
    (run / "mutated.md").write_text(mutate(md), encoding="utf-8")
    rep = spec_lint.lint(run, "mutated.md")
    return {v["rule"] for v in rep["violations"] if v["severity"] == "error"}


def test_clean_draft_green(run):
    rep = spec_lint.lint(run, "game-spec.draft.md")
    assert rep["summary"]["errors"] == 0


def test_number_outside_block(run):
    assert "NUM-OUTSIDE" in errors_after(run, lambda md: md.replace("<!-- section:overview items:C01 -->", "<!-- section:overview items:C01 -->\n轉輪有 5 個。"))


def test_fake_evidence(run):
    assert "OBS-EVIDENCE" in errors_after(run, lambda md: md.replace("evidence: E001", "evidence: E999", 1))


def test_unknown_name(run):
    assert "NAME" in errors_after(run, lambda md: md.replace("`game.title`", "`game.secret_name`", 1))


def test_kb_ref_must_exist(run):
    assert "KB-REF" in errors_after(run, lambda md: md.replace("`GKB-SLOT-FS-001`", "`GKB-SLOT-XX-999`"))


def test_proposed_needs_basis(run):
    assert "PROPOSED" in errors_after(run, lambda md: md.replace(" — basis: GKB-SLOT-FS-001, E001", ""))


def test_unknown_needs_question(run):
    assert "UNKNOWN-Q" in errors_after(run, lambda md: md.replace(" — question: Q001", "", 1))


def test_decided_needs_decision(run):
    assert "DECIDED-D" in errors_after(run, lambda md: md.replace("### OBSERVED\n- `game.title` = fake-value — evidence: E001 — confidence: high",
                                                                    "### DECIDED\n- `game.title` = fake-value — decision: D999", 1))


def test_missing_section(run):
    assert "SECTIONS" in errors_after(run, lambda md: md.replace("## 06. Paytable", "## 06. Pay Table"))


def test_config_spec_null_and_decide_deterministic(run):
    import yaml
    code, j = sh(SCRIPTS / "gs_decide.py", "--run", run, "--template")
    t = yaml.safe_load((run / "decisions.template.yaml").read_text(encoding="utf-8"))
    for d in t["decisions"]:
        d.update(decision="modify", value="v", reason="r", decided_by="p")
    (run / "decisions.yaml").write_text(yaml.safe_dump(t, allow_unicode=True, sort_keys=False), encoding="utf-8")
    code, j = sh(SCRIPTS / "gs_decide.py", "--run", run); assert code == 0, j
    v1a = (run / "game-spec.v1.md").read_bytes()
    code, j = sh(SCRIPTS / "gs_decide.py", "--run", run); assert code == 0
    assert v1a == (run / "game-spec.v1.md").read_bytes()
    assert spec_lint.lint(run, "game-spec.v1.md")["summary"]["errors"] == 0
    code, j = sh(SCRIPTS / "gs_dev.py", "--run", run); assert code == 0, j
    cfg = yaml.safe_load((run / "dev-spec" / "config-spec.yaml").read_text(encoding="utf-8"))
    assert cfg["parameters"] and all(p["value"] is None for p in cfg["parameters"])
    assert len(j["data"]["files"]) == 6
