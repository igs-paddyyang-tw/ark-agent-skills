"""常駐進程管理 — 基於 stdin/stdout pipe 的長駐子進程包裝。

移植自 team-agent (2026-06-15 穩定版)，適配 ai-team-agent 架構。
關鍵：使用 --legacy-ui 模式，stderr 合併 stdout。
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class ManagedProcess:
    """長駐子進程包裝 — stdin/stdout 持續連接，ring buffer 收集輸出。"""

    name: str
    proc: asyncio.subprocess.Process | None = None
    _output_lines: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    _reader_task: asyncio.Task | None = None
    _pipe_broken: bool = False
    _output_count: int = 0

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc else None

    @property
    def output_count(self) -> int:
        """累計輸出行數（只增不減，用於活動偵測）。"""
        return self._output_count

    def is_alive(self) -> bool:
        """Process 是否存活。"""
        return self.proc is not None and self.proc.returncode is None

    async def start(self, cmd: str, cwd: str, *, env: dict[str, str] | None = None) -> None:
        """啟動子進程（stderr 合併到 stdout）。"""
        full_env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            **(env or {}),
        }
        self._pipe_broken = False

        if sys.platform == "win32":
            cmd_parts = self._parse_windows_cmd(cmd)
        else:
            import shlex
            cmd_parts = shlex.split(cmd)

        kwargs: dict = {
            "stdin": asyncio.subprocess.PIPE,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.STDOUT,
            "cwd": cwd,
            "env": full_env,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP

        self._output_lines.clear()
        self.proc = await asyncio.create_subprocess_exec(*cmd_parts, **kwargs)
        self._reader_task = asyncio.create_task(self._read_output())
        log.info("Process started: %s (pid=%s, cwd=%s)", self.name, self.pid, cwd)

    @staticmethod
    def _parse_windows_cmd(cmd: str) -> list[str]:
        """Parse Windows command string to list, handling quoted paths."""
        parts: list[str] = []
        current = ""
        in_quote = False
        quote_char = ""
        for ch in cmd:
            if ch in ('"', "'") and not in_quote:
                in_quote = True
                quote_char = ch
            elif ch == quote_char and in_quote:
                in_quote = False
                quote_char = ""
            elif ch == " " and not in_quote:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += ch
        if current:
            parts.append(current)
        return parts

    async def _read_output(self) -> None:
        """持續讀取 stdout（含合併的 stderr），存入 ring buffer。"""
        assert self.proc and self.proc.stdout
        try:
            while True:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                # 處理 \r 覆寫：取最後一個片段
                if "\r" in decoded:
                    decoded = decoded.split("\r")[-1]
                decoded = decoded.rstrip("\r")
                if not decoded:
                    continue
                self._output_lines.append(decoded)
                self._output_count += 1
        except (asyncio.CancelledError, OSError):
            pass

    async def send_input(self, text: str) -> None:
        """發送文字到 stdin（含 pipe 保護 + drain timeout）。"""
        if not self.proc or not self.proc.stdin:
            raise RuntimeError(f"Process {self.name} has no stdin")
        if self._pipe_broken:
            raise RuntimeError(f"Process {self.name} pipe is broken")
        text = text.replace("\n", " ").replace("\r", " ")
        data = (text + "\n").encode("utf-8", errors="replace")
        try:
            self.proc.stdin.write(data)
            await asyncio.wait_for(self.proc.stdin.drain(), timeout=10.0)
        except asyncio.TimeoutError:
            log.warning("Process %s stdin drain timeout (10s)", self.name)
            self._pipe_broken = True
            raise RuntimeError(f"Process {self.name} stdin drain timeout") from None
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            log.warning("Process %s pipe broken during send: %s", self.name, e)
            self._pipe_broken = True
            raise RuntimeError(f"Process {self.name} pipe broken: {e}") from e

    def capture(self, lines: int = 200) -> str:
        """取最近 N 行 stdout（供 health check / error detection）。"""
        recent = list(self._output_lines)[-lines:]
        return "\n".join(recent)

    async def kill(self) -> None:
        """Graceful stop: drain → terminate → kill。"""
        if self._reader_task and not self._reader_task.done():
            try:
                await asyncio.wait_for(self._reader_task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass
        elif self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._reader_task = None

        if self.proc and self.proc.returncode is None:
            try:
                self.proc.terminate()
                try:
                    await asyncio.wait_for(self.proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.proc.kill()
                    await self.proc.wait()
            except OSError:
                pass
            log.info("Process killed: %s (pid=%s)", self.name, self.pid)

        # Close transport to prevent Windows GC ResourceWarning
        if self.proc:
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                if stream:
                    try:
                        stream.close()
                    except Exception:
                        pass
            transport = getattr(self.proc, "_transport", None)
            if transport and not transport.is_closing():
                try:
                    transport.close()
                except Exception:
                    pass

        self.proc = None
        self._pipe_broken = False


# ── Registry ────────────────────────────────────────────

_active: dict[str, ManagedProcess] = {}


def register(mp: ManagedProcess) -> None:
    _active[mp.name] = mp


def unregister(name: str) -> None:
    _active.pop(name, None)


def list_active() -> list[str]:
    return [name for name, mp in _active.items() if mp.is_alive()]


def get(name: str) -> ManagedProcess | None:
    return _active.get(name)
