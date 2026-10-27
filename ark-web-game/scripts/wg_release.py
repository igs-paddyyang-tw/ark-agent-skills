#!/usr/bin/env python3
"""wg_release — 產生與驗證 Release Manifest（web-game-release/1）。

pack   依 bundles 設定，把建置資料夾內的檔案分組，對實際位元組算 sha256 與大小，輸出 release.json。
verify 依 release.json 重算每個檔案與 bundle 的雜湊，任何不符即失敗。

bundles 設定（yaml 或 json；也可直接給含 `bundles:` 的 stage.yaml）：
  huff-core:      { required: true,  include: ["assets/core/**"] }
  huff-openhouse: { required: false, include: ["assets/openhouse/**"] }

用法:
  python wg_release.py pack --dir <資料夾> --bundles <設定檔> --game-id <id> --game-key <key> --version 1.0.0 \
      [--runtime-api ^1.0.0] [--out <資料夾>/release.json]
  python wg_release.py verify --dir <資料夾> --release <release.json>

exit：0 通過；1 驗證失敗或設定衝突（同一檔案屬於兩個 bundle、必要 bundle 沒有檔案）；2 輸入錯誤。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

SCHEMA = "web-game-release/1"
PROTOCOL = {"result": "proto-stage-result/1", "info": "proto-stage-info/1", "wire": "ark-wire/1"}
SKIP = {"release.json", "manifest.json", "stage-build.json"}   # 清單與建置紀錄本身不屬任何 bundle


def out(obj: dict, code: int) -> None:
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(code)


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def glob_re(pat: str) -> re.Pattern:
    i, s = 0, ""
    while i < len(pat):
        if pat.startswith("**/", i):
            s += "(?:.*/)?"
            i += 3
        elif pat.startswith("**", i):
            s += ".*"
            i += 2
        elif pat[i] == "*":
            s += "[^/]*"
            i += 1
        elif pat[i] == "?":
            s += "[^/]"
            i += 1
        else:
            s += re.escape(pat[i])
            i += 1
    return re.compile("^" + s + "$")


def load_bundles(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError:
            out({"ok": False, "fatal": "需要 pyyaml，或改用 .json 設定"}, 8)
        data = yaml.safe_load(text)
    if isinstance(data, dict) and isinstance(data.get("bundles"), dict):
        data = data["bundles"]
    if not isinstance(data, dict) or not data:
        out({"ok": False, "fatal": f"{path} 沒有 bundles 設定"}, 2)
    return data


def bundle_hash(files: list[dict]) -> str:
    lines = "\n".join(f"{f['path']}\t{f['sha256']}" for f in sorted(files, key=lambda x: x["path"]))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def pack(a) -> None:
    root = pathlib.Path(a.dir)
    if not root.is_dir():
        out({"ok": False, "fatal": f"找不到資料夾：{root}"}, 2)
    cfg = load_bundles(pathlib.Path(a.bundles))
    pats = {name: [glob_re(p) for p in (spec or {}).get("include", [])] for name, spec in cfg.items()}
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.relative_to(root).as_posix() not in SKIP)
    owner: dict[str, str] = {}
    errors, unassigned = [], []
    groups: dict[str, list[dict]] = {name: [] for name in cfg}
    for p in files:
        rel = p.relative_to(root).as_posix()
        hits = [n for n, rs in pats.items() if any(r.match(rel) for r in rs)]
        if len(hits) > 1:
            errors.append(f"{rel} 同時屬於 {hits}")
            continue
        if not hits:
            unassigned.append(rel)
            continue
        owner[rel] = hits[0]
        groups[hits[0]].append({"path": rel, "sha256": sha256_file(p), "bytes": p.stat().st_size})
    bundles = []
    for name, spec in cfg.items():
        fl = groups[name]
        req = bool((spec or {}).get("required", False))
        if req and not fl:
            errors.append(f"必要 bundle {name} 沒有任何檔案")
        bundles.append({"name": name, "requiredForPlayable": req, "hash": "sha256:" + bundle_hash(fl),
                        "bytes": sum(f["bytes"] for f in fl), "files": fl})
    if errors:
        out({"ok": False, "errors": errors}, 1)
    mf = root / "manifest.json"
    combo = hashlib.sha256("\n".join(b["hash"] for b in bundles).encode()).hexdigest()
    rel = {
        "schema": SCHEMA,
        "releaseId": f"{a.game_key}-{a.version}+{combo[:7]}",
        "gameId": a.game_id,
        "gameVersion": a.version,
        "runtimeApi": a.runtime_api,
        "protocol": PROTOCOL,
        "manifestHash": ("sha256:" + sha256_file(mf)) if mf.is_file() else None,
        "bundles": bundles,
        "unassigned": unassigned,
        "status": "candidate",
    }
    dest = pathlib.Path(a.out) if a.out else root / "release.json"
    dest.write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    out({"ok": True, "release": str(dest), "releaseId": rel["releaseId"],
         "bundles": {b["name"]: {"files": len(b["files"]), "bytes": b["bytes"], "required": b["requiredForPlayable"]} for b in bundles},
         "unassigned": len(unassigned)}, 0)


def verify(a) -> None:
    root = pathlib.Path(a.dir)
    rp = pathlib.Path(a.release)
    if not root.is_dir() or not rp.is_file():
        out({"ok": False, "fatal": "找不到資料夾或 release.json"}, 2)
    rel = json.loads(rp.read_text(encoding="utf-8"))
    if rel.get("schema") != SCHEMA:
        out({"ok": False, "fatal": f"schema 不是 {SCHEMA}"}, 2)
    errors, n = [], 0
    for b in rel.get("bundles", []):
        for f in b.get("files", []):
            n += 1
            p = root / f["path"]
            if not p.is_file():
                errors.append(f"缺檔：{f['path']}")
                continue
            if p.stat().st_size != f["bytes"] or sha256_file(p) != f["sha256"]:
                errors.append(f"內容不符：{f['path']}")
        if b.get("hash") != "sha256:" + bundle_hash(b.get("files", [])):
            errors.append(f"bundle 雜湊不符：{b.get('name')}")
    mh = rel.get("manifestHash")
    if mh:
        mf = root / "manifest.json"
        if not mf.is_file() or "sha256:" + sha256_file(mf) != mh:
            errors.append("manifest.json 雜湊不符")
    out({"ok": not errors, "checked": n, "errors": errors}, 0 if not errors else 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Release Manifest 產生與驗證")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("--dir", required=True)
    p.add_argument("--bundles", required=True)
    p.add_argument("--game-id", required=True)
    p.add_argument("--game-key", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--runtime-api", default="^1.0.0")
    p.add_argument("--out")
    v = sub.add_parser("verify")
    v.add_argument("--dir", required=True)
    v.add_argument("--release", required=True)
    a = ap.parse_args()
    pack(a) if a.cmd == "pack" else verify(a)


if __name__ == "__main__":
    main()
