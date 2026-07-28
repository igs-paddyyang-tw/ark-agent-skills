"""Checkpoint — 進度持久化。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

CHECKPOINT_DIR = Path("data")


@dataclass
class Progress:
    """執行進度。"""
    plan_name: str
    completed: dict[str, str] = field(default_factory=dict)  # task_id → "pass"|"fail"
    started_at: str = ""
    last_updated: str = ""


def _checkpoint_path(plan_name: str) -> Path:
    return CHECKPOINT_DIR / f"{plan_name}-progress.json"


def load_progress(plan_name: str) -> Progress | None:
    """載入 checkpoint。"""
    path = _checkpoint_path(plan_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Progress(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def save_progress(progress: Progress) -> None:
    """儲存 checkpoint。"""
    progress.last_updated = datetime.now(timezone.utc).isoformat()
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(progress.plan_name)
    path.write_text(json.dumps(asdict(progress), ensure_ascii=False, indent=2), encoding="utf-8")


def clear_progress(plan_name: str) -> None:
    """清除 checkpoint。"""
    path = _checkpoint_path(plan_name)
    if path.exists():
        path.unlink()
