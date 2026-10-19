"""stage_build 守門：資料夾模式、單檔模式（內嵌、雙擊可開）、缺素材回報、試點素材相對路徑複製、預算。"""
from __future__ import annotations
import json, os, pathlib, shutil, subprocess, sys
import pytest

HERE = pathlib.Path(__file__).resolve().parent
STAGE = HERE.parent
SKILL = STAGE.parent.parent
DEMO = SKILL / "golden" / "stage-demo" / "game.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")


def run(*args):
    r = subprocess.run([sys.executable, str(STAGE / "stage_build.py"), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])


def test_folder_build(tmp_path):
    rc, d = run("--game", DEMO, "--out", tmp_path / "o")
    assert rc == 0 and d["success"], d
    o = tmp_path / "o"
    html = (o / "index.html").read_text(encoding="utf-8")
    assert '<script src="vendor/pixi.min.js"></script>' in html and 'runtime/slot/module.js' in html and 'runtime/features/' in html
    order = [html.index(f"runtime/{x}") for x in ("core/core.js", "service/service.js", "slot/logic.js", "slot/module.js", "core/app.js")]
    assert order == sorted(order), "載入順序錯"
    assert (o / "vendor" / "pixi.min.js").stat().st_size > 100_000 and (o / "game.js").exists()
    assert json.loads((o / "stage-build.json").read_text(encoding="utf-8"))["feature"] == "鎖格重轉"


def test_single_build_inlines_everything(tmp_path):
    rc, d = run("--game", DEMO, "--out", tmp_path / "s", "--single")
    assert rc == 0, d
    html = (tmp_path / "s" / "index.html").read_text(encoding="utf-8")
    assert '<script src=' not in html and '<link rel="stylesheet"' not in html, "單檔不得有外部 script / css"
    assert "window.__STAGE_INLINE=" in html and "Proto.game(" in html
    assert d["data"]["mode"] == "single"


def test_assets_copied_and_missing_reported(tmp_path):
    g = tmp_path / "pack" / "play"
    (g.parent / "art").mkdir(parents=True)
    g.mkdir()
    (g.parent / "art" / "a.png").write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc0000000020001e221bc330000000049454e44ae426082"))
    src = DEMO.read_text(encoding="utf-8").replace("assets: { images: {}, videos: {}, sounds: {} }", "assets: { images: { sym_H1: '../art/a.png', nope: '../art/none.png' }, videos: {}, sounds: {} }")
    (g / "game.js").write_text(src, encoding="utf-8")
    rc, d = run("--game", g / "game.js", "--out", tmp_path / "o2")
    assert rc == 0, d
    assert d["data"]["copied"] == 1 and d["data"]["missing"] == ["../art/none.png"]
    copied = list((tmp_path / "o2").rglob("a.png"))
    assert copied, "素材應複製到輸出夾"
    rc, d = run("--game", g / "game.js", "--out", tmp_path / "o3", "--single", "--budget-mb", "0.0001")
    assert rc == 3 and d["error"]["code"] == "GATE_BLOCKED"


def test_bad_game(tmp_path):
    rc, d = run("--game", tmp_path / "x.js", "--out", tmp_path / "o")
    assert rc == 2


def test_slug_layout(tmp_path):
    """--slug：data/slot/<slug>/game/pixi-client → output/slot/<slug>/game/pixi-client/single + 清冊留在 data（佈局契約 v3 ⑦）"""
    repo = tmp_path / "repo"
    (repo / ".kiro").mkdir(parents=True)
    d = repo / "data" / "slot" / "demo" / "game" / "pixi-client"
    d.mkdir(parents=True)
    shutil.copy2(DEMO, d / "game.js")
    (d / "stage.yaml").write_text("game: game.js\nmax_side: 512\n", encoding="utf-8")
    rc, j = run("--slug", "demo", "--repo", repo)
    assert rc == 0, j
    assert (repo / "output" / "slot" / "demo" / "game" / "pixi-client" / "single" / "index.html").exists()
    man = json.loads((d / "stage-build.json").read_text(encoding="utf-8"))
    assert man["schema"] == "proto-stage-build/1" and man["outputs"]["folder"] is None
    assert not (repo / "output" / "slot" / "demo" / "game" / "pixi-client" / "folder").exists()


def test_odds_injected_before_game(tmp_path):
    """1.1.2：--odds 在 game.js 之前注入 globalThis.HUFF_ODDS（單檔內嵌、資料夾版另產 odds.js）；壞 JSON 擋下。"""
    odds = tmp_path / "odds.json"
    odds.write_text(json.dumps({"huff": {"bet_cost": 240}, "extra_odds": {"max_win": 10000}}), encoding="utf-8")
    rc, d = run("--game", DEMO, "--out", tmp_path / "s", "--single", "--odds", odds)
    assert rc == 0, d
    html = (tmp_path / "s" / "index.html").read_text(encoding="utf-8")
    assert html.index("globalThis.HUFF_ODDS") < html.index("/* game.js */")
    rc, d = run("--game", DEMO, "--out", tmp_path / "f", "--odds", odds)
    assert rc == 0, d
    idx = (tmp_path / "f" / "index.html").read_text(encoding="utf-8")
    assert (tmp_path / "f" / "odds.js").is_file() and idx.index('src="odds.js"') < idx.index('src="game.js"')
    rc, d = run("--game", DEMO, "--out", tmp_path / "n", "--single")                # 不給 odds：無注入（與 1.1.1 相同）
    assert rc == 0 and "HUFF_ODDS" not in (tmp_path / "n" / "index.html").read_text(encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc, d = run("--game", DEMO, "--out", tmp_path / "b", "--single", "--odds", bad)
    assert rc != 0
