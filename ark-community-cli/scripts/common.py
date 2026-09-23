"""common.py — ark-community-cli 共用工具：config、路徑、假名化、JSONL、PII 掃描、時間。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))
SNOWFLAKE_RE = re.compile(r"(?<!\d)\d{17,19}(?!\d)")
DISCORD_EPOCH_MS = 1420070400000


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError:
        sys.exit("需要 PyYAML：pip install pyyaml")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def dump_yaml(data: dict) -> str:
    import yaml  # type: ignore
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


class Ctx:
    """把 config 與目錄綁在一起，所有腳本共用。"""

    def __init__(self, config_path: Path):
        self.config_path = config_path.resolve()
        self.cfg = load_yaml(self.config_path)
        root = self.cfg.get("root", ".")
        self.root = (self.config_path.parent / root).resolve() if not Path(root).is_absolute() else Path(root)
        for d in ("state/discord", "state/x", "raw/discord", "raw/x", "records", "classify",
                  "cases", "reports/weekly", "reports/decisions"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        salt = self.cfg.get("pseudonym_salt", "")
        if not salt or "REPLACE" in salt:
            sys.exit("config.pseudonym_salt 未設定：跑 `community_cli.py init` 或手動填 32 bytes hex")
        self._salt = salt.encode()

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def pseudonym(self, raw_id: str) -> str:
        return hmac.new(self._salt, str(raw_id).encode(), hashlib.sha256).hexdigest()[:16]

    def env_token(self, section: str) -> str:
        var = self.cfg.get(section, {}).get("token_env", "")
        tok = os.environ.get(var, "")
        if not tok:
            sys.exit(f"環境變數 {var} 未設定（{section} token）。token 不放 config，只放環境變數。")
        return tok

    def lexicon(self) -> dict:
        p = Path(self.cfg.get("classify", {}).get("lexicon", "assets/lexicon.yaml"))
        if not p.is_absolute():
            cand = self.config_path.parent / p
            p = cand if cand.exists() else SKILL_DIR / p
        return load_yaml(p)


def record_id(source: str, raw: str) -> str:
    return hashlib.sha1(f"{source}:{raw}".encode()).hexdigest()[:16]


def read_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if line:
                yield i, json.loads(line)


def append_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def iso_week(d: datetime | None = None) -> str:
    d = d or datetime.now(TZ)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_range(week: str) -> tuple[datetime, datetime]:
    """'2026-W39' → (Mon 00:00 UTC, next Mon 00:00 UTC)."""
    y, w = week.split("-W")
    start = datetime.fromisocalendar(int(y), int(w), 1).replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def parse_since(s: str) -> datetime:
    """'7d' / '36h' / ISO date → UTC datetime."""
    m = re.fullmatch(r"(\d+)([dh])", s)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return datetime.now(timezone.utc) - (timedelta(days=n) if u == "d" else timedelta(hours=n))
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def snowflake_from_time(dt: datetime) -> int:
    return (int(dt.timestamp() * 1000) - DISCORD_EPOCH_MS) << 22


def detect_lang(text: str) -> str:
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[A-Za-z]{3,}", text):
        return "en"
    return "other"


def pii_scan(path: Path, extra_words: list[str] | None = None) -> list[str]:
    """掃 records/cases/reports 是否漏 PII：17–19 位 snowflake、@username、已知 username 詞。"""
    hits: list[str] = []
    text = path.read_text(encoding="utf-8")
    for m in SNOWFLAKE_RE.finditer(text):
        hits.append(f"snowflake:{m.group(0)}")
    for m in re.finditer(r"(?<![\w/])@[A-Za-z0-9_]{4,15}\b", text):
        hits.append(f"handle:{m.group(0)}")
    for w in extra_words or []:
        if w and w in text:
            hits.append(f"username:{w}")
    return hits


def mask(text: str, patterns: dict[str, str]) -> str:
    for name, pat in (patterns or {}).items():
        try:
            text = re.sub(pat, f"[{name}]", text)
        except re.error:
            pass
    return text
