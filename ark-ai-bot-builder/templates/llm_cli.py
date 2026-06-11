"""llm_cli — Agent CLI 大腦（Gemini/Kiro/Claude fallback chain）。"""
import asyncio
import json
import os
import re
import shutil
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

# ── Kiro Session 管理（per-user，跨呼叫保持，1h TTL） ──
_kiro_sessions: dict[int, tuple[str, float]] = {}  # user_id → (session_id, last_used_ts)
_user_locks: dict[int, asyncio.Lock] = {}  # per-user 並發鎖
_SESSION_TTL = 3600  # 1 小時


def _get_session(user_id: int) -> str:
    """取得 user session，過期則回傳空字串。"""
    import time
    entry = _kiro_sessions.get(user_id)
    if not entry:
        return ""
    sid, ts = entry
    if time.time() - ts > _SESSION_TTL:
        _kiro_sessions.pop(user_id, None)
        return ""
    return sid


def _set_session(user_id: int, sid: str) -> None:
    """設定 user session（更新時間戳）。"""
    import time
    _kiro_sessions[user_id] = (sid, time.time())
    # 順便清理過期 entries
    now = time.time()
    expired = [uid for uid, (_, ts) in _kiro_sessions.items() if now - ts > _SESSION_TTL]
    for uid in expired:
        _kiro_sessions.pop(uid, None)
        _user_locks.pop(uid, None)


def _get_user_lock(user_id: int) -> asyncio.Lock:
    """取得或建立 per-user lock。"""
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


class LlmCliParams(SkillParam):
    """llm_cli 輸入參數。"""
    prompt: str
    mode: str = "chat"           # chat / codegen / evaluate / skill_gen
    model: str = "auto"
    timeout: int = 180
    backend: str = ""            # gemini / kiro / claude（空=自動偵測）
    output_path: str = ""
    skill_id: str = ""
    user_id: int = 0             # per-user session 識別


class LlmCliSkill(BaseSkill):
    """Agent CLI 大腦 — 自然語言對話、CodeGen、Skill 產出。"""

    skill_id = "llm_cli"
    skill_type = SkillType.LLM
    description = "Agent CLI 對話（Gemini/Kiro/Claude fallback chain）"
    version = "2.1.0"
    input_schema = LlmCliParams

    # 後端設定
    BACKENDS = {
        "gemini": {
            "cmd_env": "GEMINI_CLI_CMD",
            "cmd_default": "gemini.cmd" if os.name == "nt" else "gemini",
            "args": lambda p, m, sid: ["-p", p, "-m", m, "--skip-trust"],
        },
        "kiro": {
            "cmd_env": "KIRO_CLI_CMD",
            "cmd_default": "kiro-cli",
            "args": lambda p, m, sid: (
                ["chat", "--no-interactive", "-a", "--wrap", "never"]
                + (["--resume-id", sid] if sid else [])
                + (["--model", m] if m != "auto" else [])
                + [p]
            ),
        },
        "claude": {
            "cmd_env": "CLAUDE_CLI_CMD",
            "cmd_default": "claude",
            "args": lambda p, m, sid: ["-p", p, "--model", m],
        },
    }

    @classmethod
    def is_available(cls, backend: str) -> bool:
        """檢查指定 CLI 是否已安裝。"""
        cfg = cls.BACKENDS.get(backend)
        if not cfg:
            return False
        cmd = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        return shutil.which(cmd) is not None

    async def execute(self, params: dict) -> SkillResult:
        """執行 Agent CLI Skill。"""
        try:
            on_progress = params.pop("on_progress", None)
            p = LlmCliParams(**params)
            if p.mode == "chat":
                return await self._chat(p, on_progress)
            elif p.mode == "codegen":
                return await self._codegen(p)
            elif p.mode == "evaluate":
                return await self._evaluate(p)
            elif p.mode == "skill_gen":
                return await self._skill_gen(p)
            else:
                return SkillResult(success=False, error=f"不支援模式: {p.mode}")
        except asyncio.TimeoutError:
            return SkillResult(success=False, error=f"CLI 超時（{params.get('timeout', 180)}s）")
        except Exception as e:
            return SkillResult(success=False, error=f"llm_cli 錯誤: {e}")

    def _resolve_backend(self, preferred: str) -> str:
        """Fallback chain: preferred → gemini → kiro → claude。"""
        if preferred and self.is_available(preferred):
            return preferred
        for b in ("gemini", "kiro", "claude"):
            if self.is_available(b):
                return b
        return "gemini"

    async def _run_cli(self, prompt: str, model: str, timeout: int, backend: str, user_id: int = 0) -> tuple:
        """執行 CLI subprocess，回傳 (stdout, stderr, returncode)。per-user 互斥。"""
        resolved = self._resolve_backend(backend)
        cfg = self.BACKENDS.get(resolved)
        if not cfg:
            return ("", f"不支援後端: {resolved}", 1)

        cmd_path = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        sid = _get_session(user_id) if resolved == "kiro" else ""
        args = cfg["args"](prompt, model, sid)

        import subprocess as _sp
        cmd_str = _sp.list2cmdline([cmd_path] + args)
        cwd = os.getenv("AI_BOT_WORKSPACE", str(Path.home()))

        lock = _get_user_lock(user_id) if user_id else asyncio.Lock()
        async with lock:
            process = None
            try:
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                out = stdout.decode("utf-8").strip() if stdout else ""
                err = stderr.decode("utf-8").strip() if stderr else ""

                if resolved == "kiro" and out and user_id and not _get_session(user_id):
                    new_sid = await self._get_latest_session()
                    if new_sid:
                        _set_session(user_id, new_sid)

                return (out, err, process.returncode or 0)
            except asyncio.TimeoutError:
                if process:
                    try:
                        process.kill()
                        await process.wait()
                    except Exception:
                        pass
                return ("", f"超時（{timeout}s）", 124)
            except FileNotFoundError:
                return ("", f"{cmd_path} 未安裝", 127)

    async def _get_latest_session(self) -> str:
        """取得 kiro-cli 最近的 session ID。"""
        try:
            cmd_path = os.getenv("KIRO_CLI_CMD", "kiro-cli")
            cwd = os.getenv("AI_BOT_WORKSPACE", str(Path.home()))
            process = await asyncio.create_subprocess_shell(
                f"{cmd_path} chat --list-sessions --format json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            if stdout:
                data = json.loads(stdout.decode("utf-8"))
                if isinstance(data, list) and data:
                    return data[0].get("id", "")
        except Exception:
            pass
        return ""

    async def _chat(self, p: LlmCliParams, on_progress=None) -> SkillResult:
        """對話模式（支援 per-user session resume + 串流進度）。"""
        prompt = f"直接回答，不要自我介紹：{p.prompt}"
        resolved = self._resolve_backend(p.backend)
        out, err, code = await self._run_cli_streaming(
            prompt, p.model, p.timeout, p.backend, p.user_id, on_progress,
        )

        if out:
            cleaned = self._clean_output(out)
            return SkillResult(success=True, data={"output": cleaned, "backend": resolved})

        return SkillResult(success=False, error=f"Agent CLI 失敗 (code {code}): {err[:300]}")

    async def _run_cli_streaming(
        self, prompt: str, model: str, timeout: int, backend: str,
        user_id: int = 0, on_progress=None,
    ) -> tuple:
        """readline 模式執行 CLI，逐行觸發 on_progress callback。"""
        resolved = self._resolve_backend(backend)
        cfg = self.BACKENDS.get(resolved)
        if not cfg:
            return ("", f"不支援後端: {resolved}", 1)

        cmd_path = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        sid = _get_session(user_id) if resolved == "kiro" else ""
        args = cfg["args"](prompt, model, sid)

        import subprocess as _sp
        cmd_str = _sp.list2cmdline([cmd_path] + args)
        cwd = os.getenv("AI_BOT_WORKSPACE", str(Path.home()))

        lock = _get_user_lock(user_id) if user_id else asyncio.Lock()
        async with lock:
            process = None
            lines: list[str] = []
            try:
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )

                async def _read_lines():
                    while process.stdout:
                        raw = await process.stdout.readline()
                        if not raw:
                            break
                        line = raw.decode("utf-8", errors="ignore").rstrip()
                        if line:
                            lines.append(line)
                            if on_progress:
                                stage = self._classify_stage(line)
                                await on_progress(stage, line)

                await asyncio.wait_for(_read_lines(), timeout=timeout)
                await process.wait()

                out = "\n".join(lines)
                err_bytes = await process.stderr.read() if process.stderr else b""
                err = err_bytes.decode("utf-8", errors="ignore").strip()

                if resolved == "kiro" and out and user_id and not _get_session(user_id):
                    new_sid = await self._get_latest_session()
                    if new_sid:
                        _set_session(user_id, new_sid)

                return (out, err, process.returncode or 0)
            except asyncio.TimeoutError:
                if process:
                    try:
                        process.kill()
                        await process.wait()
                    except Exception:
                        pass
                out = "\n".join(lines)
                if out:
                    return (out, "", 0)
                return ("", f"超時（{timeout}s）", 124)
            except FileNotFoundError:
                return ("", f"{cmd_path} 未安裝", 127)

    @staticmethod
    def _classify_stage(line: str) -> str:
        """從 stdout 行內容推測當前階段。"""
        lower = line.lower()
        if any(k in lower for k in ("search", "grep", "find", "looking", "reading file")):
            return "🔍 搜尋相關資料..."
        if any(k in lower for k in ("reading", "analyzing", "parsing", "read")):
            return "📖 閱讀分析中..."
        if any(k in lower for k in ("writing", "creating", "generating", "```")):
            return "✍️ 撰寫回答中..."
        if any(k in lower for k in ("running", "executing", "testing")):
            return "⚙️ 執行驗證中..."
        return "🤖 處理中..."

    async def _codegen(self, p: LlmCliParams) -> SkillResult:
        """程式碼產出模式。"""
        prompt = f"只輸出程式碼，不要解釋。需求：{p.prompt}"
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend, p.user_id)
        if code != 0 and not out:
            return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
        source = self._extract_code(out)
        if p.output_path:
            Path(p.output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(p.output_path).write_text(source, encoding="utf-8")
        return SkillResult(success=True, data={"code": source, "path": p.output_path})

    async def _evaluate(self, p: LlmCliParams) -> SkillResult:
        """意圖評估模式（回傳 JSON）。"""
        prompt = (
            f'分析意圖，回傳純 JSON：{{"action":"answer|invoke|generate","skill_id":"..."}}\n'
            f"用戶：{p.prompt}\n只回傳 JSON。"
        )
        out, _, code = await self._run_cli(prompt, p.model, min(p.timeout, 30), p.backend, p.user_id)
        parsed = self._extract_json(out)
        return SkillResult(success=True, data=parsed or {"action": "answer", "raw": out})

    async def _skill_gen(self, p: LlmCliParams) -> SkillResult:
        """Skill 產出模式。"""
        sid = p.skill_id or "generated_skill"
        prompt = (
            f"產出 Python Skill，繼承 BaseSkill（from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType），"
            f'skill_id="{sid}"，實作 async def execute(self, params: dict) -> SkillResult。'
            f"\n需求：{p.prompt}\n只輸出程式碼。"
        )
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend, p.user_id)
        if code != 0 and not out:
            return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
        source = self._extract_code(out)
        path = p.output_path or f"src/skills/internal/{sid}.py"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(source, encoding="utf-8")
        return SkillResult(success=True, data={"skill_id": sid, "path": path, "code": source})

    @staticmethod
    def _extract_code(output: str) -> str:
        match = re.search(r"```(?:python)?\n(.*?)```", output, re.DOTALL)
        return match.group(1).strip() if match else output

    @staticmethod
    def _extract_json(output: str) -> dict:
        match = re.search(r"\{.*\}", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _clean_output(output: str) -> str:
        """清理 kiro-cli stdout，提取最終回答。"""
        from src.bot.output_parser import parse
        return parse(output)
