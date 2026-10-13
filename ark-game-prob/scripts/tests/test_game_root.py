"""1.3 G-2：ARK_GAME_ROOT 預設落點（設計文件 game-pipeline-output-layout v2 §4）。
未設時維持舊預設 data/prob/<slug>（相容一版）；設了且沒給 --out/--dest → <root>/<slug>/prob。"""
from __future__ import annotations

import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import ps_common as C  # noqa: E402
from test_ps_pipeline import make_xlsx, run  # noqa: E402


def test_slug_of_layout_subdirs():
    assert C.slug_of(pathlib.Path("data/slot/lucky-cat/quicktest")) == "lucky-cat"
    assert C.slug_of(pathlib.Path("data/slot/lucky-cat/prob")) == "lucky-cat"
    assert C.slug_of(pathlib.Path("data/quicktest/lucky-cat")) == "lucky-cat"


def test_resolve_out_priority(monkeypatch):
    monkeypatch.delenv("ARK_GAME_ROOT", raising=False)
    assert C.resolve_out(None, None, "x") == (pathlib.Path("data/prob/x"), False), "未設 → 舊預設"
    monkeypatch.setenv("ARK_GAME_ROOT", "data/slot")
    assert C.resolve_out(None, None, "x") == (pathlib.Path("data/slot/x/prob"), True)
    assert C.resolve_out("out", None, "x") == (pathlib.Path("out/x"), False), "--out 優先於環境變數"
    assert C.resolve_out("out/x", None, "x") == (pathlib.Path("out/x"), False), "--out 已含 slug 不再加層"
    assert C.resolve_out("out", "d/prob", "x") == (pathlib.Path("d/prob"), True), "--dest 最優先"


def test_ps_run_lands_under_game_root(tmp_path, monkeypatch):
    xlsx = tmp_path / "測試機_機率表_v1.xlsx"
    make_xlsx(xlsx)
    root = tmp_path / "data" / "slot"
    monkeypatch.setenv("ARK_GAME_ROOT", str(root))
    r = run("ps_run.py", "--xlsx", str(xlsx), "--slug", "demo", "--game", "測試機")
    assert r["success"], r
    prob = root / "demo" / "prob"
    assert pathlib.Path(r["data"]["out"]) == prob
    for f in ("prob-data.json", "prob-spec.md", "prob-spec.html", "lint-report.json"):
        assert (prob / f).is_file(), f
    assert not (tmp_path / "data" / "prob").exists()
