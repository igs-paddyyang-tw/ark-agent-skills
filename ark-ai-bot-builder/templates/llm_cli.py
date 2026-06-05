"""llm_cli — Agent CLI 大腦（Gemini/Kiro/Claude fallback chain）。"""
import asyncio
import json
import os
import re
import shutil
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class LlmCliParams(SkillParam):
    """llm_cli 輸入參數。"""
    prompt: str
    mode: str = "chat"           # chat / codegen / evaluate / skill_gen
    model: str = "gemini-2.5-flash"
    timeout: int = 120
    backend: str = ""            # gemini / kiro / claude（空=自動偵測）
    output_path: str = ""
    skill_id: str = ""


class LlmCliSkill(BaseSkill):
    """Agent CLI 大腦 — 自然語言對話、CodeGen、Skill 產出。"""

    skill_id = "llm_cli"
    skill_type = SkillType.LLM
    description = "Agent CLI 對話（Gemini/Kiro/Claude fallback chain）"
    version = "2.0.0"
    input_schema = LlmCliParams

    # 後端設定：每個 CLI 的指令格式
    BACKENDS: dict[str, dict] = {
        "gemini": {
            "cmd_env": "GEMINI_CLI_CMD",
            "cmd_default": "gemini.cmd" if os.name == "nt" else "gemini",
            "args": lambda p, m: ["-p", p, "-m", m, "--skip-trust"],
        },
        "kiro": {
            "cmd_env": "KIRO_CLI_CMD",
            "cmd_default": "kiro-cli",
            "args": lambda p, m: ["chat", "--no-interactive", "-a", "--legacy-ui", "--model", m, p],
        },
        "claude": {
            "cmd_env": "CLAUDE_CLI_CMD",
            "cmd_default": "claude",
            "args": lambda p, m: ["-p", p, "--model", m],
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
            p = LlmCliParams(**params)
            match p.mode:
                case "chat":      return await self._chat(p)
                case "codegen":   return await self._codegen(p)
                case "evaluate":  return await self._evaluate(p)
                case "skill_gen": return await self._skill_gen(p)
                case _:           return SkillResult(success=False, error=f"不支援模式: {p.mode}")
        except asyncio.TimeoutError:
            return SkillResult(success=False, error=f"CLI 超時（{params.get('timeout', 120)}s）")
        except Exception as e:
            return SkillResult(success=False, error=f"llm_cli 錯誤: {e}")

    def _resolve_backend(self, preferred: str) -> str:
        """Fallback chain: preferred → gemini → kiro → claude。"""
        if preferred and self.is_available(preferred):
            return preferred
        for b in ("gemini", "kiro", "claude"):
            if self.is_available(b):
                return b
        return "gemini"  # 最後嘗試（可能失敗）

    async def _run_cli(self, prompt: str, model: str, timeout: int, backend: str) -> tuple[str, str, int]:
        """執行 CLI subprocess，回傳 (stdout, stderr, returncode)。"""
        resolved = self._resolve_backend(backend)
        cfg = self.BACKENDS.get(resolved)
        if not cfg:
            return ("", f"不支援後端: {resolved}", 1)

        cmd_path = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        args = cfg["args"](prompt, model)

        # Windows .cmd 必須用 shell 模式
        import subprocess as _sp
        cmd_str = _sp.list2cmdline([cmd_path] + args)
        cwd = os.getenv("AI_BOT_WORKSPACE", str(Path(__file__).resolve().parents[3]))

        try:
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return (
                stdout.decode("utf-8").strip() if stdout else "",
                stderr.decode("utf-8").strip() if stderr else "",
                process.returncode or 0,
            )
        except asyncio.TimeoutError:
            return ("", f"超時（{timeout}s）", 124)
        except FileNotFoundError:
            return ("", f"{cmd_path} 未安裝", 127)

    async def _chat(self, p: LlmCliParams) -> SkillResult:
        """對話模式。"""
        prompt = f"直接回答，不要自我介紹：{p.prompt}"
        resolved = self._resolve_backend(p.backend)
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)

        # 有 stdout 就視為成功（CLI stderr 警告不算失敗）
        if out:
            cleaned = self._clean_output(out)
            return SkillResult(success=True, data={"output": cleaned, "backend": resolved})

        # CLI 全部失敗 → fallback 到 Gemini API
        fallback = await self._gemini_api_fallback(p.prompt)
        if fallback:
            return SkillResult(success=True, data={"output": fallback, "backend": "gemini-api"})

        return SkillResult(success=False, error=f"CLI 失敗 (code {code}): {err[:300]}")

    async def _codegen(self, p: LlmCliParams) -> SkillResult:
        """程式碼產出模式。"""
        prompt = f"只輸出程式碼，不要解釋。需求：{p.prompt}"
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
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
        out, _, code = await self._run_cli(prompt, p.model, min(p.timeout, 30), p.backend)
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
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if code != 0 and not out:
            return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
        source = self._extract_code(out)
        path = p.output_path or f"src/skills/internal/{sid}.py"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(source, encoding="utf-8")
        return SkillResult(success=True, data={"skill_id": sid, "path": path, "code": source})

    async def _gemini_api_fallback(self, prompt: str) -> str:
        """CLI 全部不可用時，fallback 到 Gemini API。"""
        try:
            from src.llm.gemini_chat import chat, is_available
            if is_available():
                return await chat(prompt)
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_code(output: str) -> str:
        """從 CLI 輸出提取程式碼區塊。"""
        match = re.search(r"```(?:python)?\n(.*?)```", output, re.DOTALL)
        return match.group(1).strip() if match else output

    @staticmethod
    def _extract_json(output: str) -> dict:
        """從 CLI 輸出提取 JSON。"""
        match = re.search(r"\{.*\}", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _clean_output(output: str) -> str:
        """清理 CLI 輸出（移除 ANSI 色碼 + kiro "> " 前綴）。"""
        # ANSI escape codes
        cleaned = re.sub(r"\x1b\[[0-9;]*m", "", output)
        # kiro-cli --legacy-ui 的 "> " 前綴
        lines = cleaned.splitlines()
        lines = [line[2:] if line.startswith("> ") else line for line in lines]
        return "\n".join(lines).strip()
