"""ark-web-game 測試。pytest 執行：python -m pytest .kiro/skills/ark-web-game/scripts/tests"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

SKILL = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = SKILL / "scripts"
SCHEMA = pathlib.Path(__file__).resolve().parent / "fixtures" / "spin-result.schema.json"   # ark-game-proto schema 的測試複本
REFS = ["architecture", "result-contract", "wire-protocol", "extraction-sop", "delivery", "kb-loop", "client-vertical-slice"]

HEAD = "| # | 抽選點 | 參數 | Go | SpinResult 欄位 | 演出步驟 |\n|---|---|---|---|---|---|\n"
PROB = "## 3. 機率流程圖\n抽選點用 P-01、P-03。\n## 4. 參數表\n| P-04 | 起始框 |\n## 5. 其他\nP-99 不算\n"


def run(script: str, *args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", cwd=cwd)


# ---------- refs ----------
def test_refs_exist_and_listed():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for r in REFS:
        assert (SKILL / "references" / f"{r}.md").is_file(), r
        assert f"references/{r}.md" in text, f"SKILL.md 資產地圖沒列 {r}"
    for s in ["wg_trace_check.py", "wg_release.py", "wg_measure_assets.py", "wg_draw_scan.js", "wg_server_init.py", "wg_client_init.py", "wg_pack_assets.py"]:
        assert f"scripts/{s}" in text


def test_refs_version_matches():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    v = re.search(r'^\s+version:\s*"([^"]+)"', text, re.M).group(1)
    assert f"| {v} |" in text, "版本表沒有目前版號"


# ---------- trace ----------
def _trace(tmp: pathlib.Path, rows: str) -> pathlib.Path:
    p = tmp / "trace-map.md"
    p.write_text("---\ntype: trace-map\n---\n\n" + HEAD + rows, encoding="utf-8")
    (tmp / "prob.md").write_text(PROB, encoding="utf-8")
    return p


OK_ROWS = ("| M-① | 抽轉輪組 | P-01 | `SpinGrid` | `reel.combo` | 不演出 |\n"
           "| M-② | 判連線 | P-03 | `evaluate` | `base.ways[]{sym,len,cells}`、`base.win` | 框線 |\n"
           "| HS-① | 起始框 | P-04 | `playHS` | `feature.draw`、`feature.script.frames[]{idx,mat}` | 落框 |\n")


def test_trace_ok(tmp_path):
    p = _trace(tmp_path, OK_ROWS)
    r = run("wg_trace_check.py", p, "--prob-spec", tmp_path / "prob.md", "--schema", SCHEMA, "--json")
    assert r.returncode == 0, r.stdout
    d = json.loads(r.stdout)
    assert d["params"]["missing"] == [] and "P-99" not in d["params"]["expected"]


def test_trace_empty_cell(tmp_path):
    p = _trace(tmp_path, OK_ROWS + "| X-1 | 空白 | P-01 | `f` | `reel.stops` |  |\n")
    r = run("wg_trace_check.py", p, "--schema", SCHEMA)
    assert r.returncode == 1 and "空白欄" in r.stdout


def test_trace_unknown_field(tmp_path):
    p = _trace(tmp_path, OK_ROWS + "| X-2 | 錯欄 | P-01 | `f` | `reel.stopz`、`base.ways[]{sym,foo}` | 停輪 |\n")
    r = run("wg_trace_check.py", p, "--schema", SCHEMA)
    assert r.returncode == 1 and "stopz" in r.stdout and "foo" in r.stdout


def test_trace_missing_param(tmp_path):
    p = _trace(tmp_path, OK_ROWS.replace("| HS-① | 起始框 | P-04 |", "| HS-① | 起始框 | — |"))
    r = run("wg_trace_check.py", p, "--prob-spec", tmp_path / "prob.md", "--schema", SCHEMA)
    assert r.returncode == 1 and "P-04" in r.stdout


def test_trace_table_mode(tmp_path):
    """還原（xlsx）模式 prob-spec：沒有 P-xx，改以「### 表 X-n」表號檢查覆蓋（0.9.0）"""
    prob = "## 3. 機率流程圖\n\n## 4. 參數表\n\n### 表 M-1　主遊戲轉輪\n\n### 表 F-5　木箱\n\n### 表 F-6　銀箱\n\n## 5. 其他\n"
    rows = ("| M-① | 抽轉輪組 | 表 M-1 | `Play` | `reel.combo` | 不演出 |\n"
            "| F-⑧ | 開箱 | 表 F-5、F-6 | `playFG` | `feature.script` | 開箱 |\n")
    p = tmp_path / "trace-map.md"
    p.write_text("---\ntype: trace-map\n---\n\n" + HEAD + rows, encoding="utf-8")
    (tmp_path / "prob.md").write_text(prob, encoding="utf-8")
    r = run("wg_trace_check.py", p, "--prob-spec", tmp_path / "prob.md", "--schema", SCHEMA, "--json")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["params"]["mode"] == "table" and d["params"]["missing"] == [], r.stdout
    p.write_text("---\ntype: trace-map\n---\n\n" + HEAD + rows.replace("表 F-5、F-6", "表 F-5"), encoding="utf-8")
    r = run("wg_trace_check.py", p, "--prob-spec", tmp_path / "prob.md", "--schema", SCHEMA)
    assert r.returncode == 1 and "F-6" in r.stdout


def test_trace_no_table(tmp_path):
    p = tmp_path / "t.md"
    p.write_text("沒有表格", encoding="utf-8")
    assert run("wg_trace_check.py", p, "--schema", SCHEMA).returncode == 2


# ---------- release ----------
def _build(tmp: pathlib.Path) -> pathlib.Path:
    d = tmp / "dist"
    for rel, data in {"assets/core/bg.webp": b"bg", "assets/core/sym.json": b"{}", "assets/oh/house.webp": b"house",
                      "index.html": b"<html>", "manifest.json": b'{"bundles":[]}'}.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    (tmp / "bundles.json").write_text(json.dumps({
        "huff-core": {"required": True, "include": ["assets/core/**", "index.html"]},
        "huff-openhouse": {"required": False, "include": ["assets/oh/*"]}}), encoding="utf-8")
    return d


def test_release_pack_verify_and_tamper(tmp_path):
    d = _build(tmp_path)
    r = run("wg_release.py", "pack", "--dir", d, "--bundles", tmp_path / "bundles.json",
            "--game-id", "huffnpuff-open-house", "--game-key", "huffnpuff", "--version", "1.0.0")
    assert r.returncode == 0, r.stdout
    rel = json.loads((d / "release.json").read_text(encoding="utf-8"))
    assert rel["releaseId"].startswith("huffnpuff-1.0.0+") and rel["manifestHash"].startswith("sha256:")
    core = next(b for b in rel["bundles"] if b["name"] == "huff-core")
    assert core["requiredForPlayable"] and len(core["files"]) == 3
    assert run("wg_release.py", "verify", "--dir", d, "--release", d / "release.json").returncode == 0
    (d / "assets/oh/house.webp").write_bytes(b"HOUSE")
    v = run("wg_release.py", "verify", "--dir", d, "--release", d / "release.json")
    assert v.returncode == 1 and "house.webp" in v.stdout


def test_release_overlap_and_required_empty(tmp_path):
    d = _build(tmp_path)
    (tmp_path / "b2.json").write_text(json.dumps({
        "a": {"required": True, "include": ["assets/**"]}, "b": {"required": False, "include": ["assets/oh/*"]},
        "c": {"required": True, "include": ["nothing/**"]}}), encoding="utf-8")
    r = run("wg_release.py", "pack", "--dir", d, "--bundles", tmp_path / "b2.json",
            "--game-id", "g", "--game-key", "g", "--version", "0.1.0")
    assert r.returncode == 1 and "同時屬於" in r.stdout and "必要 bundle c" in r.stdout


def test_release_stage_yaml_bundles_key(tmp_path):
    d = _build(tmp_path)
    (tmp_path / "stage.yaml").write_text(
        "game: game.js\nbundles:\n  huff-core: { required: true, include: ['assets/core/**'] }\n", encoding="utf-8")
    r = run("wg_release.py", "pack", "--dir", d, "--bundles", tmp_path / "stage.yaml",
            "--game-id", "g", "--game-key", "g", "--version", "0.1.0")
    assert r.returncode == 0, r.stdout
    assert json.loads(r.stdout)["unassigned"] == 2   # index.html、assets/oh/house.webp


# ---------- server_init ----------
import shutil  # noqa: E402

import pytest  # noqa: E402


def test_server_init_scaffold(tmp_path):
    dest = tmp_path / "srv"
    r = run("wg_server_init.py", "--slug", "demo-slot", "--engine", "demo", "--module", "example.com/demo/go-server", "--out", dest)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (dest / "internal/prob/demo/game.go").is_file() and (dest / "cmd/server/main.go").is_file()
    main = (dest / "cmd/server/main.go").read_text(encoding="utf-8")
    assert '"example.com/demo/go-server/internal/prob/demo"' in main and "__MODULE__" not in main
    assert not list(dest.rglob("*.tmpl"))
    vj = json.loads((dest / "internal/ark-go/VENDORED.json").read_text(encoding="utf-8"))
    assert vj["sync_chain"][-1]["from"].startswith("ark-web-game")
    again = run("wg_server_init.py", "--slug", "demo-slot", "--engine", "demo", "--out", dest)
    assert again.returncode == 1, "已存在且未加 --force 應拒絕"
    assert run("wg_server_init.py", "--slug", "x", "--engine", "Bad-Name", "--out", tmp_path / "b").returncode == 2
    if shutil.which("go"):
        b = subprocess.run(["go", "build", "./..."], cwd=dest, capture_output=True, text=True)
        assert b.returncode == 0, b.stderr
        v = subprocess.run(["go", "test", "./internal/ark-go/"], cwd=dest, capture_output=True, text=True)
        assert v.returncode == 0, v.stdout + v.stderr   # vendored 守門：重算雜湊後通過
    else:
        pytest.skip("沒有 go，只驗檔案")


def test_client_init_scaffold(tmp_path):
    dest = tmp_path / "pgp-demo"
    r = run("wg_client_init.py", "--out", dest, "--game", "demo-slot", "--key", "demo", "--name", "Demo's Slot")
    assert r.returncode == 0, r.stdout + r.stderr
    for rel in ["package.json", "pnpm-workspace.yaml", "tools/sec_check.py", "packages/ark-wire/src/codec.ts", "packages/ark-wire/test/mock-ark.mjs",
                "packages/game-service/src/ws.ts", "packages/shared-types/src/protocol.ts", "games/demo-slot/src/main.ts",
                "games/demo-slot/src/game/controller.ts", "games/demo-slot/src/presenters/index.ts", "games/demo-slot/.wg-client.json",
                "games/demo-slot/e2e/e2e.mjs", "games/demo-slot/e2e/e2e.config.json", "games/demo-slot/assets.yaml"]:
        assert (dest / rel).is_file(), rel
    cfg = (dest / "games/demo-slot/src/game.config.ts").read_text(encoding="utf-8")
    assert "key: 'demo'" in cfg and 'name: "Demo\'s Slot"' in cfg
    assert json.loads((dest / "games/demo-slot/package.json").read_text(encoding="utf-8"))["name"] == "demo-slot"
    ec = json.loads((dest / "games/demo-slot/e2e/e2e.config.json").read_text(encoding="utf-8"))
    assert ec["game"] == "demo-slot" and ec["arkIdPrefix"] == "e2e-demo"
    for p in dest.rglob("*"):
        assert "__GAME__" not in p.as_posix() and not p.name.endswith(".tmpl"), p
        if p.is_file() and p.suffix in {".ts", ".json", ".html", ".md", ".yaml"}:
            t = p.read_text(encoding="utf-8")
            assert not re.search(r"__(GAME|KEY|NAME|NAME_JSON|REPO)__", t), p
    assert run("wg_client_init.py", "--out", dest, "--game", "demo-slot").returncode == 1, "非空且未加 --force 應拒絕"
    add = run("wg_client_init.py", "--out", dest, "--game", "second", "--add-game")
    assert add.returncode == 0 and (dest / "games/second/src/main.ts").is_file()
    assert run("wg_client_init.py", "--out", tmp_path / "x", "--game", "Bad_Name").returncode == 2
    # 完整建置很慢（pnpm install＋vite build）：WG_CLIENT_BUILD=1 才跑
    import os
    if os.environ.get("WG_CLIENT_BUILD") == "1" and shutil.which("pnpm"):
        for cmd in (["pnpm", "install"], ["pnpm", "-r", "test"], ["pnpm", "-r", "build"]):
            b = subprocess.run(cmd, cwd=dest, capture_output=True, text=True)
            assert b.returncode == 0, " ".join(cmd) + "\n" + b.stdout[-2000:] + b.stderr[-2000:]


def test_pack_assets(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    art = tmp_path / "art"
    art.mkdir()
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(art / "sym_A.png")
    Image.new("RGBA", (300, 100), (0, 0, 255, 255)).save(art / "logo.png")
    have_svg = True
    try:
        import cairosvg  # noqa: F401
    except ImportError:
        have_svg = False
    gen = tmp_path / "gen.py"
    gen.write_text("import sys,pathlib\no=pathlib.Path(sys.argv[2]);o.mkdir(parents=True,exist_ok=True)\n"
                   "(o/'bg.svg').write_text('<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"40\" height=\"80\"><rect width=\"40\" height=\"80\" fill=\"#0a0\"/></svg>')\n", encoding="utf-8")
    sfx = tmp_path / "sfx"
    sfx.mkdir()
    has_ff = shutil.which("ffmpeg") is not None
    if has_ff:
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", "-c:a", "libvorbis", str(sfx / "ding.ogg")], check=True)
    cfg = {"schema": "pgp-assets/1", "game_key": "demo", "version": "0.1.0",
           "sources": {"art": {"dir": "art"}, "gen": {"generator": "gen.py"}, "sfx": {"env": "WG_TEST_SFX"}},
           "image": {"quality": 80},
           "bundles": {"demo-core": {"required": True, "images": {"sym_A": "art:sym_A", "logo": {"src": "art:logo", "max_side": 150}, **({"bg": "gen:bg"} if have_svg else {})}},
                       "demo-audio": {"sounds": {"sfx_ding": "sfx:ding.ogg"}} if has_ff else {"images": {}}}}
    cp = tmp_path / "assets.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    r = run("wg_pack_assets.py", "--config", cp, "--out", tmp_path / "out", "--set", f"sfx={sfx}")
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads(r.stdout)
    out = tmp_path / "out" / "assets"
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert man["meta"]["schema"] == "pgp-assets-manifest/1" and man["meta"]["required"] == ["demo-core"]
    core = {a["alias"]: a["src"] for a in man["bundles"][0]["assets"]}
    assert set(core) >= {"sym_A", "logo"} and all(re.search(r"\.[0-9a-f]{8}\.webp$", s) for s in core.values())
    assert Image.open(out / core["logo"]).size == (150, 50), "max_side 生效"
    if has_ff:
        assert {s.split(".")[-1] for s in man["sounds"][0]["src"]} == {"ogg"}
    rel = json.loads((out / "release.json").read_text(encoding="utf-8"))
    assert rel["schema"] == "web-game-release/1" and res["requiredBytes"] > 0
    assert run("wg_release.py", "verify", "--dir", out, "--release", out / "release.json").returncode == 0
    cfg["bundles"]["demo-core"]["images"]["nope"] = "art:missing"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    bad = run("wg_pack_assets.py", "--config", cp, "--only-check", "--set", f"sfx={sfx}")
    assert bad.returncode == 1 and "missing" in bad.stdout


def test_pack_assets_svg_engines(tmp_path):
    """SVG 兩種轉圖方式（cairosvg、瀏覽器）尺寸一致；缺工具時 skip"""
    pytest.importorskip("PIL")
    from PIL import Image
    gen = tmp_path / "g"
    gen.mkdir()
    (gen / "bg.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="80"><rect width="40" height="80" fill="#0a0"/></svg>', encoding="utf-8")
    cfg = {"schema": "pgp-assets/1", "game_key": "d", "version": "0.1.0", "sources": {"art": {"dir": "g"}},
           "bundles": {"d-core": {"required": True, "images": {"bg": {"src": "art:bg", "scale": 2}}}}}
    cp = tmp_path / "a.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    sizes = {}
    for eng in ("cairo", "browser"):
        r = run("wg_pack_assets.py", "--config", cp, "--out", tmp_path / eng, "--svg-engine", eng)
        if r.returncode != 0:
            continue
        man = json.loads((tmp_path / eng / "assets" / "manifest.json").read_text(encoding="utf-8"))
        sizes[eng] = Image.open(tmp_path / eng / "assets" / man["bundles"][0]["assets"][0]["src"]).size
        assert json.loads(r.stdout)["svgEngine"] == eng
    if not sizes:
        pytest.skip("cairosvg 與瀏覽器轉圖都不可用")
    assert all(s == (80, 160) for s in sizes.values()), sizes


def test_pack_assets_l2_passthrough_dir_priority_export(tmp_path, monkeypatch):
    """0.10.0 素材版控分層：dir（repo 內 L2）優先於 env／generator；成品 WebP 與同名音效直通（位元組不變）；--regen＋--export 凍結成品"""
    pytest.importorskip("PIL")
    from PIL import Image
    art = tmp_path / "art"
    art.mkdir()
    Image.new("RGBA", (32, 32), (9, 9, 9, 255)).save(art / "sym_A.webp", "WEBP", quality=70)
    art_bytes = (art / "sym_A.webp").read_bytes()
    gen = tmp_path / "gen.py"                                   # generator 產不同的圖（PNG），用來驗證 dir 優先、--regen 改用它
    gen.write_text("import sys,pathlib\nfrom PIL import Image\no=pathlib.Path(sys.argv[2]);o.mkdir(parents=True,exist_ok=True)\n"
                   "Image.new('RGBA',(16,16),(200,0,0,255)).save(o/'sym_A.png')\n", encoding="utf-8")
    sfx = tmp_path / "sfx"
    sfx.mkdir()
    (sfx / "ding.ogg").write_bytes(b"OggS-fake-ogg")
    (sfx / "ding.m4a").write_bytes(b"fake-m4a-bytes")           # 同名成品：不得呼叫 ffmpeg
    other = tmp_path / "env-sfx"
    other.mkdir()
    (other / "ding.ogg").write_bytes(b"OggS-from-env")
    monkeypatch.setenv("WG_T_SFX", str(other))
    cfg = {"schema": "pgp-assets/1", "game_key": "t", "version": "0.1.0",
           "sources": {"art": {"dir": "art", "generator": "gen.py"}, "sfx": {"dir": "sfx", "env": "WG_T_SFX"}},
           "image": {"quality": 86}, "audio": {"formats": ["ogg", "m4a"]},
           "bundles": {"t-core": {"required": True, "images": {"sym_A": "art:sym_A"}, "sounds": {"sfx_ding": "sfx:ding.ogg"}}}}
    cp = tmp_path / "assets.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    env = {**__import__("os").environ, "PATH": ""}               # 沒有 ffmpeg 也要過
    r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "wg_pack_assets.py"), "--config", str(cp), "--out", str(tmp_path / "o1")],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads(r.stdout)
    assert res["sources"] == {"art": "dir", "sfx": "dir"} and res["passthrough"] == 1 and res["svgEngine"] == "none" and not res["warnings"]
    out = tmp_path / "o1" / "assets"
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    img = man["bundles"][0]["assets"][0]["src"]
    assert (out / img).read_bytes() == art_bytes, "成品 WebP 直通：出貨位元組＝L2 檔"
    got = {s.rsplit(".", 1)[1]: (out / s).read_bytes() for s in man["sounds"][0]["src"]}
    assert got == {"ogg": b"OggS-fake-ogg", "m4a": b"fake-m4a-bytes"}, "dir 優先於 env；同名 m4a 直通"
    # 同一份 L2 打兩次 → release 完全相同（可重現）
    r2 = run("wg_pack_assets.py", "--config", cp, "--out", tmp_path / "o2")
    assert json.loads((tmp_path / "o2/assets/release.json").read_text(encoding="utf-8"))["releaseId"] == \
        json.loads((out / "release.json").read_text(encoding="utf-8"))["releaseId"], r2.stdout
    # 美術改版：--regen art 用 generator，--export 把成品寫回 L2
    frozen = tmp_path / "frozen"
    r3 = run("wg_pack_assets.py", "--config", cp, "--out", tmp_path / "o3", "--regen", "art", "--export", f"art={frozen}")
    assert r3.returncode == 0, r3.stdout + r3.stderr
    assert json.loads(r3.stdout)["sources"]["art"] == "generator"
    assert Image.open(frozen / "sym_A.webp").size == (16, 16)
    # dir 不存在 → 退回 generator（舊設定相容）
    cfg["sources"]["art"]["dir"] = "no-such-dir"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    r4 = run("wg_pack_assets.py", "--config", cp, "--out", tmp_path / "o4")
    assert r4.returncode == 0 and json.loads(r4.stdout)["sources"]["art"] == "generator"


def test_release_safe_defaults_in_templates():
    """0.11.0 上線前資安：範本預設要安全——Server 映像預設 CMD 不帶 -dev（fail closed）、Client 正式 build 不產 source map"""
    init = (SCRIPTS / "wg_server_init.py").read_text(encoding="utf-8")
    cmd = [ln for ln in init.splitlines() if ln.startswith("CMD [")]
    assert cmd and all('"-dev"' not in ln for ln in cmd), cmd
    vite = (SKILL / "assets/client-template/games/__GAME__/vite.config.ts").read_text(encoding="utf-8")
    assert "sourcemap: true" not in vite and "PGP_SOURCEMAP" in vite
