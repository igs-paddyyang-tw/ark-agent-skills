"""scaffold_llm_cli.py — 確定性產出 LLM CLI Skill + LLMRouter。

用法：python .kiro/skills/ark-llm-cli/scripts/scaffold_llm_cli.py [project_dir]
產出：
  src/skills/internal/gemini_cli.py  — v1 單一 Gemini 後端（deprecated 相容層）
  src/skills/internal/llm_cli.py     — v2 統一 4 後端（主要）
  src/llm/llm_router.py             — LLMRouter（API + CLI fallback）
"""
import sys
import textwrap
from pathlib import Path


def _write(project_dir: Path, rel_path: str, content: str) -> bool:
    """寫入檔案（已存在則跳過，冪等）。回傳是否新建。"""
    target = project_dir / rel_path
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content), encoding="utf-8")
    return True


def scaffold(project_dir: Path) -> list[str]:
    """產出 LLM CLI Skill + LLMRouter。回傳已建立的檔案路徑列表。"""
    created: list[str] = []

    def emit(rel_path: str, content: str) -> None:
        if _write(project_dir, rel_path, content):
            created.append(rel_path)

    # ── 1. src/skills/internal/gemini_cli.py（v1 獨立 subprocess）──
    emit("src/skills/internal/gemini_cli.py", '''\
        """gemini_cli — 封裝 Gemini CLI 為標準化 Skill（subprocess 呼叫 gemini -p）。"""

        import asyncio
        import json
        import os
        import re
        import tempfile
        from pathlib import Path

        from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


        class GeminiCliParams(SkillParam):
            """gemini_cli 輸入參數。"""
            prompt: str
            mode: str = "chat"  # chat / codegen / skill_gen / evaluate
            model: str = "gemini-2.5-flash"
            system_prompt: str = ""
            timeout: int = 120
            output_path: str = ""
            skill_id: str = ""


        class GeminiCliSkill(BaseSkill):
            """Gemini CLI 封裝 — 對話、CodeGen、Skill 產出、需求評估。"""

            skill_id = "gemini_cli"
            skill_type = SkillType.PYTHON
            description = "Gemini CLI 封裝 — subprocess 呼叫 gemini -p"
            version = "1.0.0"
            input_schema = GeminiCliParams

            async def execute(self, params: dict) -> SkillResult:
                """執行 Gemini CLI。"""
                try:
                    p = GeminiCliParams(**params)
                    if p.mode == "chat":
                        return await self._chat(p)
                    elif p.mode == "codegen":
                        return await self._codegen(p)
                    elif p.mode == "skill_gen":
                        return await self._skill_gen(p)
                    elif p.mode == "evaluate":
                        return await self._evaluate(p)
                    else:
                        return SkillResult(success=False, error=f"不支援的模式: {p.mode}")
                except asyncio.TimeoutError:
                    return SkillResult(success=False, error="Gemini CLI 超時")
                except Exception as e:
                    return SkillResult(success=False, error=f"gemini_cli 錯誤: {e}")

            async def _run_cli(self, prompt: str, model: str, timeout: int) -> tuple[str, str, int]:
                """執行 gemini -p subprocess。"""
                gemini_cmd = os.getenv("GEMINI_CLI_CMD", "gemini.cmd" if os.name == "nt" else "gemini")
                cmd = [gemini_cmd, "-p", prompt, "-m", model, "--skip-trust", "--approval-mode", "plan"]
                env = os.environ.copy()
                env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                        cwd=tempfile.gettempdir(),
                    )
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                    return (
                        stdout.decode("utf-8").strip() if stdout else "",
                        stderr.decode("utf-8").strip() if stderr else "",
                        process.returncode or 0,
                    )
                except FileNotFoundError:
                    return ("", f"{gemini_cmd} 未安裝", 127)
                except asyncio.TimeoutError:
                    return ("", f"超時（{timeout}s）", 124)

            async def _chat(self, p: GeminiCliParams) -> SkillResult:
                prompt = f"{p.system_prompt}\\n\\n{p.prompt}" if p.system_prompt else p.prompt
                out, err, code = await self._run_cli(prompt, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗 (code {code}): {err[:300]}")
                return SkillResult(success=True, data={"output": out, "model": p.model})

            async def _codegen(self, p: GeminiCliParams) -> SkillResult:
                prompt = f"只輸出程式碼，不要解釋。需求：{p.prompt}"
                out, err, code = await self._run_cli(prompt, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
                source = self._extract_code(out)
                if p.output_path:
                    Path(p.output_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(p.output_path).write_text(source, encoding="utf-8")
                return SkillResult(success=True, data={"code": source, "path": p.output_path or "", "model": p.model})

            async def _skill_gen(self, p: GeminiCliParams) -> SkillResult:
                sid = p.skill_id or "generated_skill"
                prompt = (
                    f"產出一個 Python Skill，遵循以下介面：\\n"
                    f"- 繼承 BaseSkill（from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType）\\n"
                    f'- skill_id = "{sid}"\\n'
                    f"- 實作 async def execute(self, params: dict) -> SkillResult\\n\\n"
                    f"需求：{p.prompt}\\n\\n只輸出程式碼。"
                )
                out, err, code = await self._run_cli(prompt, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
                source = self._extract_code(out)
                output_path = p.output_path or f"src/skills/internal/{sid}.py"
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(source, encoding="utf-8")
                return SkillResult(success=True, data={"skill_id": sid, "path": output_path, "model": p.model})

            async def _evaluate(self, p: GeminiCliParams) -> SkillResult:
                prompt = (
                    "你是意圖分類器。分析用戶需求，回傳純 JSON（不要 markdown）：\\n"
                    '{"action": "answer|invoke|generate", "reason": "...", '
                    '"skill_id": "...", "params": {}}\\n\\n'
                    f"用戶需求：{p.prompt}\\n\\n只回傳 JSON。"
                )
                out, err, code = await self._run_cli(prompt, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
                parsed = self._extract_json(out)
                if not parsed:
                    return SkillResult(success=True, data={"action": "answer", "raw": out})
                return SkillResult(success=True, data=parsed)

            @staticmethod
            def _extract_code(output: str) -> str:
                match = re.search(r"```(?:python)?\\n(.*?)```", output, re.DOTALL)
                return match.group(1).strip() if match else output

            @staticmethod
            def _extract_json(output: str) -> dict:
                match = re.search(r"\\{.*\\}", output, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass
                return {}
    ''')

    # ── 2. src/skills/internal/llm_cli.py（v2 主要）──
    emit("src/skills/internal/llm_cli.py", '''\
        """llm_cli — 通用 LLM CLI 封裝 Skill（Gemini / Kiro / Claude / Antigravity）。"""

        import asyncio
        import json
        import logging
        import os
        import re
        import shutil
        import tempfile
        from pathlib import Path

        from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

        log = logging.getLogger(__name__)


        class LlmCliParams(SkillParam):
            """llm_cli 輸入參數。"""
            prompt: str
            mode: str = "chat"  # chat / codegen / skill_gen / evaluate
            model: str = ""
            system_prompt: str = ""
            timeout: int = 120
            output_path: str = ""
            skill_id: str = ""
            backend: str = ""  # gemini / kiro / claude / antigravity


        def _gemini_cmd() -> str:
            return os.getenv("GEMINI_CLI_CMD", "gemini.cmd" if os.name == "nt" else "gemini")


        def _kiro_cmd() -> str:
            default = (
                str(Path.home() / "AppData/Local/Kiro-Cli/kiro-cli.exe")
                if os.name == "nt"
                else "kiro-cli"
            )
            return os.getenv("KIRO_CLI_PATH", default)


        BACKENDS: dict[str, dict] = {
            "gemini": {
                "cmd_fn": _gemini_cmd,
                "default_model": "gemini-2.5-flash",
                "build_args": lambda cmd, prompt, model: [
                    cmd, "-p", prompt, "-m", model, "--skip-trust", "--approval-mode", "plan",
                ],
                "env_extra": {"GEMINI_CLI_TRUST_WORKSPACE": "true"},
                "default_timeout": 60,
            },
            "kiro": {
                "cmd_fn": _kiro_cmd,
                "default_model": "auto",
                "build_args": lambda cmd, prompt, model: [
                    cmd, "chat", "--trust-all-tools", "--legacy-ui", "--resume",
                    "--model", model, "--message", prompt,
                ],
                "env_extra": {},
                "default_timeout": 120,
            },
            "claude": {
                "cmd_fn": lambda: os.getenv("CLAUDE_CLI_CMD", "claude"),
                "default_model": "claude-sonnet-4-20250514",
                "build_args": lambda cmd, prompt, model: [
                    cmd, "-p", prompt, "-m", model, "--output-format", "text",
                ],
                "env_extra": {},
                "default_timeout": 60,
            },
            "antigravity": {
                "cmd_fn": lambda: os.getenv("AG_CLI_CMD", "ag"),
                "default_model": "claude-sonnet-4-20250514",
                "build_args": lambda cmd, prompt, model: [
                    cmd, "chat", "-m", model, "--message", prompt,
                ],
                "env_extra": {},
                "default_timeout": 60,
            },
        }

        FALLBACK_ORDER = ["gemini", "claude", "kiro", "antigravity"]

        _availability_cache: dict[str, bool] = {}


        def _check_available(backend: str) -> bool:
            """檢查 CLI 是否已安裝（結果快取）。"""
            if backend in _availability_cache:
                return _availability_cache[backend]
            cfg = BACKENDS.get(backend)
            if not cfg:
                _availability_cache[backend] = False
                return False
            cmd = cfg["cmd_fn"]()
            available = shutil.which(cmd) is not None
            _availability_cache[backend] = available
            return available


        class LlmCliSkill(BaseSkill):
            """通用 LLM CLI 封裝 — 對話、CodeGen、Skill 產出、需求評估。"""

            skill_id = "llm_cli"
            skill_type = SkillType.PYTHON
            description = "統一 LLM CLI 封裝 — Gemini/Kiro/Claude/Antigravity（自動 fallback）"
            version = "2.0.0"
            input_schema = LlmCliParams

            @classmethod
            def is_available(cls, backend: str | None = None) -> bool:
                """檢查指定後端是否可用。"""
                resolved = backend or os.getenv("LLM_CLI_BACKEND", "gemini")
                return _check_available(resolved)

            def _resolve_backend(self, preferred: str) -> str | None:
                """解析可用後端，依 fallback chain 降級。"""
                if preferred and _check_available(preferred):
                    return preferred
                env_backend = os.getenv("LLM_CLI_BACKEND", "")
                if env_backend and _check_available(env_backend):
                    return env_backend
                for b in FALLBACK_ORDER:
                    if _check_available(b):
                        return b
                return None

            async def execute(self, params: dict) -> SkillResult:
                """執行 LLM CLI Skill。"""
                try:
                    p = LlmCliParams(**params)
                    backend = self._resolve_backend(p.backend)
                    if not backend:
                        return SkillResult(success=False, error="無可用 CLI 後端")

                    if p.mode == "chat":
                        return await self._chat(p, backend)
                    elif p.mode == "codegen":
                        return await self._codegen(p, backend)
                    elif p.mode == "skill_gen":
                        return await self._skill_gen(p, backend)
                    elif p.mode == "evaluate":
                        return await self._evaluate(p, backend)
                    else:
                        return SkillResult(success=False, error=f"不支援的模式: {p.mode}")
                except asyncio.TimeoutError:
                    return SkillResult(success=False, error="LLM CLI 超時")
                except Exception as e:
                    return SkillResult(success=False, error=f"llm_cli 錯誤: {e}")

            async def _run_cli(
                self, prompt: str, backend: str, model: str, timeout: int
            ) -> tuple[str, str, int]:
                """執行 CLI subprocess。"""
                cfg = BACKENDS[backend]
                cmd = cfg["cmd_fn"]()
                m = model or cfg["default_model"]
                args = cfg["build_args"](cmd, prompt, m)
                env = os.environ.copy()
                env.update(cfg.get("env_extra", {}))
                t = timeout or cfg.get("default_timeout", 60)

                try:
                    process = await asyncio.create_subprocess_exec(
                        *args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                        cwd=tempfile.gettempdir(),
                    )
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=t)
                    return (
                        stdout.decode("utf-8").strip() if stdout else "",
                        stderr.decode("utf-8").strip() if stderr else "",
                        process.returncode or 0,
                    )
                except FileNotFoundError:
                    return ("", f"{cmd} 未安裝", 127)
                except asyncio.TimeoutError:
                    return ("", f"超時（{t}s）", 124)

            async def _chat(self, p: LlmCliParams, backend: str) -> SkillResult:
                """純對話模式。"""
                prompt = f"{p.system_prompt}\\n\\n{p.prompt}" if p.system_prompt else p.prompt
                out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗 (code {code}): {err[:300]}")
                return SkillResult(
                    success=True,
                    data={"output": out, "backend": backend, "model": p.model or BACKENDS[backend]["default_model"]},
                )

            async def _codegen(self, p: LlmCliParams, backend: str) -> SkillResult:
                """程式碼產出模式。"""
                prompt = f"只輸出程式碼，不要解釋。需求：{p.prompt}"
                out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
                source = self._extract_code(out)
                if p.output_path:
                    Path(p.output_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(p.output_path).write_text(source, encoding="utf-8")
                return SkillResult(success=True, data={"code": source, "path": p.output_path or "", "backend": backend})

            async def _skill_gen(self, p: LlmCliParams, backend: str) -> SkillResult:
                """產出 BaseSkill .py 檔案。"""
                sid = p.skill_id or "generated_skill"
                prompt = (
                    f"產出一個 Python Skill，遵循以下介面：\\n"
                    f"- 繼承 BaseSkill（from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType）\\n"
                    f'- skill_id = "{sid}"\\n'
                    f"- 實作 async def execute(self, params: dict) -> SkillResult\\n"
                    f"- Docstring 繁體中文\\n\\n"
                    f"需求：{p.prompt}\\n\\n只輸出程式碼。"
                )
                out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
                source = self._extract_code(out)
                output_path = p.output_path or f"src/skills/internal/{sid}.py"
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(source, encoding="utf-8")
                return SkillResult(success=True, data={"skill_id": sid, "path": output_path, "backend": backend})

            async def _evaluate(self, p: LlmCliParams, backend: str) -> SkillResult:
                """評估需求，回傳結構化 JSON。"""
                prompt = (
                    "你是意圖分類器。分析用戶需求，回傳純 JSON（不要 markdown）：\\n"
                    '{"action": "answer|invoke|generate", "reason": "...", '
                    '"skill_id": "...", "params": {}}\\n\\n'
                    f"用戶需求：{p.prompt}\\n\\n只回傳 JSON。"
                )
                out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
                if code != 0:
                    return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
                parsed = self._extract_json(out)
                if not parsed:
                    return SkillResult(success=True, data={"action": "answer", "raw": out})
                return SkillResult(success=True, data=parsed)

            @staticmethod
            def _extract_code(output: str) -> str:
                """從 CLI 輸出提取程式碼區塊。"""
                match = re.search(r"```(?:python)?\\n(.*?)```", output, re.DOTALL)
                return match.group(1).strip() if match else output

            @staticmethod
            def _extract_json(output: str) -> dict:
                """從 CLI 輸出提取 JSON。"""
                match = re.search(r"\\{.*\\}", output, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass
                return {}
    ''')

    # ── 3. src/llm/llm_router.py ──
    emit("src/llm/__init__.py", '''\
        """LLM 整合層。"""
    ''')

    emit("src/llm/gemini_adapter.py", '''\
        """GeminiAdapter — Gemini API 封裝（google-genai SDK）。"""
        from __future__ import annotations

        import logging
        import os

        log = logging.getLogger(__name__)


        class GeminiAdapter:
            """Gemini API 封裝，支援 generate 和 function_call。"""

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
                    contents = f"{system}\\n\\n{prompt}" if system else prompt
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
    ''')

    emit("src/llm/llm_router.py", '''\
        """LLMRouter — 統一路由 + fallback chain。

        generate：Gemini API → Gemini CLI → 靜態回應。
        function_call：僅 Gemini API（其他後端不支援 FC）。
        """
        from __future__ import annotations

        import asyncio
        import logging
        import os

        log = logging.getLogger(__name__)


        class LLMRouter:
            """統一 LLM 路由，自動 fallback。"""

            def __init__(self) -> None:
                self._backend = os.getenv("LLM_BACKEND", "gemini")
                self._gemini = None

            def _get_gemini(self):
                """延遲初始化 GeminiAdapter。"""
                if self._gemini is None:
                    from .gemini_adapter import GeminiAdapter
                    self._gemini = GeminiAdapter()
                return self._gemini

            async def generate(self, prompt: str, system: str = "", tier: str = "BALANCE") -> dict:
                """文字生成，自動 fallback。回傳 {"text": str, "model": str}。"""
                gemini = self._get_gemini()
                if gemini.available:
                    result = await gemini.generate(prompt, system=system, tier=tier)
                    if result["text"]:
                        return result

                result = await self._gemini_cli_generate(prompt, system)
                if result["text"]:
                    return result

                return {"text": "抱歉，目前 LLM 不可用。請稍後再試。", "model": "static"}

            async def function_call(self, user_message: str, tools: list[dict]) -> dict:
                """Function Calling（僅 Gemini API，不支援 fallback）。

                回傳 {"action": "call", "skill_id": str, "params": dict}
                或 {"action": "reply", "text": str}。
                """
                gemini = self._get_gemini()
                if not gemini.available:
                    return {"action": "reply", "text": "FC 不可用（需要 Gemini API Key）"}

                try:
                    from google import genai

                    contents = user_message
                    response = await gemini._client.aio.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=contents,
                        config=genai.types.GenerateContentConfig(
                            tools=[{"function_declarations": tools}],
                        ),
                    )

                    # 解析 FC 回應
                    part = response.candidates[0].content.parts[0]
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        return {
                            "action": "call",
                            "skill_id": fc.name,
                            "params": dict(fc.args) if fc.args else {},
                        }
                    return {"action": "reply", "text": part.text or ""}
                except Exception as e:
                    log.error("Function call 失敗: %s", e)
                    return {"action": "reply", "text": f"FC 錯誤: {e}"}

            @staticmethod
            async def _gemini_cli_generate(prompt: str, system: str = "") -> dict:
                """Gemini CLI subprocess fallback。"""
                gemini_cmd = os.getenv(
                    "GEMINI_CLI_CMD", "gemini.cmd" if os.name == "nt" else "gemini"
                )
                full_prompt = f"{system}\\n\\n{prompt}" if system else prompt
                cmd = [gemini_cmd, "-p", full_prompt, "-m", "gemini-2.5-flash", "--skip-trust"]
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=os.environ.copy(),
                    )
                    stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
                    output = stdout.decode("utf-8").strip() if stdout else ""
                    return {"text": output, "model": "gemini-cli"}
                except (asyncio.TimeoutError, FileNotFoundError, Exception) as e:
                    log.warning("Gemini CLI fallback failed: %s", e)
                    return {"text": "", "model": ""}
    ''')

    return created


def main() -> None:
    project_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    project_dir = project_dir.resolve()

    print(f"🔧 scaffold_llm_cli: 產出 LLM 整合層到 {project_dir}")
    created = scaffold(project_dir)
    print(f"✅ 完成！產出 {len(created)} 個檔案：")
    for f in created:
        print(f"   {f}")


if __name__ == "__main__":
    main()
