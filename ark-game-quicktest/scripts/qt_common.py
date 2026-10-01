"""qt_common — ark-game-quicktest 共用：envelope、路徑、yaml、sha。不呼叫 LLM。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

CONTRACT = "1"
SKILL_VERSION = "1.1.0"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "QUERY_FAILED": 6, "MISSING_DEP": 8}
HERE = pathlib.Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
MD_REPORT = SKILL_DIR.parent / "ark-md-report" / "scripts"

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
