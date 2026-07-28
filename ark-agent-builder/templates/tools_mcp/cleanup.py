"""Output 目錄 TTL 清理 — 刪除超過 N 天的暫存檔。

用法：
  from src.tools.cleanup import cleanup_output
  deleted = cleanup_output(max_age_days=30)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "output"

# 預設保留天數
DEFAULT_MAX_AGE_DAYS = 30


def cleanup_output(max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> list[str]:
    """清理 output/ 下超過 max_age_days 的檔案。

    Returns:
        被刪除的檔案路徑列表
    """
    if not OUTPUT_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted: list[str] = []

    for category_dir in OUTPUT_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        for f in category_dir.iterdir():
            if f.name.startswith("."):
                continue
            if not f.is_file():
                continue
            # 用檔案修改時間判斷
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                rel_path = str(f.relative_to(BASE_DIR))
                f.unlink()
                deleted.append(rel_path)
                log.info("cleanup: deleted %s (age: %d days)", rel_path, (datetime.now() - mtime).days)

    if deleted:
        log.info("cleanup_output: removed %d files older than %d days", len(deleted), max_age_days)

    return deleted
