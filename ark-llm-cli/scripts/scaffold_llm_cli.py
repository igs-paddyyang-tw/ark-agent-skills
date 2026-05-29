#!/usr/bin/env python3
"""scaffold_llm_cli.py — 確定性產出 LLM CLI 封裝 Skill。

使用方式：
    python scaffold_llm_cli.py <project_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

LLM_CLI_PY = '''\
"""llm_cli — 通用 LLM CLI 封裝 Skill（Gemini/Kiro/Claude/Antigravity）。"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class LlmCliParams(SkillParam):
    """llm_cli 輸入參數。"""
    prompt: str
    mode: str = "chat"  # chat / codegen / skill_gen / evaluate
    model: str = "gemini-2.5-flash"
    system_prompt: str = ""
    timeout: int = 120
    output_path: str = ""
    skill_id: str = ""
    backend: str = ""


class LlmCliSkill(BaseSkill):
    """通用 LLM CLI 封裝。"""

    skill_id = "llm_cli"
    skill_type = SkillType.PYTHON
    description = "LLM CLI 封裝 — 對話、CodeGen、Skill 產出（Gemini/Kiro/Claude/AG）"
    version = "2.0.0"
    input_schema = LlmCliParams

    BACKENDS: dict[str, dict] = {
        "gemini": {
            "cmd_env": "GEMINI_CLI_CMD",
            "cmd_default": "gemini.cmd" if os.name == "nt" else "gemini",
            "args": lambda p, m: ["-p", p, "-m", m, "--skip-trust", "--approval-mode", "plan"],
        },
        "kiro": {
            "cmd_env": "KIRO_CLI_CMD",
            "cmd_default": "kiro-cli",
            "args": lambda p, m: ["chat", "--no-interactive", "-m", p],
        },
        "claude": {
            "cmd_env": "CLAUDE_CLI_CMD",
            "cmd_default": "claude",
            "args": lambda p, m: ["-p", p, "--model", m],
        },
        "antigravity": {
            "cmd_env": "AG_CLI_CMD",
            "cmd_default": "ag",
            "args": lambda p, m: ["ask", p, "--model", m],
        },
    }

    _available_cache: dict[str, bool] = {}

    @classmethod
    def is_available(cls, backend: str = "gemini") -> bool:
        if backend in cls._available_cache:
            return cls._available_cache[backend]
        import shutil
        cfg = cls.BACKENDS.get(backend)
        if not cfg:
            cls._available_cache[backend] = False
            return False
        cmd = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        available = shutil.which(cmd) is not None
        cls._available_cache[backend] = available
        return available

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = LlmCliParams(**params)
            if p.mode == "chat":
                return await self._chat(p)
            elif p.mode == "codegen":
                return await self._codegen(p)
            elif p.mode == "skill_gen":
                return await self._skill_gen(p)
            elif p.mode == "evaluate":
                return await self._evaluate(p)
            return SkillResult(success=False, error=f"不支援的模式: {p.mode}")
        except asyncio.TimeoutError:
            return SkillResult(success=False, error="LLM CLI 超時")
        except Exception as e:
            return SkillResult(success=False, error=f"llm_cli 錯誤: {e}")

    def _resolve_backend(self, backend: str) -> str:
        if backend and self.is_available(backend):
            return backend
        env_b = os.getenv("LLM_CLI_BACKEND", "")
        if env_b and self.is_available(env_b):
            return env_b
        for b in ("gemini", "claude", "kiro", "antigravity"):
            if self.is_available(b):
                return b
        return "gemini"

    async def _run_cli(self, prompt: str, model: str, timeout: int, backend: str = "") -> tuple[str, str, int]:
        resolved = self._resolve_backend(backend)
        cfg = self.BACKENDS.get(resolved)
        if not cfg:
            return ("", f"不支援: {resolved}", 1)

        cmd_path = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        args = cfg["args"](prompt, model)
        cmd = [cmd_path] + args

        env = os.environ.copy()
        if resolved == "gemini":
            env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"

        PROJECT_ROOT = Path(__file__).resolve().parents[3]
        cwd = os.getenv("AI_BOT_WORKSPACE", str(PROJECT_ROOT))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                stdout.decode("utf-8").strip() if stdout else "",
                stderr.decode("utf-8").strip() if stderr else "",
                proc.returncode,
            )
        except FileNotFoundError:
            return ("", f"{cmd_path} 未安裝", 127)
        except asyncio.TimeoutError:
            return ("", f"超時（{timeout}s）", 124)

    async def _chat(self, p: LlmCliParams) -> SkillResult:
        prompt = f"{p.system_prompt}\\n\\n{p.prompt}" if p.system_prompt else p.prompt
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if code != 0:
            return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
        return SkillResult(success=True, data={"output": out, "model": p.model})

    async def _codegen(self, p: LlmCliParams) -> SkillResult:
        prompt = f"只輸出程式碼，不要解釋。需求：{p.prompt}"
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if code != 0:
            return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
        source = self._extract_code(out)
        if p.output_path:
            Path(p.output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(p.output_path).write_text(source, encoding="utf-8")
        return SkillResult(success=True, data={"code": source, "path": p.output_path})

    async def _skill_gen(self, p: LlmCliParams) -> SkillResult:
        sid = p.skill_id or "generated_skill"
        prompt = (
            f"產出 Python Skill，繼承 BaseSkill（from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType）\\n"
            f"skill_id = \\"{sid}\\"\\n需求：{p.prompt}\\n只輸出程式碼。"
        )
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if code != 0:
            return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
        source = self._extract_code(out)
        output_path = p.output_path or f"src/skills/internal/{sid}.py"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(source, encoding="utf-8")
        return SkillResult(success=True, data={"skill_id": sid, "path": output_path, "code": source})

    async def _evaluate(self, p: LlmCliParams) -> SkillResult:
        prompt = (
            f"分析需求，回傳純 JSON：{{\\"action\\": \\"answer|invoke|generate\\", \\"reason\\": \\"...\\"}}\\n"
            f"需求：{p.prompt}\\n只回傳 JSON。"
        )
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if code != 0:
            return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
        parsed = self._extract_json(out)
        return SkillResult(success=True, data=parsed or {"action": "answer", "raw": out})

    @staticmethod
    def _extract_code(output: str) -> str:
        m = re.search(r"```(?:python)?\\n(.*?)```", output, re.DOTALL)
        return m.group(1).strip() if m else output

    @staticmethod
    def _extract_json(output: str) -> dict:
        m = re.search(r"\\{.*\\}", output, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {}
'''

GEMINI_ADAPTER_PY = '''\
"""GeminiAdapter — Gemini API 封裝（google-genai SDK）。"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


class GeminiAdapter:
    """Gemini API 封裝，支援 generate + function_call。"""

    TIERS = {
        "FAST": "gemini-2.5-flash",
        "BALANCE": "gemini-2.5-flash",
        "SMART": "gemini-2.5-pro",
    }

    def __init__(self) -> None:
        self._client = None
        self.available = False
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=api_key)
                self.available = True
            except ImportError:
                log.warning("google-genai 未安裝，Gemini API 不可用")
            except Exception as e:
                log.warning("Gemini API 初始化失敗: %s", e)

    async def generate(self, prompt: str, system: str = "", tier: str = "BALANCE") -> dict:
        """文字生成。回傳 {"text": str, "model": str}。"""
        if not self.available or not self._client:
            return {"text": "", "model": ""}
        model = self.TIERS.get(tier, "gemini-2.5-flash")
        try:
            from google import genai
            contents = "%s\\n\\n%s" % (system, prompt) if system else prompt
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            text = response.text or ""
            return {"text": text, "model": model}
        except Exception as e:
            log.error("Gemini generate 失敗: %s", e)
            return {"text": "", "model": ""}
'''

LLM_ROUTER_PY = '''\
"""LLMRouter — 統一 LLM 路由（API + CLI fallback）。"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


class LLMRouter:
    """統一路由 LLM 呼叫，支援 API 優先 + CLI fallback。"""

    def __init__(self):
        self._backend = os.getenv("LLM_BACKEND", "gemini")

    async def generate(self, prompt: str, system: str = "", tier: str = "FAST") -> str:
        """文字生成（API 優先，CLI fallback）。"""
        # 嘗試 Gemini API
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            try:
                return await self._gemini_api(prompt, system)
            except Exception as e:
                log.warning("Gemini API 失敗，fallback CLI: %s", e)

        # Fallback: CLI
        from src.skills.internal.llm_cli import LlmCliSkill
        skill = LlmCliSkill()
        result = await skill.execute({"prompt": prompt, "mode": "chat", "system_prompt": system})
        if result.success:
            return result.data.get("output", "")
        return f"（LLM 不可用：{result.error}）"

    async def _gemini_api(self, prompt: str, system: str) -> str:
        """呼叫 Gemini API。"""
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        contents = f"{system}\\n\\n{prompt}" if system else prompt
        response = client.models.generate_content(model=model, contents=contents)
        return response.text
'''

FILES: dict[str, str] = {
    "src/skills/internal/llm_cli.py": LLM_CLI_PY,
    "src/llm/__init__.py": '"""LLM 整合模組。"""\n',
    "src/llm/gemini_adapter.py": GEMINI_ADAPTER_PY,
    "src/llm/llm_router.py": LLM_ROUTER_PY,
}


def scaffold(project_dir: Path) -> list[str]:
    """產出 LLM CLI Skill + Router。"""
    created: list[str] = []
    for rel, content in FILES.items():
        full = project_dir / rel
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        created.append(rel)
    return created


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方式: python scaffold_llm_cli.py <project_dir>")
        sys.exit(1)
    project_dir = Path(sys.argv[1])
    project_dir.mkdir(parents=True, exist_ok=True)
    created = scaffold(project_dir)
    if created:
        print(f"✅ 產出 {len(created)} 個檔案：")
        for f in created:
            print(f"   • {f}")
    else:
        print("✅ 所有檔案已存在。")


if __name__ == "__main__":
    main()
