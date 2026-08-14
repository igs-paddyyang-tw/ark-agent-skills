"""YAML Workflow 執行引擎 — 讀 yaml → step 順序執行。

Workflow YAML 格式：
  name: my-workflow
  steps:
    - id: step1
      action: llm_chat
      params:
        prompt: "..."
    - id: step2
      action: skill_invoke
      params:
        skill_id: news
        query: "..."
      depends_on: step1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


@dataclass
class StepResult:
    """單步驟執行結果。"""
    step_id: str
    success: bool
    output: Any = None
    error: str = ""


@dataclass
class WorkflowResult:
    """整體 Workflow 執行結果。"""
    name: str
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    error: str = ""


class WorkflowEngine:
    """YAML Workflow 執行引擎。

    支援的 action 類型：
    - llm_chat: 呼叫 LLM 取得文字回應
    - skill_invoke: 呼叫已註冊的 Skill
    - shell: 執行 shell 指令（需啟用）
    - template: 渲染 Jinja2 模板
    """

    def __init__(self, skill_registry: Any = None) -> None:
        self._registry = skill_registry
        self._action_handlers: dict[str, Any] = {
            "llm_chat": self._handle_llm_chat,
            "skill_invoke": self._handle_skill_invoke,
            "template": self._handle_template,
        }

    async def execute(self, workflow_path: str | Path) -> WorkflowResult:
        """載入並執行 Workflow YAML。"""
        path = Path(workflow_path)
        if not path.exists():
            return WorkflowResult(
                name=str(path), success=False,
                error=f"Workflow file not found: {path}",
            )

        with open(path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)

        if not spec or "steps" not in spec:
            return WorkflowResult(
                name=str(path), success=False,
                error="Invalid workflow: missing 'steps'",
            )

        name = spec.get("name", path.stem)
        return await self._run_steps(name, spec["steps"])

    async def _run_steps(
        self, name: str, steps: list[dict],
    ) -> WorkflowResult:
        """依序執行所有步驟。"""
        results: list[StepResult] = []
        context: dict[str, Any] = {}  # 步驟間傳遞資料

        for step_spec in steps:
            step_id = step_spec.get("id", f"step_{len(results)}")
            action = step_spec.get("action", "")
            params = step_spec.get("params", {})

            # 注入前步驟結果
            params["_context"] = context

            handler = self._action_handlers.get(action)
            if not handler:
                result = StepResult(
                    step_id=step_id, success=False,
                    error=f"Unknown action: {action}",
                )
            else:
                try:
                    output = await handler(params)
                    result = StepResult(step_id=step_id, success=True, output=output)
                    context[step_id] = output
                except Exception as e:
                    log.error("Step %s failed: %s", step_id, e)
                    result = StepResult(step_id=step_id, success=False, error=str(e))

            results.append(result)

            # 失敗時中止（除非標記 continue_on_error）
            if not result.success and not step_spec.get("continue_on_error", False):
                return WorkflowResult(
                    name=name, success=False, steps=results,
                    error=f"Step '{step_id}' failed: {result.error}",
                )

        all_ok = all(r.success for r in results)
        return WorkflowResult(name=name, success=all_ok, steps=results)

    # ── Action Handlers ──

    async def _handle_llm_chat(self, params: dict) -> str:
        """呼叫 LLM 快答。"""
        prompt = params.get("prompt", "")
        system = params.get("system", "")
        try:
            from src.llm.gemini_chat import gemini_quick_chat
            return await gemini_quick_chat(prompt=prompt, system=system)
        except ImportError:
            return f"[LLM unavailable] prompt: {prompt}"

    async def _handle_skill_invoke(self, params: dict) -> Any:
        """呼叫已註冊的 Skill。"""
        if not self._registry:
            raise RuntimeError("No skill registry configured")

        skill_id = params.get("skill_id", "")
        skill_params = {k: v for k, v in params.items() if k not in ("skill_id", "_context")}
        result = await self._registry.invoke(skill_id, skill_params)
        if not result.success:
            raise RuntimeError(f"Skill {skill_id} failed: {result.error}")
        return result.data

    async def _handle_template(self, params: dict) -> str:
        """渲染 Jinja2 模板。"""
        from jinja2 import Template

        template_str = params.get("template", "")
        context = params.get("_context", {})
        variables = {k: v for k, v in params.items() if k not in ("template", "_context")}
        variables.update(context)

        tpl = Template(template_str)
        return tpl.render(**variables)


async def run_workflow(
    workflow_path: str | Path,
    skill_registry: Any = None,
) -> WorkflowResult:
    """便捷函式 — 一行跑完 Workflow。"""
    engine = WorkflowEngine(skill_registry=skill_registry)
    return await engine.execute(workflow_path)
