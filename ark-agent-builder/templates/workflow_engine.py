"""WorkflowEngine — YAML 工作流載入與執行。"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

from src.skills.base import SkillResult
from src.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RunContext:
    """工作流執行上下文。"""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    workflow_id: str = ""
    params: dict = field(default_factory=dict)
    status: RunStatus = RunStatus.PENDING
    outputs: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 0

    def set_output(self, step_id: str, data: dict) -> None:
        self.outputs[step_id] = data

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)


class WorkflowEngine:
    """YAML 工作流引擎：載入、解析、執行。"""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._workflows: dict[str, dict] = {}

    def load(self, yaml_path: Path) -> dict:
        """載入單一 YAML 工作流。"""
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        wf_id = data.get("id", yaml_path.stem)
        data["id"] = wf_id
        self._workflows[wf_id] = data
        return data

    def load_dir(self, dir_path: Path) -> int:
        """載入目錄下所有 .yaml 工作流（不含 schedules/）。"""
        count = 0
        if not dir_path.exists():
            return 0
        for p in dir_path.glob("*.yaml"):
            try:
                self.load(p)
                count += 1
            except Exception as e:
                logger.warning("載入工作流 %s 失敗: %s", p.name, e)
        return count

    def list_workflows(self) -> list[dict]:
        """列出所有已載入工作流。"""
        return [{"id": w["id"], "name": w.get("name", w["id"])} for w in self._workflows.values()]

    async def run(self, workflow_id: str, params: dict | None = None) -> RunContext:
        """執行工作流。"""
        wf = self._workflows.get(workflow_id)
        if not wf:
            # 嘗試從檔案載入
            path = Path(f"workflows/{workflow_id}.yaml")
            if path.exists():
                wf = self.load(path)
            else:
                ctx = RunContext(workflow_id=workflow_id, status=RunStatus.FAILED)
                ctx.add_error(f"工作流不存在: {workflow_id}")
                return ctx

        steps = wf.get("steps", [])
        ctx = RunContext(
            workflow_id=workflow_id,
            params=params or {},
            total_steps=len(steps),
            status=RunStatus.RUNNING,
        )

        for i, step in enumerate(steps):
            ctx.current_step = i + 1
            try:
                await self._execute_step(step, ctx)
            except Exception as e:
                ctx.add_error(f"步驟 {step.get('id', i)} 失敗: {e}")
                ctx.status = RunStatus.FAILED
                return ctx

        ctx.status = RunStatus.COMPLETED
        return ctx

    async def _execute_step(self, step: dict, ctx: RunContext) -> None:
        """執行單一步驟（依 type 分派）。"""
        step_type = step.get("type", "skill")

        if step_type == "skill":
            await self._exec_skill(step, ctx)
        elif step_type == "condition":
            await self._exec_condition(step, ctx)
        elif step_type == "loop":
            await self._exec_loop(step, ctx)
        elif step_type == "parallel":
            await self._exec_parallel(step, ctx)
        else:
            ctx.add_error(f"未知步驟類型: {step_type}")

    async def _exec_skill(self, step: dict, ctx: RunContext) -> None:
        """執行 skill 步驟。"""
        skill_id = step.get("skill", "")
        raw_params = step.get("params", {})
        resolved = self._resolve_params(raw_params, ctx)
        output_key = step.get("output", step.get("id", ""))

        result = await self._registry.invoke(skill_id, resolved)
        if result.success:
            ctx.set_output(output_key, result.data)
        else:
            raise RuntimeError(f"{skill_id}: {result.error}")

    async def _exec_condition(self, step: dict, ctx: RunContext) -> None:
        """執行 condition 步驟。"""
        expr = step.get("condition", "False")
        result = self._eval_expr(expr, ctx)

        branch = step.get("then") if result else step.get("else")
        if branch:
            await self._execute_step(branch, ctx)

    async def _exec_loop(self, step: dict, ctx: RunContext) -> None:
        """執行 loop 步驟。"""
        items_raw = step.get("items", "[]")
        items = self._resolve_value(items_raw, ctx)
        if isinstance(items, str):
            items = json.loads(items)

        item_var = step.get("item_var", "item")
        inner_step = step.get("step", {})
        output_key = step.get("output", step.get("id", ""))
        results = []

        for item in items:
            # 注入 item_var 到 ctx.params 供模板解析
            ctx.params[item_var] = item
            await self._execute_step(inner_step, ctx)
            # 收集每次迴圈的輸出
            inner_out = step.get("step", {}).get("output", "")
            if inner_out and inner_out in ctx.outputs:
                results.append(ctx.outputs[inner_out])

        ctx.set_output(output_key, {"results": results, "count": len(results)})

    async def _exec_parallel(self, step: dict, ctx: RunContext) -> None:
        """執行 parallel 步驟（序列化執行，未來可改 asyncio.gather）。"""
        sub_steps = step.get("steps", [])
        for s in sub_steps:
            await self._execute_step(s, ctx)

    def _resolve_params(self, raw: dict, ctx: RunContext) -> dict:
        """解析參數模板（Jinja2 風格簡易版）。"""
        resolved = {}
        for k, v in raw.items():
            resolved[k] = self._resolve_value(v, ctx)
        return resolved

    def _resolve_value(self, value, ctx: RunContext):
        """解析單一值。"""
        if not isinstance(value, str):
            return value

        # 環境變數 ${ENV_VAR}
        if value.startswith("${") and value.endswith("}"):
            return os.environ.get(value[2:-1], "")

        # 簡單引用 {{ outputs.step_id.field }}
        simple = re.match(r"^\{\{\s*outputs\.(\w+)(?:\.(\w+))?\s*\}\}$", value)
        if simple:
            step_id = simple.group(1)
            field_name = simple.group(2)
            data = ctx.outputs.get(step_id, {})
            if field_name:
                return data.get(field_name, "")
            return data

        # params 引用 {{ params.key }}
        param_match = re.match(r"^\{\{\s*params\.(\w+)\s*\}\}$", value)
        if param_match:
            return ctx.params.get(param_match.group(1), "")

        # item_var 引用 {{ var_name }}
        item_match = re.match(r"^\{\{\s*(\w+)\s*\}\}$", value)
        if item_match:
            return ctx.params.get(item_match.group(1), value)

        # 含有模板但不是純引用 → 字串替換
        if "{{" in value:
            def _replacer(m: re.Match) -> str:
                expr = m.group(1).strip()
                if expr.startswith("outputs."):
                    parts = expr[8:].split(".", 1)
                    data = ctx.outputs.get(parts[0], {})
                    return str(data.get(parts[1], "")) if len(parts) > 1 else str(data)
                if expr.startswith("params."):
                    return str(ctx.params.get(expr[7:], ""))
                return str(ctx.params.get(expr, m.group(0)))
            return re.sub(r"\{\{\s*(.+?)\s*\}\}", _replacer, value)

        return value

    def _eval_expr(self, expr: str, ctx: RunContext) -> bool:
        """安全評估條件表達式（白名單 builtins）。"""
        _SAFE_BUILTINS = {"len": len, "str": str, "int": int, "float": float, "bool": bool, "True": True, "False": False, "None": None}
        try:
            local_ns = {"outputs": ctx.outputs, "params": ctx.params}
            return bool(eval(expr, {"__builtins__": _SAFE_BUILTINS}, local_ns))  # noqa: S307
        except Exception:
            return False
