"""GrowthDetector — 偵測重複 codegen 模式，建議轉為 Skill。"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_PATTERNS_PATH = Path("data/growth_patterns.json")
_THRESHOLD = 2  # 同一模式出現 N 次後建議


class GrowthDetector:
    """追蹤 codegen 回覆，偵測重複模式。"""

    def __init__(self) -> None:
        self._patterns: dict[str, dict] = {}  # hash → {count, prompt, code_snippet}
        self._load()

    def _load(self) -> None:
        if _PATTERNS_PATH.exists():
            try:
                self._patterns = json.loads(_PATTERNS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save(self) -> None:
        _PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATTERNS_PATH.write_text(json.dumps(self._patterns, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, prompt: str, code: str) -> bool:
        """記錄一次 codegen。回傳 True 表示達到建議閾值。"""
        h = self._hash(prompt)
        if h not in self._patterns:
            self._patterns[h] = {"count": 0, "prompt": prompt[:100], "code_snippet": code[:200]}
        self._patterns[h]["count"] += 1
        self._save()
        return self._patterns[h]["count"] == _THRESHOLD

    def get_suggestion(self, prompt: str) -> dict | None:
        """若達到閾值回傳建議資訊，否則 None。"""
        h = self._hash(prompt)
        p = self._patterns.get(h)
        if p and p["count"] >= _THRESHOLD:
            return {"hash": h, "prompt": p["prompt"], "count": p["count"]}
        return None

    def clear(self, prompt_hash: str) -> None:
        """使用者確認轉 Skill 後清除該模式。"""
        self._patterns.pop(prompt_hash, None)
        self._save()

    @staticmethod
    def _hash(prompt: str) -> str:
        """取 prompt 前 200 字的 SHA256 前 8 碼。"""
        return hashlib.sha256(prompt[:200].encode()).hexdigest()[:8]
