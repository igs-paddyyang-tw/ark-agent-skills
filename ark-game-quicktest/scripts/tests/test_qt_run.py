"""qt_run patch 測試（--no-run，不需 go）：odds 載入路徑跟版本走、固定 seed、engine 副本外的範本不被改。"""
from __future__ import annotations
import json, pathlib, shutil, subprocess, sys
import pytest

yaml = pytest.importorskip("yaml")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FIX = SCRIPTS / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import qt_run  # noqa: E402

TPL = qt_run.DEFAULT_TEMPLATE
pytestmark = pytest.mark.skipif(not (TPL / "main.go").exists(), reason="快測範本不在預設位置")


def run(*args) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / "qt_run.py"), *args], capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def qt_dir(tmp: pathlib.Path, version: str) -> pathlib.Path:
    d = tmp / "qt"; (d / "odds").mkdir(parents=True)
    shutil.copy(FIX / "odds_1.0.0.template.json", d / "odds" / f"odds_{version}.json")
    shutil.copy(FIX / "qt-config.template.yaml", d / "qt-config.yaml")
    return d


def test_patch_odds_path_and_seed(tmp_path):
    before = (TPL / "main.go").read_bytes()
    d = qt_dir(tmp_path, "1.2.0")
    r = run("--dir", str(d), "--version", "1.2.0", "--no-run", "--seed", "777"); assert r["success"], r
    m = (d / "engine" / "main.go").read_text(encoding="utf-8")
    assert 'odds.LoadProbSetting("odds/odds_1.2.0.json")' in m and 'OddsVersion = "1.2.0"' in m
    assert "seed := int64(777) + int64(i)*1000003" in m and r["data"]["seed"] == 777
    assert (d / "engine" / "odds" / "odds_1.2.0.json").exists()
    assert (TPL / "main.go").read_bytes() == before                     # 範本本身不動


def test_seed_zero_keeps_template_behavior(tmp_path):
    d = qt_dir(tmp_path, "1.0.0")
    r = run("--dir", str(d), "--no-run", "--seed", "0"); assert r["success"], r
    m = (d / "engine" / "main.go").read_text(encoding="utf-8")
    assert "time.Now().UnixNano() + int64(i)*1000003" in m and r["data"]["seed"] == "time"


def test_lint_blocks_before_copy(tmp_path):
    d = qt_dir(tmp_path, "1.0.0")
    qc = yaml.safe_load((d / "qt-config.yaml").read_text(encoding="utf-8")); qc["structure"]["reels"] = 5
    (d / "qt-config.yaml").write_text(yaml.safe_dump(qc, allow_unicode=True), encoding="utf-8")
    r = run("--dir", str(d), "--no-run"); assert not r["success"] and r["rc"] == 3
    assert not (d / "engine").exists()
