#!/usr/bin/env python3
"""semver.py — 最小 semver 實作（比較 + 範圍），不引第三方（ADR-001 技術棧）。

支援範圍語法:`*`（任意）、`>=x.y.z`、`<x.y.z`、`>x`、`<=x`、`==x`、`^x.y.z`（相容 major）、
`~x.y.z`（相容 minor）、以及空白分隔的交集（`>=2.0 <3`）。
"""
from __future__ import annotations

import re


def parse(v: str) -> tuple[int, int, int]:
    """'2.1' → (2,1,0);'2' → (2,0,0);非法 → (0,0,0)。"""
    s = str(v).strip().strip('"').strip("'").lstrip("vV")
    parts = re.split(r"[.\-+]", s)
    nums = []
    for p in parts[:3]:
        nums.append(int(p) if p.isdigit() else 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])  # type: ignore


def cmp(a: str, b: str) -> int:
    pa, pb = parse(a), parse(b)
    return (pa > pb) - (pa < pb)


def _satisfies_one(ver: tuple, op: str, target: str) -> bool:
    t = parse(target)
    if op == ">=":
        return ver >= t
    if op == "<=":
        return ver <= t
    if op == ">":
        return ver > t
    if op == "<":
        return ver < t
    if op in ("==", "="):
        return ver == t
    if op == "^":  # 相容 major:>= t 且 < (major+1).0.0
        return ver >= t and ver[0] == t[0]
    if op == "~":  # 相容 minor:>= t 且 major.minor 相同
        return ver >= t and ver[0] == t[0] and ver[1] == t[1]
    return False


def satisfies(version: str, spec: str) -> bool:
    """version 是否滿足範圍 spec。spec 為空/`*` → 任意。空白分隔為交集（全滿足）。"""
    spec = (spec or "").strip()
    if not spec or spec == "*":
        return True
    ver = parse(version)
    for clause in spec.split():
        m = re.match(r"^(>=|<=|==|=|>|<|\^|~)?\s*(.+)$", clause)
        if not m:
            return False
        op = m.group(1) or "=="
        if not _satisfies_one(ver, op, m.group(2)):
            return False
    return True


def is_semver(v: str) -> bool:
    return bool(re.match(r"^\d+\.\d+\.\d+$", str(v).strip().strip('"').strip("'")))
