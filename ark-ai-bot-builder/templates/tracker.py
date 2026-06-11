"""SkillTracker — Skill 執行統計 + 自我改進觸發。"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_STATS_PATH = Path("data/skill_stats.json")
_FAIL_THRESHOLD = 0.3
_CONSECUTIVE_FAIL_LIMIT = 3


@dataclass
class SkillStats:
    skill_id: str
    total: int = 0
    success: int = 0
    fail: int = 0
    consecutive_fails: int = 0
    total_duration: float = 0.0
    last_error: str = ""
    evolved_count: int = 0

    def needs_evolution(self) -> bool:
        if self.total < 3:
            return False
        if self.consecutive_fails >= _CONSECUTIVE_FAIL_LIMIT:
            return True
        fail_rate = self.fail / self.total if self.total else 0
        return fail_rate > _FAIL_THRESHOLD and self.consecutive_fails > 0


class SkillTracker:
    """Skill 執行統計追蹤器。"""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _STATS_PATH
        self._stats: dict[str, SkillStats] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for sid, d in data.items():
                    self._stats[sid] = SkillStats(**d)
            except Exception:
                pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {sid: asdict(s) for sid, s in self._stats.items()}
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, skill_id: str, success: bool, duration: float, error: str = "") -> None:
        s = self._stats.setdefault(skill_id, SkillStats(skill_id=skill_id))
        s.total += 1
        s.total_duration += duration
        if success:
            s.success += 1
            s.consecutive_fails = 0
        else:
            s.fail += 1
            s.consecutive_fails += 1
            s.last_error = error[:200]
        self._save()

    def get(self, skill_id: str) -> SkillStats | None:
        return self._stats.get(skill_id)

    def get_evolution_candidates(self) -> list[SkillStats]:
        return [s for s in self._stats.values() if s.needs_evolution()]

    def mark_evolved(self, skill_id: str) -> None:
        s = self._stats.get(skill_id)
        if s:
            s.evolved_count += 1
            s.consecutive_fails = 0
            self._save()

    def summary(self) -> list[dict]:
        """回傳所有 Skill 統計摘要。"""
        return [
            {"id": s.skill_id, "total": s.total, "success_rate": round(s.success / s.total * 100, 1) if s.total else 0, "avg_ms": round(s.total_duration / s.total * 1000) if s.total else 0}
            for s in sorted(self._stats.values(), key=lambda x: x.total, reverse=True)
        ]
