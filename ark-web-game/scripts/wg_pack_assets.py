#!/usr/bin/env python3
"""wg_pack_assets — 依遊戲素材設定（assets.yaml）打包正式 Client 素材：圖轉 WebP、音效多格式、PixiJS 分包清單、Release Manifest。

素材來源（sources）三種，可並用：
  generator  遊戲自帶的原創美術產生器（例：games/<game>/art/gen_art.py --out <暫存>），產出 SVG
  dir／env   素材資料夾（路徑或環境變數；原檔不複製進 repo，例：共用音效）
  override   同名覆蓋（美術組交 PNG／WebP 時，放這裡即取代產生器的圖，程式不用改）

輸出（<out>/assets/）：
  <bundle>/<alias>.<雜湊8>.webp｜.ogg｜.m4a    檔名帶內容雜湊（CDN 長快取）
  manifest.json                                 PixiJS Assets manifest（bundles[].assets[]{alias, src}）＋ sounds[]{alias, bundle, src[]}
  release.json                                  wg_release pack（每檔 sha256、bundle hash）並立即 verify

用法:
  python wg_pack_assets.py --config <assets.yaml> --out <資料夾> [--set sfx=<資料夾>] [--svg-engine auto|cairo|browser] [--only-check]
  --svg-engine：SVG 轉圖方式。auto（預設）＝有 cairosvg 用 cairosvg，否則用瀏覽器（wg_svg_render.mjs，需 node＋playwright）
  --set 名稱=路徑：覆寫 sources 的資料夾（等同設定環境變數）
  --only-check：只檢查設定與來源齊全，不輸出

需要：Pillow（WebP）；SVG 來源需 cairosvg（pip install cairosvg）或 node＋playwright（瀏覽器轉圖）；多格式音效需 ffmpeg（沒有時只輸出原格式並警告）。
注意：cairosvg 不支援 SVG paint-order 與文字漸層；瀏覽器轉圖兩者都支援，但字型以本機安裝為準（CJK 字需有 Noto Sans CJK 等字型）。
exit：0 成功；1 來源缺檔或驗證失敗；2 設定或環境錯誤。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parent
IMG_EXT = (".svg", ".png", ".webp", ".jpg", ".jpeg")


def die(msg: str, code: int = 2, **extra) -> None:
    print(json.dumps({"ok": False, "fatal": msg, **extra}, ensure_ascii=False, indent=1))
    sys.exit(code)


def load_cfg(p: pathlib.Path) -> dict:
    t = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        return json.loads(t)
    try:
        import yaml  # type: ignore
    except ImportError:
        die("需要 pyyaml（或改用 json 設定）")
    return yaml.safe_load(t) or {}


def h8(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:8]


class Sources:
    def __init__(self, cfg: dict, base: pathlib.Path, sets: dict[str, str], tmp: pathlib.Path):
        self.dirs: dict[str, list[pathlib.Path]] = {}
        self.missing_roots: list[str] = []
        for name, s in (cfg.get("sources") or {}).items():
            roots: list[pathlib.Path] = []
            ov = s.get("override")
            if isinstance(ov, dict) and ov.get("env") and os.environ.get(ov["env"]):
                roots.append(pathlib.Path(os.environ[ov["env"]]))
            elif isinstance(ov, str):
                roots.append((base / ov).resolve())
            if name in sets:
                roots.append(pathlib.Path(sets[name]))
            elif s.get("generator"):
                gen = (base / s["generator"]).resolve()
                out = tmp / f"gen-{name}"
                r = subprocess.run([sys.executable, str(gen), "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
                if r.returncode != 0:
                    die(f"產生器失敗：{gen}", 2, stderr=r.stderr[-1500:])
                roots.append(out)
            elif s.get("env") and os.environ.get(s["env"]):
                roots.append(pathlib.Path(os.environ[s["env"]]))
            elif s.get("dir"):
                roots.append((base / s["dir"]).resolve())
            roots = [r for r in roots if r.is_dir()]
            if not roots:
                self.missing_roots.append(f"{name}（{s.get('env') or s.get('dir') or s.get('generator')}；可用 --set {name}=<資料夾>；{s.get('hint', '')}）")
            self.dirs[name] = roots

    def find(self, ref: str) -> pathlib.Path | None:
        name, _, rel = ref.partition(":")
        for root in self.dirs.get(name, []):
            p = root / rel
            if p.suffix and p.is_file():
                return p
            for ext in IMG_EXT:
                q = root / f"{rel}{ext}"
                if q.is_file():
                    return q
        return None


class SvgRenderer:
    """SVG → PNG：cairosvg 或瀏覽器（批次，一次啟動）"""

    def __init__(self, engine: str):
        self.engine = engine
        self._cairo = None
        if engine in ("auto", "cairo"):
            try:
                import cairosvg  # type: ignore  # noqa: PLC0415
                self._cairo = cairosvg
                self.engine = "cairo"
            except ImportError:
                if engine == "cairo":
                    die("--svg-engine cairo 需要 cairosvg：pip install cairosvg")
                self.engine = "browser"
        self.cache: dict[tuple[str, float], bytes] = {}

    def prefetch(self, items: list[tuple[pathlib.Path, float]], tmp: pathlib.Path) -> None:
        """瀏覽器模式：一次轉完全部 SVG"""
        if self.engine != "browser" or not items:
            return
        node = shutil.which("node")
        if not node:
            die("SVG 轉圖需要 cairosvg（pip install cairosvg）或 node＋playwright")
        jobs = []
        for i, (p, sc) in enumerate(sorted(set(items))):
            jobs.append({"svg": str(p), "png": str(tmp / f"svg-{i}.png"), "scale": sc, "_key": [str(p), sc]})
        jf = tmp / "svg-jobs.json"
        jf.write_text(json.dumps(jobs), encoding="utf-8")
        r = subprocess.run([node, str(SCRIPTS / "wg_svg_render.mjs"), str(jf)], capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            die("瀏覽器轉圖失敗（需要 playwright＋Chromium；或改裝 cairosvg）", 2, stderr=r.stderr[-800:])
        for j in jobs:
            self.cache[(j["_key"][0], j["_key"][1])] = pathlib.Path(j["png"]).read_bytes()

    def png(self, src: pathlib.Path, scale: float) -> bytes:
        if self.engine == "cairo":
            return self._cairo.svg2png(url=str(src), scale=scale)
        hit = self.cache.get((str(src), scale))
        if hit is None:
            die(f"瀏覽器轉圖缺 {src}")
        return hit


def render_image(src: pathlib.Path, spec: dict, img: dict, svg: SvgRenderer) -> bytes:
    from PIL import Image  # noqa: PLC0415
    scale = float(spec.get("scale", img.get("scale", 1.0)))
    if src.suffix == ".svg":
        im = Image.open(io.BytesIO(svg.png(src, scale)))
    else:
        im = Image.open(src)
        if scale != 1.0:
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    ms = int(spec.get("max_side", img.get("max_side", 0)) or 0)
    if ms and max(im.size) > ms:
        k = ms / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    im = im.convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=int(spec.get("quality", img.get("quality", 85))), method=6)
    return buf.getvalue()


def audio_variants(src: pathlib.Path, formats: list[str], warn: list[str]) -> list[tuple[str, bytes]]:
    out = []
    have_ff = shutil.which("ffmpeg") is not None
    for fmt in formats:
        if src.suffix.lstrip(".").lower() == fmt:
            out.append((fmt, src.read_bytes()))
            continue
        if not have_ff:
            warn.append(f"沒有 ffmpeg，{src.name} 不產 {fmt}")
            continue
        codec = {"m4a": ["-c:a", "aac", "-b:a", "96k"], "mp3": ["-c:a", "libmp3lame", "-b:a", "96k"], "ogg": ["-c:a", "libvorbis", "-q:a", "4"]}.get(fmt)
        if not codec:
            warn.append(f"不支援的音效格式 {fmt}")
            continue
        with tempfile.TemporaryDirectory() as td:
            dst = pathlib.Path(td) / f"o.{fmt}"
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *codec, str(dst)], capture_output=True, text=True)
            if r.returncode != 0:
                warn.append(f"ffmpeg 轉 {src.name} → {fmt} 失敗：{r.stderr[-200:]}")
                continue
            out.append((fmt, dst.read_bytes()))
    if not out:
        out.append((src.suffix.lstrip("."), src.read_bytes()))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="正式 Client 素材打包")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--only-check", action="store_true")
    ap.add_argument("--svg-engine", choices=["auto", "cairo", "browser"], default="auto")
    a = ap.parse_args()
    cfgp = pathlib.Path(a.config).resolve()
    if not cfgp.is_file():
        die(f"找不到設定 {cfgp}")
    cfg = load_cfg(cfgp)
    if cfg.get("schema") != "pgp-assets/1":
        die("設定 schema 必須是 pgp-assets/1")
    sets = dict(s.split("=", 1) for s in a.set if "=" in s)
    bundles = cfg.get("bundles") or {}
    img, aud = cfg.get("image") or {}, cfg.get("audio") or {}
    with tempfile.TemporaryDirectory() as td:
        src = Sources(cfg, cfgp.parent, sets, pathlib.Path(td))
        missing, aliases = [], set()
        plan = []
        for bname, b in bundles.items():
            for kind in ("images", "sounds"):
                for alias, spec in (b.get(kind) or {}).items():
                    spec = spec if isinstance(spec, dict) else {"src": spec}
                    if alias in aliases:
                        die(f"別名重複：{alias}")
                    aliases.add(alias)
                    p = src.find(spec["src"])
                    if p is None:
                        missing.append(f"{bname}/{alias} ← {spec['src']}")
                    plan.append((bname, kind, alias, spec, p))
        if src.missing_roots or missing:
            die("素材來源不齊", 1, missing_roots=src.missing_roots, missing=missing[:50])
        if a.only_check:
            print(json.dumps({"ok": True, "assets": len(plan), "bundles": list(bundles)}, ensure_ascii=False))
            return
        if not a.out:
            die("需要 --out")
        out = pathlib.Path(a.out).resolve() / "assets"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        warn: list[str] = []
        svg = SvgRenderer(a.svg_engine)
        svg.prefetch([(p, float(spec.get("scale", img.get("scale", 1.0)))) for _, k, _, spec, p in plan if k == "images" and p.suffix == ".svg"], pathlib.Path(td))
        man: dict = {"bundles": [], "sounds": [], "meta": {"schema": "pgp-assets-manifest/1", "game_key": cfg.get("game_key"), "version": cfg.get("version")}}
        by_b: dict[str, list] = {b: [] for b in bundles}
        stats: dict[str, dict] = {b: {"files": 0, "bytes": 0} for b in bundles}
        for bname, kind, alias, spec, p in plan:
            (out / bname).mkdir(exist_ok=True)
            if kind == "images":
                data = render_image(p, spec, img, svg)
                name = f"{bname}/{alias}.{h8(data)}.webp"
                (out / name).write_bytes(data)
                by_b[bname].append({"alias": alias, "src": name})
                stats[bname]["files"] += 1
                stats[bname]["bytes"] += len(data)
            else:
                srcs = []
                for fmt, data in audio_variants(p, list(aud.get("formats", ["ogg"])), warn):
                    name = f"{bname}/{alias}.{h8(data)}.{fmt}"
                    (out / name).write_bytes(data)
                    srcs.append(name)
                    stats[bname]["files"] += 1
                    stats[bname]["bytes"] += len(data)
                man["sounds"].append({"alias": alias, "bundle": bname, "src": srcs, "volume": spec.get("volume", 1)})
        man["bundles"] = [{"name": b, "assets": by_b[b]} for b in bundles if by_b[b]]
        man["meta"]["required"] = [b for b, v in bundles.items() if v.get("required")]
        (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        rb = {b: {"required": bool(v.get("required")), "include": [f"{b}/**"]} for b, v in bundles.items()}
        rbp = pathlib.Path(td) / "release-bundles.json"
        rbp.write_text(json.dumps(rb), encoding="utf-8")
        rel = out / "release.json"
        r = subprocess.run([sys.executable, str(SCRIPTS / "wg_release.py"), "pack", "--dir", str(out), "--bundles", str(rbp),
                            "--game-id", str(cfg.get("game_id", cfg.get("game_key"))), "--game-key", str(cfg.get("game_key")),
                            "--version", str(cfg.get("version", "0.0.0")), "--out", str(rel)], capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            die("wg_release pack 失敗", 1, detail=r.stdout[-800:] + r.stderr[-800:])
        v = subprocess.run([sys.executable, str(SCRIPTS / "wg_release.py"), "verify", "--dir", str(out), "--release", str(rel)],
                           capture_output=True, text=True, encoding="utf-8")
        if v.returncode != 0:
            die("wg_release verify 失敗", 1, detail=v.stdout[-800:])
        total = sum(s["bytes"] for s in stats.values())
        print(json.dumps({"ok": True, "out": str(out), "assets": len(plan), "bundles": stats, "totalBytes": total,
                          "requiredBytes": sum(stats[b]["bytes"] for b in man["meta"]["required"]), "svgEngine": svg.engine, "warnings": warn[:20]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
