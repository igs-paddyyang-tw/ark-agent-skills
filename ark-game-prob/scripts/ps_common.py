"""ps_common — ark-game-prob 共用：envelope、路徑、yaml、sha。不呼叫 LLM。"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys

CONTRACT = "1"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "QUERY_FAILED": 6, "MISSING_DEP": 8}
HERE = pathlib.Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
MD_REPORT = SKILL_DIR.parent / "ark-md-report" / "scripts"


def _skill_version() -> str:
    """從 SKILL.md frontmatter 讀 version（不再寫死）。"""
    try:
        for line in (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").splitlines()[:40]:
            m = re.match(r'\s*version:\s*"?([0-9][^"\s]*)"?', line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "0.0.0"


SKILL_VERSION = _skill_version()

LEGACY_OUT = "data/prob"  # ARK_GAME_ROOT 未設時的舊預設（相容一版，G-2）


def game_root() -> pathlib.Path | None:
    """G-2：環境變數 ARK_GAME_ROOT（例 data/slot）→ 一款遊戲的家 = <root>/<slug>/；未設回 None。"""
    v = os.environ.get("ARK_GAME_ROOT", "").strip()
    return pathlib.Path(v) if v else None


def slug_of(p: pathlib.Path) -> str:
    """從目錄推 slug：`<game>/quicktest`、`<game>/prob` 這類規範子目錄取上一層名，其餘取本身名。"""
    p = pathlib.Path(p)
    return p.parent.name if p.name in ("quicktest", "prob", "spec") else p.name


def resolve_out(out: str | None, dest: str | None, slug: str) -> tuple[pathlib.Path, bool]:
    """決定 prob 產物落點，回 (目錄, 是否 dest 落法)。
    優先序：--dest > --out（<out>/<slug>）> ARK_GAME_ROOT（<root>/<slug>/prob）> 舊預設 data/prob/<slug>。"""
    if dest:
        return pathlib.Path(dest), True
    if not out and (root := game_root()):
        return root / slug / "prob", True
    base = pathlib.Path(out or LEGACY_OUT)
    return (base if base.name == slug else base / slug), False


PCT_RE = re.compile(r"^-?\d+(?:\.\d+)?%$")


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def emit(data, meta=None) -> None:
    _utf8()
    print(json.dumps({"success": True, "contract": CONTRACT, "data": data, "meta": {"skill_version": SKILL_VERSION, **(meta or {})}}, ensure_ascii=False))


def fail(code: str, message: str, hint: str = "", data=None) -> None:
    _utf8()
    print(json.dumps({"success": False, "contract": CONTRACT, "error": {"code": code, "message": message, "hint": hint}, "data": data}, ensure_ascii=False))
    sys.exit(EXIT.get(code, 1))


def yaml_load(p: pathlib.Path):
    try:
        import yaml  # type: ignore
    except ImportError:
        fail("MISSING_DEP", "需要 pyyaml")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def yaml_dump(o) -> str:
    import yaml  # type: ignore
    return yaml.safe_dump(o, allow_unicode=True, sort_keys=False, width=200)


def sha16(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def num(s: str):
    """'59.4492%' → 0.594492；'101.76' → 101.76；'-' / 'NaN%' / '+Inf' → None。"""
    s = (s or "").strip()
    if s in ("", "-", "—", "NaN", "NaN%", "+Inf", "Inf", "-Inf"):
        return None
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None
