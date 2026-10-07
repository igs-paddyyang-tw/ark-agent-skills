"""md_render — 雙軌戳記（content-src）唯一實作；三套 mini-markdown 渲染器的收斂（D-9）留下一版，本檔先提供戳記與 STALE 判定。"""
from __future__ import annotations
import hashlib, pathlib, re

STAMP_RE = re.compile(r"<!-- (?:content-src|gdd-src): (\S+) sha256:([0-9a-f]{8,64}) -->")


def sha16(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def stamp(src_name: str, sha: str) -> str:
    return f"<!-- content-src: {src_name} sha256:{sha} -->"


def read_stamp(html_text: str) -> tuple[str, str] | None:
    m = STAMP_RE.search(html_text[:4000])
    return (m.group(1), m.group(2)) if m else None


def is_stale(html_path: pathlib.Path, src_path: pathlib.Path) -> bool:
    """html 戳記（content-src 或舊 gdd-src）與來源 sha 不符 → True。"""
    st = read_stamp(html_path.read_text(encoding="utf-8", errors="replace"))
    if not st:
        return True
    full = hashlib.sha256(src_path.read_bytes()).hexdigest()
    return not full.startswith(st[1])
