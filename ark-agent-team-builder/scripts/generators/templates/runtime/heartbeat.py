"""Heartbeat — daemon 每 30 秒寫 timestamp，外部 watchdog 偵測凍結。"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30
HEARTBEAT_FILE = "heartbeat"


async def heartbeat_loop(state_dir: Path) -> None:
    """背景 task — 每 30 秒寫入 unix timestamp。"""
    hb_path = state_dir / HEARTBEAT_FILE
    state_dir.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            hb_path.write_text(str(int(time.time())), encoding="utf-8")
        except OSError:
            pass
        await asyncio.sleep(HEARTBEAT_INTERVAL)


def is_heartbeat_stale(state_dir: Path, max_age_s: int = 90) -> bool:
    """檢查 heartbeat 是否過期（>max_age_s 秒）。"""
    hb_path = state_dir / HEARTBEAT_FILE
    if not hb_path.exists():
        return True
    try:
        ts = int(hb_path.read_text(encoding="utf-8").strip())
        return (time.time() - ts) > max_age_s
    except (ValueError, OSError):
        return True
