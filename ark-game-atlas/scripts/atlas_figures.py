#!/usr/bin/env python3
"""atlas_figures — 由 run 的 keyframes 依 pack atlas/figures.yaml 產出 figure（deterministic）。

用法:
  python atlas_figures.py --run <run> --book <atlas_dir>   （通常由 atlas_compile 呼叫）
figure 型別：hero（封面）、frame（單幀，燒 caption）、strip（時序條，箭頭）、state_frames（狀態機各 state 縮圖）。
產出 assets/figures/Fnnn.jpg + figures.json：每筆記 evidence、時間碼、來源幀 sha、ops，同 run 重編 bit-identical。
不畫框、不標物件（observations 無座標）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_common as C  # noqa: E402

LOW = {"fallback", "scene", "periodic"}


def _pil():
    try:
        from PIL import Image, ImageDraw
        return Image, ImageDraw
    except ImportError:
        C.fail("DRIVER_MISSING", "缺 Pillow", "pip install Pillow --break-system-packages")


def burn(img, text: str, Image, ImageDraw):
    d = ImageDraw.Draw(img)
    w = max(7 * len(text) + 12, 60)
    d.rectangle([8, img.height - 26, 8 + w, img.height - 6], fill=(0, 0, 0))
    d.text((14, img.height - 23), text, fill=(255, 230, 0))
    return img


def pick_frame(kfs: list[dict], prefer: list[str]) -> dict | None:
    for lb in prefer:
        c = [k for k in kfs if k["label"] == lb]
        if c:
            return c[0]
    prim = [k for k in kfs if k["label"] not in LOW]
    return (prim or kfs or [None])[0]


def pick_strip(kfs: list[dict], rule: dict) -> list[dict]:
    if rule.get("around"):
        idx = next((i for i, k in enumerate(kfs) if k["label"] == rule["around"]), None)
        if idx is None:
            return []
        lo, hi = max(0, idx - int(rule.get("before", 2))), min(len(kfs), idx + int(rule.get("after", 2)) + 1)
        return kfs[lo:hi][: int(rule.get("max", 5))]
    out, pos = [], 0
    for lb in rule.get("labels", []):
        nxt = next((k for k in kfs[pos:] if k["label"] == lb), None)
        if nxt:
            out.append(nxt)
            pos = kfs.index(nxt) + 1
    return out[: int(rule.get("max", 5))]


def save_frame(src: pathlib.Path, dst: pathlib.Path, caption: str, cfg: dict, Image, ImageDraw) -> dict:
    with Image.open(src) as im:
        im = im.convert("RGB")
        mw = int(cfg.get("max_width", 1280))
        if im.width > mw:
            im = im.resize((mw, int(im.height * mw / im.width)))
        if cfg.get("burn_caption", True):
            burn(im, caption, Image, ImageDraw)
        im.save(dst, quality=int(cfg.get("quality", 82)), subsampling=0)
        return {"w": im.width, "h": im.height}


def save_strip(srcs: list[pathlib.Path], caps: list[str], dst: pathlib.Path, cfg: dict, Image, ImageDraw) -> dict:
    cw = int(cfg.get("cell_width", 420))
    ims = []
    for p, cap in zip(srcs, caps):
        with Image.open(p) as im:
            im = im.convert("RGB").resize((cw, int(im.height * cw / im.width)))
            burn(im, cap, Image, ImageDraw)
            ims.append(im)
    gap = 28 if cfg.get("arrow", True) else 8
    h = max(i.height for i in ims)
    out = Image.new("RGB", (cw * len(ims) + gap * (len(ims) - 1), h), (18, 18, 18))
    d = ImageDraw.Draw(out)
    x = 0
    for i, im in enumerate(ims):
        out.paste(im, (x, (h - im.height) // 2))
        x += cw
        if i < len(ims) - 1:
            if cfg.get("arrow", True):
                cy = h // 2
                d.polygon([(x + 6, cy - 8), (x + gap - 6, cy), (x + 6, cy + 8)], fill=(230, 200, 90))
            x += gap
    out.save(dst, quality=82, subsampling=0)
    return {"w": out.width, "h": out.height}


def main() -> None:
    ap = argparse.ArgumentParser(description="atlas figures")
    ap.add_argument("--run", required=True)
    ap.add_argument("--book", required=True)
    a = ap.parse_args()
    Image, ImageDraw = _pil()
    run = C.run_dir(a.run)
    book = pathlib.Path(a.book)
    resolved, atlas_pack, _stale = C.load_atlas_pack(run)
    cfg = atlas_pack.get("figures", {})
    chapters = atlas_pack.get("chapters", [])
    kfs = json.loads((run / "frames" / "keyframes.json").read_text(encoding="utf-8"))["keyframes"]
    ev_by_frame = {e["frame"]: e for e in C.load_evidence(run) if e.get("frame")}
    analysis = C.yaml_load(run / "game-analysis.yaml")
    claim_ev = {c["key"]: c["evidence"] for it in analysis["items"] for c in it["claims"]}
    ev_frame = {e["evidence_id"]: e for e in C.load_evidence(run)}
    out_dir = book / "assets" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    figs, n = [], 0
    ev_of = lambda k: ev_by_frame.get(k["file"], {}).get("evidence_id", "E???")  # noqa: E731
    cap = lambda k: f"{ev_of(k)} · {k['ts']} · {k['label']}"  # noqa: E731

    def new_fig(ftype, chapter, keys, ops):
        nonlocal n
        n += 1
        fid = f"F{n:03d}"
        dst = out_dir / f"{fid}.jpg"
        caps = [cap(k) for k in keys]
        if ftype == "strip":
            dims = save_strip([run / k["file"] for k in keys], caps, dst, cfg.get("strip", {}), Image, ImageDraw)
        else:
            dims = save_frame(run / keys[0]["file"], dst, caps[0], cfg.get("frame", {}) if ftype != "state_frame" else {**cfg.get("frame", {}), "max_width": cfg.get("state_frames", {}).get("thumb_width", 320)}, Image, ImageDraw)
        figs.append({"figure_id": fid, "type": ftype, "chapter": chapter, "evidence": [ev_of(k) for k in keys],
                     "t": [k["t"] for k in keys], "ts": [k["ts"] for k in keys], "labels": [k["label"] for k in keys],
                     "src_frames_sha256": [C.sha_file(run / k["file"]) for k in keys], "file": f"assets/figures/{fid}.jpg",
                     "caption": " → ".join(caps) if ftype == "strip" else caps[0], **dims, "ops": ops,
                     "sha256": C.sha_file(dst)})
        return fid

    with C.Timer() as t:
        for ch in chapters:
            fig = ch.get("figure") or {}
            ftype = fig.get("type")
            if not ftype or ftype == "none" or ch.get("special"):
                continue
            if ftype == "hero":
                k = pick_frame(kfs, cfg.get("hero", {}).get("prefer", []))
                if k:
                    new_fig("hero", ch["id"], [k], {"prefer": cfg.get("hero", {}).get("prefer", [])})
            elif ftype == "frame":
                k = pick_frame(kfs, fig.get("prefer", []))
                if k:
                    new_fig("frame", ch["id"], [k], {"prefer": fig.get("prefer", [])})
            elif ftype == "strip":
                rule = (cfg.get("strips") or {}).get(fig.get("rule"), {})
                keys = pick_strip(kfs, rule)
                if len(keys) >= 2:
                    new_fig("strip", ch["id"], keys, {"rule": fig.get("rule"), **rule})
                elif keys:
                    new_fig("frame", ch["id"], keys[:1], {"rule": fig.get("rule"), "degraded": "strip<2"})
            elif ftype == "state_frames":
                sm = resolved["spec"].get("state_machine") or ""
                for m in re.finditer(r"^\s*(\w+)\s*-->\s*(\w+)\s*:.*\{\{evidence:([\w.]+)\}\}", sm, re.M):
                    state, key = m.group(2), m.group(3)
                    eids = [e for e in claim_ev.get(key, []) if e in ev_frame and ev_frame[e].get("frame")]
                    if eids:
                        k = next((x for x in kfs if x["file"] == ev_frame[eids[0]]["frame"]), None)
                        if k:
                            fid = new_fig("state_frame", ch["id"], [k], {"state": state, "claim_key": key})
                            figs[-1]["state"] = state
    C.atomic_write(book / "figures.json", json.dumps({"contract": C.CONTRACT, "run_id": C.load_manifest(run)["run_id"], "figures": figs,
                                                       "stats": {"count": len(figs), "by_type": {t2: sum(1 for f in figs if f["type"] == t2) for t2 in ("hero", "frame", "strip", "state_frame")}}},
                                                      ensure_ascii=False, indent=1))
    C.emit({"count": len(figs), "by_type": {t2: sum(1 for f in figs if f["type"] == t2) for t2 in ("hero", "frame", "strip", "state_frame")},
            "dir": str(out_dir)}, {"stage": "figures", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
