"""Kiro CLI backend — 命令建構、Ready/Error 偵測、配置寫入。

移植自 team-agent，適配 ai-team-agent 架構。
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

READY_PATTERN = re.compile(
    r"All tools are now trusted|Trust All Tools active|Credits:.*Time:"
    r"|ask a question or describe a task|ctrl-c to start chatting now|start chatting",
    re.MULTILINE,
)

ERROR_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"rate.?limit|429|too many requests", re.I), "rate_limit", "Rate limit reached"),
    (re.compile(r"auth.*error|unauthorized|401", re.I), "auth_error", "Authentication error"),
    (re.compile(r"usage limit|insufficient.?credit|credit.*exhaust", re.I), "quota", "Usage limit reached"),
    (re.compile(r"network.?error|ECONNREFUSED|ETIMEDOUT|fetch failed", re.I), "network_error", "Network error"),
    (re.compile(r"internal.?server.?error|500|service unavailable|503", re.I), "server_error", "Server error"),
    (re.compile(r"context.?length|token.?limit|too.?long", re.I), "context_overflow", "Context length exceeded"),
]

STARTUP_DIALOG = re.compile(r"No,?\s*exit", re.MULTILINE)
RUNTIME_DIALOG = re.compile(r"Do you trust the files|Yes,?\s*I accept", re.MULTILINE)

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[=>]?\S*")


def _resolve_binary() -> str:
    """找到 kiro-cli 執行檔路徑。"""
    path = shutil.which("kiro-cli")
    if path:
        return path
    import platform
    if platform.system() == "Windows":
        candidates = []
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            candidates.append(Path(local_app) / "kiro-cli" / "kiro-cli.exe")
        candidates.append(Path.home() / "AppData" / "Local" / "kiro-cli" / "kiro-cli.exe")
        username = os.environ.get("USERNAME", "")
        if username:
            for drive in ("D:", "E:", "C:"):
                candidates.append(Path(f"{drive}\\Users\\{username}\\AppData\\Local\\kiro-cli\\kiro-cli.exe"))
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    else:
        for loc in (Path.home() / ".local" / "bin" / "kiro-cli", Path("/usr/local/bin/kiro-cli")):
            if loc.exists():
                return str(loc)
    raise RuntimeError("kiro-cli not found. Install from https://kiro.dev/downloads/")


@dataclass
class KiroBackendConfig:
    """啟動配置。"""
    working_directory: str = "."
    instance_name: str = ""
    skip_resume: bool = False
    model: str | None = None


class KiroBackend:
    """Kiro CLI 啟動與偵測。"""

    def __init__(self) -> None:
        self.binary_path = _resolve_binary()

    def build_command(self, cfg: KiroBackendConfig) -> str:
        """產生啟動命令字串。"""
        cmd = f"{self.binary_path} chat --trust-all-tools --legacy-ui --require-mcp-startup"
        if not cfg.skip_resume:
            cmd += " --resume"
        if cfg.model:
            if not re.match(r"^[A-Za-z0-9._:/-]+$", cfg.model):
                raise ValueError(f"Invalid model name: {cfg.model}")
            cmd += f" --model {cfg.model}"
        return cmd

    @staticmethod
    def quit_command() -> str:
        return "/quit"

    @staticmethod
    def _strip(output: str) -> str:
        return _ANSI_RE.sub("", output)

    @staticmethod
    def is_ready(output: str) -> bool:
        """偵測 kiro-cli 是否已就緒。"""
        return bool(READY_PATTERN.search(KiroBackend._strip(output)))

    @staticmethod
    def detect_error(output: str) -> tuple[str, str] | None:
        """偵測錯誤類型，回傳 (type, message) 或 None。"""
        clean = KiroBackend._strip(output)
        for pattern, err_type, msg in ERROR_PATTERNS:
            if pattern.search(clean):
                return err_type, msg
        return None

    @staticmethod
    def has_startup_dialog(output: str) -> bool:
        return bool(STARTUP_DIALOG.search(KiroBackend._strip(output)))

    @staticmethod
    def has_runtime_dialog(output: str) -> bool:
        return bool(RUNTIME_DIALOG.search(KiroBackend._strip(output)))
