"""2.4 G-1：gs_run --stage publish —— ①② 定版件從 run 收進 data/slot/<slug>/{analysis, spec}，記 sha。
合成 run 目錄（不需 ffmpeg / LLM）。"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
GS = HERE.parent / "gs_run.py"


def sh(*args, env=None):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})})
    line = next((ln for ln in reversed(r.stdout.strip().splitlines()) if ln.startswith("{")), "{}")
    return r.returncode, json.loads(line)


def sha16(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


@pytest.fixture
def run(tmp_path):
    r = tmp_path / "output" / "slot" / "lucky-cat" / "runs" / "20261013-a"
    (r / "report").mkdir(parents=True)
    (r / "dev-spec").mkdir()
    (r / "frames").mkdir()
    (r / "manifest.json").write_text(json.dumps({"run_id": r.name}), encoding="utf-8")
    for f in ("game-analysis.yaml", "kb-refs.yaml"):
        (r / f).write_text(f"name: {f}\n", encoding="utf-8")
    (r / "evidence.jsonl").write_text('{"id": "E1"}\n', encoding="utf-8")
    (r / "report" / "2026-10-13-game-analysis-lucky-cat.md").write_text("# 競品分析\n", encoding="utf-8")
    (r / "game-spec.v1.md").write_text("# v1\n", encoding="utf-8")
    (r / "decisions.yaml").write_text("decisions: []\n", encoding="utf-8")
    (r / "dev-spec" / "config-spec.yaml").write_text("mode: design\nparameters: []\n", encoding="utf-8")
    (r / "dev-spec" / "feature-spec.md").write_text("# feature\n", encoding="utf-8")
    (r / "frames" / "f0001.png").write_bytes(b"\x89PNG")  # 不該被收
    return r


def test_publish_copies_and_records_sha(run, tmp_path):
    dest = tmp_path / "data" / "slot" / "lucky-cat"
    code, j = sh(GS, "--stage", "publish", "--run", run, "--dest", dest)
    assert code == 0, j
    d = j["data"]
    assert (dest / "analysis" / "game-analysis.yaml").is_file()
    assert (dest / "analysis" / "report" / "2026-10-13-game-analysis-lucky-cat.md").is_file()
    assert (dest / "spec" / "config-spec.yaml").is_file(), "config-spec 要提到 spec/ 規範位置（ps_layout L-SPEC）"
    assert (dest / "spec" / "dev-spec" / "feature-spec.md").is_file()
    assert not list(dest.rglob("*.png")), "frames 等可重產大檔不進 data"
    assert "dev-spec/ui-spec.md" in d["missing"] and d["replaced"] == []
    m = json.loads((dest / "publish-manifest.json").read_text(encoding="utf-8"))
    cs = next(f for f in m["files"] if f["path"] == "spec/config-spec.yaml")
    assert cs["sha256_16"] == sha16(dest / "spec" / "config-spec.yaml") and cs["source"] == "dev-spec/config-spec.yaml"
    # 重發：改來源 → 記錄被取代檔的舊 sha
    old = cs["sha256_16"]
    (run / "dev-spec" / "config-spec.yaml").write_text("mode: design\nparameters: [1]\n", encoding="utf-8")
    code, j = sh(GS, "--stage", "publish", "--run", run, "--dest", dest)
    assert code == 0 and j["data"]["replaced"] == ["spec/config-spec.yaml"]
    cs2 = next(f for f in j["data"]["files"] if f["path"] == "spec/config-spec.yaml")
    assert cs2["replaced_sha256_16"] == old


def test_publish_dest_from_ark_game_root(run, tmp_path):
    root = tmp_path / "data" / "slot"
    code, j = sh(GS, "--stage", "publish", "--run", run, "--slug", "lucky-cat", "--dry-run", env={"ARK_GAME_ROOT": str(root)})
    assert code == 0, j
    assert j["data"]["dest"] == (root / "lucky-cat").as_posix() and j["data"]["dry_run"] is True
    assert not (root / "lucky-cat").exists(), "dry-run 不寫入"


def test_publish_without_dest_or_root_is_bad_input(run):
    env = {k: v for k, v in os.environ.items() if k != "ARK_GAME_ROOT"}
    r = subprocess.run([sys.executable, str(GS), "--stage", "publish", "--run", str(run)], capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 2 and "ARK_GAME_ROOT" in r.stdout


def test_publish_refuses_to_overwrite_restore_live(run, tmp_path):
    dest = tmp_path / "data" / "slot" / "lucky-cat"
    (dest / "spec").mkdir(parents=True)
    (dest / "spec" / "config-spec.yaml").write_text("mode: restore-live\nparameters: []\n", encoding="utf-8")
    code, j = sh(GS, "--stage", "publish", "--run", run, "--dest", dest)
    assert code == 3 and "restore-live" in j["error"]["message"]
    assert "restore-live" in (dest / "spec" / "config-spec.yaml").read_text(encoding="utf-8")
    code, _ = sh(GS, "--stage", "publish", "--run", run, "--dest", dest, "--force")
    assert code == 0
