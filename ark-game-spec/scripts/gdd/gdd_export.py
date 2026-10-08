#!/usr/bin/env python3
"""gdd_export — gdd-pack → 企劃樣板交付夾（與 data/references/kaiji-gdd-sample 同目錄結構）。

輸出（--out，預設 <pack>/export/）：
  <short_title>_素材總覽.html     單檔 HTML，圖一律以樣板相對路徑引用（symbols/…、illustrations/…、spec-reference-images/…）
  symbols/                        圖騰（symbols.yaml 的 file）
  illustrations/                  示意圖（screens.yaml 的 file、info.yaml slots 的 file）
  spec-reference-images/          規格書競品參考圖（symbols.yaml 的 ref_files）
三夾一律建立（即使空）；交付夾內不放任何 yaml / json，來源與核對清單寫回 pack 的 export-manifest.json。
資產來源讀 gdd.yaml.assets（相容舊中文夾名：圖騰 / 全示意圖 / 規格書競品圖），輸出一律英文夾名。

預設只複製「有被引用」的圖；--all-assets 連同來源三夾裡未引用的圖一起帶（重現樣板原夾用）。
守門：HTML 內每個圖片連結都必須在交付夾找得到，否則 exit 3（GATE_BLOCKED）。

用法:
  python gdd_export.py --pack data/gdd/<slug> [--out <dir>] [--all-assets] [--clean] [--style <style.yaml>]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdd_common as C  # noqa: E402
import gdd_build  # noqa: E402

IMG_RE = re.compile(r'(?:src|href)="([^"#?]+?\.(?:png|jpe?g|webp|gif|svg))"', re.I)
JSON_SRC_RE = re.compile(r'"src":"([^"]+)"')


def referenced(p: dict) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {k: set() for k in C.ASSET_DIRS}
    for s in p["symbols"]:
        if s.get("file"):
            refs["symbols"].add(s["file"])
        for rf in s.get("ref_files") or []:
            refs["reference"].add(rf)
    for s in p["screens"]:
        if s.get("file"):
            refs["screens"].add(s["file"])
    for slot in (p["info"].get("slots") or []):
        for it in slot.get("items") or []:
            if it.get("file"):
                refs["screens"].add(it["file"])
    return refs


def unsafe_names(refs: dict[str, set[str]]) -> list[dict]:
    """檔名必須是單層純檔名：含路徑分隔、..、絕對路徑者會讓複製越出三夾（src_dir / name、dst_dir / name）。"""
    bad = []
    for kind, names in refs.items():
        for n in sorted(names):
            s = str(n)
            if not s or "/" in s or "\\" in s or s in (".", "..") or pathlib.PurePath(s).is_absolute() or re.match(r"^[A-Za-z]:", s):
                bad.append({"kind": kind, "file": s})
    return bad


def export(pack: pathlib.Path, out: pathlib.Path, all_assets: bool, clean: bool, style: pathlib.Path | None) -> dict:
    p = C.load_pack(pack)
    bad = unsafe_names(referenced(p))
    if bad:                                               # 先擋再動檔：任何複製／清理都不發生
        C.fail("GATE_BLOCKED", f"{len(bad)} 個圖檔名含路徑（會越出交付夾三夾）",
               "symbols/screens/info 的 file、ref_files 只能寫純檔名（如 S1.png），圖放進對應來源夾", {"unsafe_names": bad[:10]})
    if clean and out.exists():
        for kind in C.ASSET_DIRS.values():
            shutil.rmtree(out / kind, ignore_errors=True)
        for old in out.glob("*" + C.BUNDLE_SUFFIX):
            old.unlink()
    refs = referenced(p)
    copied: dict[str, list[str]] = {k: [] for k in C.ASSET_DIRS}
    missing: list[dict] = []
    for kind, dst_name in C.ASSET_DIRS.items():
        dst_dir = out / dst_name
        dst_dir.mkdir(parents=True, exist_ok=True)
        src_dir = p["assets"]["root"] / p["assets"][kind]
        names = set(refs[kind])
        if all_assets and src_dir.exists():
            names |= {f.name for f in src_dir.iterdir() if f.is_file()}
        for name in sorted(names):
            src = src_dir / name
            if not src.exists():
                missing.append({"kind": kind, "file": name, "expected": str(src)})
                continue
            dst = dst_dir / name
            if not dst.exists() or dst.read_bytes() != src.read_bytes():
                shutil.copy2(src, dst)
            copied[kind].append(name)
    html_name = C.bundle_html_name(p["gdd"])
    html_path = out / html_name
    override = {"root": out.resolve(), "root_rel": ".", **C.ASSET_DIRS, "legacy": []}
    b = gdd_build.build(pack, html_path, style, assets=override, write_todo=False)
    # 守門：HTML 內所有圖片連結（img/href 與燈箱 gallery JSON）都要在交付夾內
    text = html_path.read_text(encoding="utf-8")
    links = set(IMG_RE.findall(text)) | {u for u in JSON_SRC_RE.findall(text) if u}
    broken = sorted(u for u in links if not (out / unquote(u)).exists())
    outside = sorted(u for u in links if unquote(u).split("/")[0] not in C.ASSET_DIRS.values())
    top = sorted(x.name for x in out.iterdir())
    expected_top = sorted([html_name, *C.ASSET_DIRS.values()])
    extra_top = [x for x in top if x not in expected_top]
    manifest = {"contract": "1", "pack": str(pack), "out": str(out), "html": html_name, "layout": expected_top,
                "copied": {C.ASSET_DIRS[k]: v for k, v in copied.items()},
                "counts": {C.ASSET_DIRS[k]: len(v) for k, v in copied.items()},
                "missing_sources": missing, "broken_links": broken, "links_outside_layout": outside,
                "extra_top_level": extra_top, "all_assets": all_assets, "source_stamp": b["stamp"],
                "legacy_source_dirs": p["assets"].get("legacy", [])}
    C.atomic_write(pack / "export-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out", help="交付夾（預設 <pack>/export）")
    ap.add_argument("--all-assets", action="store_true", help="連來源三夾未引用的圖一起帶")
    ap.add_argument("--clean", action="store_true", help="先清掉交付夾內舊的三夾與 *_素材總覽.html")
    ap.add_argument("--style")
    a = ap.parse_args()
    pack = C.pack_dir(a.pack)
    out = pathlib.Path(a.out) if a.out else pack / "export"
    m = export(pack, out, a.all_assets, a.clean, pathlib.Path(a.style) if a.style else None)
    data = {"out": m["out"], "html": m["html"], "counts": m["counts"], "missing_sources": len(m["missing_sources"]),
            "broken_links": m["broken_links"][:10], "extra_top_level": m["extra_top_level"], "manifest": str(pack / "export-manifest.json"),
            "delivery": f"樣板交付夾 {m['out']}｜{m['html']} + symbols {m['counts']['symbols']} / illustrations {m['counts']['illustrations']}"
                        f" / spec-reference-images {m['counts']['spec-reference-images']}｜缺圖 {len(m['missing_sources'])}｜斷鏈 {len(m['broken_links'])}"}
    if m["broken_links"] or m["links_outside_layout"]:
        C.fail("GATE_BLOCKED", f"交付夾 HTML 有 {len(m['broken_links'])} 個斷鏈、{len(m['links_outside_layout'])} 個連到三夾以外",
               "補齊來源圖（見 export-manifest.json missing_sources）或修正 symbols/screens 的 file 後重跑", data)
    C.emit(data, {"stage": "gdd_export"})


if __name__ == "__main__":
    main()
