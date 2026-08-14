"""標準 logging 設定 — 統一格式、分級輸出。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_dir: str | Path = "logs",
    app_name: str = "agent",
) -> None:
    """初始化標準 logging 配置。

    - Console: 彩色精簡格式
    - File: 完整時間戳 + 模組名（存到 log_dir/app.log）

    Args:
        level: 日誌等級（DEBUG/INFO/WARNING/ERROR）
        log_dir: 日誌目錄
        app_name: 應用名稱（用於日誌檔命名）
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有 handler（避免重複）
    root.handlers.clear()

    # ── Console Handler ──
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "%(asctime)s │ %(levelname)-5s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    console.setFormatter(console_fmt)
    root.addHandler(console)

    # ── File Handler ──
    file_handler = logging.FileHandler(
        log_path / f"{app_name}.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    # 降低第三方套件噪音
    for noisy in ("httpx", "httpcore", "telegram", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
