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
    r = subprocess.run([sys.executable, "-X", "utf8", str(STAGE / "stage_build.py"), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
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


def test_odds_required_game_loads_with_odds(tmp_path):
    """1.4.1：素材清單掃描（node 載入 game.js）也先注入 odds → 「沒有 odds 就丟錯」的遊戲包（例 magic-lamp）建得起來；沒給 odds 仍明確失敗。"""
    g = tmp_path / "game.js"
    g.write_text(DEMO.read_text(encoding="utf-8").replace("(function () {\n  'use strict';",
        "(function () {\n  'use strict';\n  if (!globalThis.HUFF_ODDS) throw new Error('需要 odds');", 1), encoding="utf-8")
    odds = tmp_path / "odds.json"
    odds.write_text(json.dumps({"ok": 1}), encoding="utf-8")
    rc, d = run("--game", g, "--out", tmp_path / "s", "--single", "--odds", odds)
    assert rc == 0 and d["success"], d
    rc, d = run("--game", g, "--out", tmp_path / "n", "--single")
    assert rc != 0 and not d["success"]


@pytest.mark.skipif(not os.environ.get("SLOTPROTO_BROWSER"), reason="SLOTPROTO_BROWSER=1 才跑（真瀏覽器）")
@pytest.mark.parametrize("single", [False, True])
def test_smoke_real_browser(tmp_path, single):
    """真瀏覽器冒煙：smoke.js（Playwright 或系統 Chrome / Edge）跑 stage-demo 一般局＋全部情境，0 頁面錯誤、帳務一致。"""
    rc, d = run("--game", DEMO, "--out", tmp_path / "o", *(["--single"] if single else []))
    assert rc == 0, d
    r = subprocess.run(["node", str(HERE / "smoke.js"), "--html", str(tmp_path / "o"), "--scenes", "all", "--out", str(tmp_path / "shots"), "--strict"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if r.returncode == 2:
        pytest.skip("沒有可用瀏覽器：" + r.stdout.strip()[-200:])
    assert r.returncode == 0, r.stdout[-1500:]
    rep = json.loads((tmp_path / "shots" / "smoke.json").read_text(encoding="utf-8"))
    assert rep["pass"] and not rep["errors"]


def test_bundles_release_and_service(tmp_path):
    """1.5.0：--bundles 產 manifest.json（PixiJS Assets）＋ release.json（ark-web-game wg_release，sha256 對實際位元組）；--service 注入結果來源。"""
    g = tmp_path / "pack" / "play"
    (g.parent / "art" / "core").mkdir(parents=True)
    (g.parent / "art" / "oh").mkdir(parents=True)
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc0000000020001e221bc330000000049454e44ae426082")
    (g.parent / "art" / "core" / "a.png").write_bytes(png)
    (g.parent / "art" / "oh" / "b.png").write_bytes(png + b"x")
    g.mkdir()
    src = DEMO.read_text(encoding="utf-8").replace("assets: { images: {}, videos: {}, sounds: {} }", "assets: { images: { sym_H1: '../art/core/a.png', house: '../art/oh/b.png' }, videos: {}, sounds: {} }")
    (g / "game.js").write_text(src, encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"demo-core": {"required": True, "include": ["../art/core/**"]}, "demo-oh": {"required": False, "include": ["../art/oh/*"]}}), encoding="utf-8")
    out = tmp_path / "o"
    rc, d = run("--game", g / "game.js", "--out", out, "--bundles", tmp_path / "b.json", "--game-key", "demo", "--version", "1.2.3", "--service", '{"kind":"ws","url":"/ws"}')
    assert rc == 0, d
    rel = d["data"]["release"]
    assert rel["releaseId"].startswith("demo-1.2.3+") and rel["bundles"]["boot"]["required"] and rel["bundles"]["demo-oh"]["files"] == 1
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [b["name"] for b in man["bundles"]] == ["demo-core", "demo-oh"] and man["bundles"][0]["assets"][0]["alias"] == "../art/core/a.png"
    assert 'window.__STAGE_SERVICE={"kind": "ws", "url": "/ws"}' in (out / "index.html").read_text(encoding="utf-8")
    wg = SKILL.parent / "ark-web-game" / "scripts" / "wg_release.py"
    v = subprocess.run([sys.executable, "-X", "utf8", str(wg), "verify", "--dir", str(out), "--release", str(out / "release.json")], capture_output=True, text=True, encoding="utf-8")
    assert v.returncode == 0, v.stdout
    hit = next(out.rglob("b.png"))
    hit.write_bytes(png + b"tampered")
    v = subprocess.run([sys.executable, "-X", "utf8", str(wg), "verify", "--dir", str(out), "--release", str(out / "release.json")], capture_output=True, text=True, encoding="utf-8")
    assert v.returncode == 1 and "b.png" in v.stdout


def test_slug_placeholder_mode_and_require_assets(tmp_path):
    """1.8.0：assets_base 指到不存在的外部參考資料夾 → 佔位模式照常建置（清冊不寫各機器絕對路徑）；--require-assets 才擋"""
    repo = tmp_path / "repo"
    (repo / ".kiro").mkdir(parents=True)
    d = repo / "data" / "slot" / "demo" / "game" / "pixi-client"
    d.mkdir(parents=True)
    shutil.copy2(DEMO, d / "game.js")
    (d / "stage.yaml").write_text("game: game.js\nassets_base:\n  - D:/no/such/ref/folder\n  - /mnt/d/no/such/ref/folder\n"
                                  "game_key: demo\nversion: 1.0.0\nbundles:\n  demo-core:\n    required: true\n    include: [\"../art/**\"]\n", encoding="utf-8")
    rc, j = run("--slug", "demo", "--repo", repo)
    assert rc == 0, j
    man = json.loads((d / "stage-build.json").read_text(encoding="utf-8"))
    assert man["assets_mode"] == "placeholder" and man["assets_base"] == "placeholder", man
    assert str(tmp_path) not in json.dumps(man, ensure_ascii=False), "清冊不得寫入本機絕對路徑"
    assert man["release"] is None and "佔位模式" in man.get("release_note", ""), "佔位模式不產 release（必要 bundle 為空不得擋建置）"
    if man["missing"]:
        rc2, j2 = run("--slug", "demo", "--repo", repo, "--require-assets")
        assert rc2 != 0 and "require-assets" in json.dumps(j2, ensure_ascii=False)
    # 參考資料夾在 repo 外且存在 → external:<最後兩層>
    ext = tmp_path / "ext" / "refs"
    ext.mkdir(parents=True)
    (d / "stage.yaml").write_text(f"game: game.js\nassets_base: {ext.as_posix()}\n", encoding="utf-8")
    rc3, _ = run("--slug", "demo", "--repo", repo)
    man3 = json.loads((d / "stage-build.json").read_text(encoding="utf-8"))
    assert rc3 == 0 and man3["assets_base"] == "external:ext/refs" and man3["assets_mode"] in ("ref", "partial")
