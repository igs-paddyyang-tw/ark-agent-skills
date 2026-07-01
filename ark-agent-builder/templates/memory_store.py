"""MemoryStore — per-user YAML 偏好記憶。"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

_MEMORY_DIR = Path("data/memory")
_DEFAULT_PROFILE = {
    "language": "",
    "role": "",
    "style": "",
    "tech_stack": [],
    "常用功能": [],
    "active_hours": "",
    "備註": "",
}


class MemoryStore:
    """per-user YAML 記憶讀寫。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or _MEMORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: int) -> Path:
        return self._dir / f"{user_id}.yaml"

    def load(self, user_id: int) -> dict:
        """載入使用者 profile，不存在回傳空 dict。"""
        p = self._path(user_id)
        if not p.exists():
            return {}
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save(self, user_id: int, profile: dict) -> None:
        """完整覆寫 profile。"""
        profile["updated"] = datetime.now().strftime("%Y-%m-%d")
        self._path(user_id).write_text(
            yaml.dump(profile, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def update(self, user_id: int, key: str, value) -> None:
        """更新單一欄位。"""
        profile = self.load(user_id)
        profile[key] = value
        self.save(user_id, profile)

    def get_context_str(self, user_id: int) -> str:
        """回傳可注入 system prompt 的偏好摘要（排除 30 天未更新的 stale 記憶）。"""
        profile = self.load(user_id)
        if not profile:
            return ""
        # 衰減：超過 30 天未更新的整個 profile 視為 stale
        from datetime import datetime, timedelta
        updated = profile.get("updated", "")
        if updated:
            try:
                last = datetime.strptime(updated, "%Y-%m-%d")
                if datetime.now() - last > timedelta(days=30):
                    return ""  # 整個 profile stale
            except Exception:
                pass
        lines = []
        for k, v in profile.items():
            if k == "updated" or not v:
                continue
            if isinstance(v, list):
                lines.append(f"- {k}: {', '.join(str(x) for x in v)}")
            else:
                lines.append(f"- {k}: {v}")
        return "\n".join(lines)
