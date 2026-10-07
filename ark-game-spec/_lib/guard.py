"""guard — 注入句型 / 隱形字元 偵測（全 skill 唯一一份；pack_lint / atlas_lint / gdd_lint 共用）。"""
from __future__ import annotations
import re

INJECTION = re.compile(r"(ignore (all |the )?(previous|above|prior) instructions|disregard (all |the )?(previous|above)|"
                       r"you are now|system prompt|請忽略(以上|之前|先前)|忽略(上述|以上)指令|系統提示|override (the )?rules)", re.I)
INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\u2028\u2029\u202a-\u202e\u2060-\u2064\ufeff]")
HTML_ACTIVE = re.compile(r"<\s*(script|iframe|object|embed)\b|\son[a-z]+\s*=", re.I)


def scan(text: str) -> list[tuple[str, int]]:
    """回傳 [(kind, line_no)]；kind ∈ injection / invisible / html。"""
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        if INJECTION.search(ln):
            out.append(("injection", i))
        if INVISIBLE.search(ln):
            out.append(("invisible", i))
        if HTML_ACTIVE.search(ln):
            out.append(("html", i))
    return out
