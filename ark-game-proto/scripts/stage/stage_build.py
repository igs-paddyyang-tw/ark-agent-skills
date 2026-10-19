#!/usr/bin/env python3
"""stage_build — 組裝 ark-game-proto Stage（PixiJS 8 正式演出版型）

  遊戲包（game.js，Proto.game({...})）＋ runtime ＋ vendor/pixi.min.js ＋ 素材 → 輸出夾

用法:
  python stage_build.py --slug <slug> [--repo <aidev 根>] [--folder] [--serve]   # 依 data/slot 佈局（推薦）
      讀 data/slot/<slug>/game/pixi-client/stage.yaml（game、assets_base、max_side；舊 proto/stage 相容一版）
      → output/slot/<slug>/game/pixi-client/folder/（http 版）＋ single/index.html（單檔）
      → data/slot/<slug>/game/pixi-client/stage-build.json（清冊：來源 sha、大小、輸出路徑；入 git）
  python stage_build.py --game <game.js> --out <dir> [--assets-base <dir>] [--serve [--port 8765]]
  python stage_build.py --game <game.js> --out <dir> --single [--inline-quality 82] [--max-side 0]

  --assets-base  game.js 裡素材相對路徑的基準（預設 = game.js 所在目錄）；素材依相對路徑複製到輸出夾
  --serve        建置後起本機 http 服務（WebGL 不能讀 file:// 圖片，ADR-006）
  --single       單一 index.html：runtime / pixi / game.js 全部內嵌，圖片轉 WebP（有 Pillow）後以 data URI 內嵌，
                 可雙擊開啟、可寄送（影片不內嵌，改佔位；聲音內嵌）
輸出：<out>/index.html（+ 非 single 時 runtime/ vendor/ game.js 與素材）、<out>/stage-build.json（清冊）
需要 node 18+（讀 game.js 取得素材清單）；Pillow 選配（--single 轉 WebP）
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import io
import json
import mimetypes
import os
import pathlib
import shutil
import socketserver
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
RUNTIME = HERE / "runtime"
SRC = HERE.parent / "src"


def rt(s: str) -> pathlib.Path:
    """manifest 路徑：@src/x = ark-game-proto scripts/src/x（與驗證台共用）；其餘相對 runtime/"""
    return SRC / s[5:] if s.startswith("@src/") else RUNTIME / s


def rt_url(s: str) -> str:
    return f"runtime/_src/{s[5:]}" if s.startswith("@src/") else f"runtime/{s}"
PIXI = HERE.parent / "vendor" / "pixi.min.js"
TEMPLATE = HERE / "index.template.html"
VERSION = "1.1.0"


def emit(data: dict, ok=True, code=None, msg=None):
    out = {"success": ok, "contract": "1", "data": data, "meta": {"stage": "stage_build", "version": VERSION}}
    if not ok:
        out["error"] = {"code": code, "message": msg}
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.exit(0 if ok else {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "MISSING_DEP": 8}.get(code, 1))


def dump_config(game: pathlib.Path) -> dict:
    js = (
        "const {load}=require(process.argv[1]);const P=load(process.argv[2]);"
        "const c=P.config;process.stdout.write(JSON.stringify({name:c.name,assets:c.assets||{},feature:(c.spec&&c.spec.feature&&c.spec.feature.type)||null,"
        "stage:c.stage||{},info:!!c.info}));"
    )
    try:
        r = subprocess.run(["node", "-e", js, str(HERE / "tests" / "load.js"), str(game)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    except FileNotFoundError:
        emit({}, False, "MISSING_DEP", "需要 node 18+（讀 game.js 的素材清單）")
    if r.returncode != 0:
        emit({"stderr": r.stderr[-800:]}, False, "BAD_INPUT", f"無法載入 {game}")
    return json.loads(r.stdout)


def asset_srcs(cfg: dict) -> list[tuple[str, str]]:
    out = []
    for kind in ("images", "videos", "sounds"):
        for _id, e in (cfg["assets"].get(kind) or {}).items():
            src = e if isinstance(e, str) else (e or {}).get("src")
            if src and not src.startswith(("data:", "http:", "https:", "blob:")):
                out.append((kind, src))
    return out


def webp_data_uri(path: pathlib.Path, quality: int, max_side: int) -> tuple[str, int]:
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if mime in ("image/png", "image/jpeg", "image/webp"):
        try:
            from PIL import Image  # type: ignore
            im = Image.open(io.BytesIO(raw))
            if max_side and max(im.size) > max_side:
                k = max_side / max(im.size)
                im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
            buf = io.BytesIO()
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")
            im.save(buf, "WEBP", quality=quality, method=6)
            if buf.tell() < len(raw) or max_side:
                raw, mime = buf.getvalue(), "image/webp"
        except ImportError:
            pass
        except Exception:                                   # 壞圖 / 不支援格式 → 原檔內嵌
            pass
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii"), len(raw)


def build(game: pathlib.Path, out: pathlib.Path, assets_base: pathlib.Path, single: bool, quality: int, max_side: int,
          odds: pathlib.Path | None = None) -> dict:
    """odds（1.1.2）：遊戲包的機率設定檔（例 quicktest/odds/odds_<ver>.json）→ 在 game.js 之前注入 globalThis.HUFF_ODDS；
    遊戲包有 odds 模式時（例 HuffNPuff game.js），瀏覽器內 LocalService 就吃正式機率。None 時輸出與 1.1.1 相同。"""
    if not game.is_file():
        emit({}, False, "BAD_INPUT", f"找不到 {game}")
    if not PIXI.is_file():
        emit({}, False, "MISSING_DEP", f"找不到 {PIXI}")
    if odds is not None and not odds.is_file():
        emit({}, False, "BAD_INPUT", f"找不到 odds {odds}")
    odds_js = None
    if odds is not None:
        odds_txt = odds.read_text(encoding="utf-8").strip()
        try:
            json.loads(odds_txt)                            # 先驗 JSON 合法，壞檔不進產物
        except json.JSONDecodeError as e:
            emit({}, False, "BAD_INPUT", f"odds 不是合法 JSON：{odds.name}（{e}）")
        odds_js = f"globalThis.HUFF_ODDS = {odds_txt};"
    man = json.loads((RUNTIME / "manifest.json").read_text(encoding="utf-8"))
    cfg = dump_config(game)
    scripts = list(man["scripts"])
    feat = cfg.get("feature")
    for f in (man.get("features", {}).get(feat, {}) or {}).get("scripts", []) if feat else []:
        if rt(f).exists():
            scripts.insert(scripts.index("core/app.js"), f)
    out.mkdir(parents=True, exist_ok=True)
    missing, copied, inlined, inl_bytes = [], 0, {}, 0
    srcs = asset_srcs(cfg)
    if single:
        for kind, src in srcs:
            p = (assets_base / src).resolve()
            if not p.is_file():
                missing.append(src)
                continue
            if kind == "videos":
                continue                                    # 影片不內嵌（佔位），避免單檔爆大
            uri, n = webp_data_uri(p, quality, max_side) if kind == "images" else (f"data:{mimetypes.guess_type(p.name)[0] or 'audio/ogg'};base64," + base64.b64encode(p.read_bytes()).decode(), p.stat().st_size)
            inlined[src] = uri
            inl_bytes += n
        tag_s = "\n".join(f"<style>/* {s} */\n{(RUNTIME / s).read_text(encoding='utf-8')}\n</style>" for s in man["styles"])
        parts = [f"<script>/* vendor/pixi.min.js */\n{PIXI.read_text(encoding='utf-8')}\n</script>"]
        parts.append("<script>window.__STAGE_INLINE=" + json.dumps(inlined, ensure_ascii=False) + ";</script>")
        for s in scripts:
            parts.append(f"<script>/* {rt_url(s)} */\n{rt(s).read_text(encoding='utf-8')}\n</script>")
        if odds_js:
            parts.append(f"<script>/* odds: {odds.name} */\n{odds_js}\n</script>")
        parts.append(f"<script>/* game.js */\n{game.read_text(encoding='utf-8')}\n</script>")
        tag_j = "\n".join(p.replace("</script>\n</script>", "<\\/script>\n</script>") for p in parts)
    else:
        if (out / "runtime").exists():
            shutil.rmtree(out / "runtime")
        shutil.copytree(RUNTIME, out / "runtime")
        for s_ in scripts:
            if s_.startswith("@src/"):
                (out / "runtime" / "_src").mkdir(parents=True, exist_ok=True)
                shutil.copy2(rt(s_), out / rt_url(s_))
        (out / "vendor").mkdir(exist_ok=True)
        shutil.copy2(PIXI, out / "vendor" / "pixi.min.js")
        shutil.copy2(game, out / "game.js")
        if odds_js:
            (out / "odds.js").write_text(odds_js + "\n", encoding="utf-8")
        elif (out / "odds.js").exists():
            (out / "odds.js").unlink()
        root = out.resolve()
        for _kind, src in srcs:
            p = (assets_base / src).resolve()
            if not p.is_file():
                missing.append(src)
                continue
            dst = pathlib.Path(os.path.normpath(out / src)).resolve()
            if root not in dst.parents and dst != root:
                # 素材路徑跳出輸出夾（../ 太多層）→ 改放 _assets/ 並在 index 以對照表改寫
                dst = root / "_assets" / hashlib.sha1(src.encode()).hexdigest()[:10] / p.name
                inlined[src] = dst.relative_to(root).as_posix()
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists() or dst.stat().st_size != p.stat().st_size:
                shutil.copy2(p, dst)
            copied += 1
        tag_s = "\n".join(f'<link rel="stylesheet" href="runtime/{s}">' for s in man["styles"])
        tag_j = "\n".join(['<script src="vendor/pixi.min.js"></script>'] + (["<script>window.__STAGE_INLINE=" + json.dumps(inlined, ensure_ascii=False) + ";</script>"] if inlined else [])
                          + [f'<script src="{rt_url(s)}"></script>' for s in scripts]
                          + (['<script src="odds.js"></script>'] if odds_js else []) + ['<script src="game.js"></script>'])
    html = TEMPLATE.read_text(encoding="utf-8").replace("__TITLE__", str(cfg.get("name") or "Stage")).replace("__STYLES__", tag_s).replace("__SCRIPTS__", tag_j)
    idx = out / "index.html"
    idx.write_text(html, encoding="utf-8", newline="\n")
    rep = {"out": str(out), "index": str(idx), "mode": "single" if single else "folder", "game": str(game), "name": cfg.get("name"),
           "feature": feat, "scripts": len(scripts), "assets": len(srcs), "copied": copied, "inlined": len(inlined) if single else 0,
           "missing": missing, "bytes": idx.stat().st_size, "inline_mb": round(inl_bytes / 1e6, 2),
           "odds": str(odds) if odds is not None else None}
    (out / "stage-build.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def serve(out: pathlib.Path, port: int):
    os.chdir(out)
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Stage 服務中：http://localhost:{port}/index.html   （Ctrl+C 結束）", flush=True)
        httpd.serve_forever()


def find_repo(start: pathlib.Path) -> pathlib.Path | None:
    for d in [start, *start.parents]:
        if (d / "data" / "slot").is_dir() and (d / ".kiro").is_dir():
            return d
    return None


def load_stage_yaml(p: pathlib.Path) -> dict:
    cfg = {}
    if not p.exists():
        return cfg
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except ImportError:                                    # 極簡 key: value 解析（不需 pyyaml）
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ":" in ln and not ln.lstrip().startswith("#") and not ln.startswith(" "):
                k, v = ln.split(":", 1)
                cfg[k.strip()] = v.strip().strip('"\'')
    return cfg


def resolve_assets(base_dir: pathlib.Path, cands) -> pathlib.Path:
    """assets_base 可給字串或清單（Windows 路徑 / WSL 路徑 / 相對路徑），取第一個存在的；環境變數 STAGE_ASSETS 優先"""
    env = os.environ.get("STAGE_ASSETS")
    lst = ([env] if env else []) + (cands if isinstance(cands, list) else [cands] if cands else [])
    for c in lst:
        c = str(c)
        for q in (pathlib.Path(c), base_dir / c, pathlib.Path("/mnt/" + c[0].lower() + c[2:].replace("\\", "/")) if len(c) > 2 and c[1] == ":" else None):
            if q is not None and q.is_dir():
                return q.resolve()
    return base_dir


def slug_build(a) -> None:
    repo = pathlib.Path(a.repo).resolve() if a.repo else find_repo(pathlib.Path.cwd().resolve()) or find_repo(HERE)
    if not repo:
        emit({}, False, "BAD_INPUT", "找不到 aidev 根目錄（含 data/slot 與 .kiro），請給 --repo")
    # 佈局契約 v3（ark-game-spec references/game-layout-contract.md）：⑦ 用戶端在 game/pixi-client；舊 proto/stage 相容一版
    data = repo / "data" / "slot" / a.slug / "game" / "pixi-client"
    if not (data / "stage.yaml").is_file() and (repo / "data" / "slot" / a.slug / "proto" / "stage" / "stage.yaml").is_file():
        data = repo / "data" / "slot" / a.slug / "proto" / "stage"
    yml = load_stage_yaml(data / "stage.yaml")
    game = data / str(yml.get("game", "game.js"))
    assets = resolve_assets(data, yml.get("assets_base"))
    out = repo / "output" / "slot" / a.slug / "game" / "pixi-client"
    max_side = int(yml.get("max_side", a.max_side) or 0)
    odds = (data / str(yml["odds"])).resolve() if yml.get("odds") else None   # stage.yaml 的 odds:（相對本目錄；1.1.2）
    single = build(game, out / "single", assets, True, int(yml.get("inline_quality", a.inline_quality)), max_side, odds)
    if a.folder or a.serve:                                 # 資料夾版（http 服務用）：檔案多，需要時才產
        build(game, out / "folder", assets, False, a.inline_quality, 0, odds)
    man = {"schema": "proto-stage-build/1", "slug": a.slug, "skill": f"ark-game-proto {VERSION} stage", "game": game.relative_to(repo).as_posix(),
           "game_sha16": hashlib.sha256(game.read_bytes()).hexdigest()[:16],
           "odds": odds.relative_to(repo).as_posix() if odds else None, "odds_sha16": hashlib.sha256(odds.read_bytes()).hexdigest()[:16] if odds else None,
           "assets_base": str(assets), "assets": single["assets"], "missing": single["missing"],
           "outputs": {"single": (out / "single" / "index.html").relative_to(repo).as_posix(), "single_bytes": single["bytes"], "folder": (out / "folder").relative_to(repo).as_posix() if (a.folder or a.serve) else None},
           "runtime": "output 為重產物（不入 git）；依 data/slot/_schema/layout.md：data < 1 MB、圖檔不入 data"}
    (data / "stage-build.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    if single["bytes"] > a.budget_mb * 1e6:
        emit(man, False, "GATE_BLOCKED", f"單檔 {single['bytes'] / 1e6:.1f} MB 超過 {a.budget_mb} MB")
    man["delivery"] = f"{man['outputs']['single']}（{single['bytes'] / 1e6:.2f} MB）{('＋ ' + man['outputs']['folder'] + '/') if man['outputs']['folder'] else ''}｜素材 {single['assets']}（缺 {len(single['missing'])}）｜清冊 {(data / 'stage-build.json').relative_to(repo).as_posix()}"
    if a.serve:
        print(json.dumps({"success": True, "data": man}, ensure_ascii=False), flush=True)
        serve(out / "folder", a.port)
    emit(man)


def main():
    ap = argparse.ArgumentParser(description="ark-game-proto Stage 建置", allow_abbrev=False)
    ap.add_argument("--slug", help="依 data/slot/<slug>/game/pixi-client 佈局建置（契約 v3）")
    ap.add_argument("--repo")
    ap.add_argument("--folder", action="store_true", help="--slug 時另產資料夾版（http 服務用）")
    ap.add_argument("--game")
    ap.add_argument("--out")
    ap.add_argument("--assets-base")
    ap.add_argument("--odds", help="機率設定檔（odds_<ver>.json）→ 注入 globalThis.HUFF_ODDS（1.1.2）；--slug 時改讀 stage.yaml 的 odds:")
    ap.add_argument("--single", action="store_true")
    ap.add_argument("--inline-quality", type=int, default=82)
    ap.add_argument("--max-side", type=int, default=0)
    ap.add_argument("--budget-mb", type=float, default=15.0)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.slug:
        return slug_build(a)
    if not a.game or not a.out:
        emit({}, False, "BAD_INPUT", "需要 --slug，或 --game 與 --out")
    game = pathlib.Path(a.game).resolve()
    out = pathlib.Path(a.out).resolve()
    base = pathlib.Path(a.assets_base).resolve() if a.assets_base else game.parent
    rep = build(game, out, base, a.single, a.inline_quality, a.max_side, pathlib.Path(a.odds).resolve() if a.odds else None)
    if a.single and rep["bytes"] > a.budget_mb * 1e6:
        emit(rep, False, "GATE_BLOCKED", f"單檔 {rep['bytes'] / 1e6:.1f} MB 超過 {a.budget_mb} MB（調 --inline-quality 或 --max-side）")
    rep["delivery"] = f"{rep['index']}｜{rep['mode']}｜素材 {rep['assets']}（缺 {len(rep['missing'])}）｜{rep['bytes'] / 1e6:.2f} MB"
    if a.serve:
        print(json.dumps({"success": True, "data": rep}, ensure_ascii=False), flush=True)
        serve(out, a.port)
    emit(rep)


if __name__ == "__main__":
    main()
