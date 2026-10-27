#!/usr/bin/env python3
"""wg_measure_assets — 量測遊戲素材大小，依 bundles 分組（定 Bundle 與預算前的依據；ark-web-game 計畫 P1 任務 1.3）。

兩種來源（自動擇一）：
  files   素材原檔（stage.yaml assets_base 找得到時）：讀 game.js 素材清單（node），量原檔位元組
  inline  單檔建置輸出（素材原檔不在本機時）：解析 single/index.html 的 window.__STAGE_INLINE，量內嵌後（WebP 轉檔後）位元組

用法:
  python wg_measure_assets.py --slug <slug> [--repo <aidev 根>] [--bundles <yaml|json>] [--html <single/index.html>] [--out <json>] [--check]
  python wg_measure_assets.py --html <single/index.html> [--bundles <yaml|json>] [--check]

分組：bundles 設定（同 stage.yaml bundles:）的 include glob 對素材相對路徑（game.js 裡的寫法）比對；沒設定時只依資料夾彙總。
--check：各組合計＋未分組 = 全部（張數、位元組都要相等），且同一素材不屬於兩組；不符 exit 1。
exit：0 成功；1 檢查不過；2 輸入錯誤。
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re
import sys

SKILLS = pathlib.Path(__file__).resolve().parents[2]
STAGE = SKILLS / "ark-game-proto" / "scripts" / "stage"


def out(obj: dict, code: int) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))
    sys.exit(code)


def glob_re(pat: str) -> re.Pattern:
    i, s = 0, ""
    while i < len(pat):
        if pat.startswith("**/", i):
            s, i = s + "(?:.*/)?", i + 3
        elif pat.startswith("**", i):
            s, i = s + ".*", i + 2
        elif pat[i] == "*":
            s, i = s + "[^/]*", i + 1
        else:
            s, i = s + re.escape(pat[i]), i + 1
    return re.compile("^" + s + "$")


def load_yaml(p: pathlib.Path) -> dict:
    t = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        return json.loads(t)
    import yaml  # type: ignore
    return yaml.safe_load(t) or {}


def from_inline(html: pathlib.Path) -> dict[str, int]:
    t = html.read_text(encoding="utf-8")
    m = re.search(r"window\.__STAGE_INLINE=(\{.*?\});</script>", t, re.S)
    if not m:
        out({"ok": False, "fatal": f"{html} 沒有 window.__STAGE_INLINE（不是單檔建置？）"}, 2)
    sizes = {}
    for src, uri in json.loads(m.group(1)).items():
        if isinstance(uri, str) and uri.startswith("data:") and ";base64," in uri:
            sizes[src] = len(base64.b64decode(uri.split(";base64,", 1)[1]))
    return sizes


def from_files(game: pathlib.Path, base: pathlib.Path, odds: pathlib.Path | None) -> tuple[dict[str, int], list[str]]:
    sys.path.insert(0, str(STAGE))
    import stage_build  # type: ignore  # noqa: E402
    cfg = stage_build.dump_config(game, odds)
    sizes, missing = {}, []
    for _kind, src in stage_build.asset_srcs(cfg):
        p = (base / src).resolve()
        if p.is_file():
            sizes[src] = p.stat().st_size
        else:
            missing.append(src)
    return sizes, missing


def main() -> None:
    ap = argparse.ArgumentParser(description="素材量測與分組")
    ap.add_argument("--slug")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--html")
    ap.add_argument("--bundles")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    repo = pathlib.Path(a.repo).resolve()
    yml, data = {}, None
    if a.slug:
        data = repo / "data" / "slot" / a.slug / "game" / "pixi-client"
        if not (data / "stage.yaml").is_file():
            out({"ok": False, "fatal": f"找不到 {data / 'stage.yaml'}"}, 2)
        yml = load_yaml(data / "stage.yaml")
    bundles = load_yaml(pathlib.Path(a.bundles)) if a.bundles else (yml.get("bundles") or {})
    if isinstance(bundles.get("bundles"), dict):
        bundles = bundles["bundles"]
    source, sizes, missing = None, {}, []
    if data is not None and not a.html:
        bases = yml.get("assets_base") or []
        bases = [bases] if isinstance(bases, str) else bases
        base = next((pathlib.Path(b) for b in bases if pathlib.Path(b).is_dir()), None)
        if base is None and not yml.get("assets_base"):
            base = data
        if base is not None:
            odds = (data / str(yml["odds"])).resolve() if yml.get("odds") else None
            sizes, missing = from_files(data / str(yml.get("game", "game.js")), base, odds)
            source = f"files:{base}"
    if source is None:
        html = pathlib.Path(a.html) if a.html else repo / "output" / "slot" / str(a.slug) / "game" / "pixi-client" / "single" / "index.html"
        if not html.is_file():
            out({"ok": False, "fatal": f"素材原檔不在本機，也找不到單檔建置 {html}（先跑 stage_build --slug）"}, 2)
        sizes = from_inline(html)
        source = f"inline:{html}"
    pats = {n: [glob_re(x) for x in (b or {}).get("include", [])] for n, b in bundles.items()}
    groups = {n: {"count": 0, "bytes": 0, "required": bool((b or {}).get("required", False))} for n, b in bundles.items()}
    unassigned = {"count": 0, "bytes": 0, "files": []}
    folders: dict[str, dict] = {}
    overlap = []
    for src, n in sorted(sizes.items()):
        hit = [g for g, rs in pats.items() if any(r.match(src) for r in rs)]
        if len(hit) > 1:
            overlap.append({"src": src, "bundles": hit})
        if hit:
            groups[hit[0]]["count"] += 1
            groups[hit[0]]["bytes"] += n
        else:
            unassigned["count"] += 1
            unassigned["bytes"] += n
            unassigned["files"].append(src)
        key = "/".join(src.replace("\\", "/").split("/")[:-1][-2:]) or "."
        f = folders.setdefault(key, {"count": 0, "bytes": 0})
        f["count"] += 1
        f["bytes"] += n
    total = {"count": len(sizes), "bytes": sum(sizes.values())}
    required = sum(g["bytes"] for g in groups.values() if g["required"])
    rep = {"schema": "wg-asset-measure/1", "slug": a.slug, "source": source, "total": total, "requiredBytes": required,
           "bundles": groups, "unassigned": {**unassigned, "files": unassigned["files"][:50]}, "missing": missing,
           "folders": dict(sorted(folders.items(), key=lambda kv: -kv[1]["bytes"])), "overlap": overlap}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = True
    if a.check:
        sc = sum(g["count"] for g in groups.values()) + unassigned["count"]
        sb = sum(g["bytes"] for g in groups.values()) + unassigned["bytes"]
        ok = sc == total["count"] and sb == total["bytes"] and not overlap
        rep["check"] = {"ok": ok, "sumCount": sc, "sumBytes": sb}
    out(rep, 0 if ok else 1)


if __name__ == "__main__":
    main()
