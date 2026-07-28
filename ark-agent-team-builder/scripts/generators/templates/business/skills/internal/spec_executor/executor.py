"""Executor — 任務執行 + 角色切換。"""
from __future__ import annotations

import asyncio
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Awaitable

from .parser import Task, PlanSpec
from .checkpoint import Progress, load_progress, save_progress

log = logging.getLogger("spec_executor")

TASK_TIMEOUT = 120  # seconds
MAX_RETRY = 2

ROLE_MAP = {
    "coder": "coder-agent",
    "ai-dev": "ai-dev-agent",
    "qa": "qa-agent",
    "pm": "leader-agent",
    "admin": "admin-agent",
    "data": "data-agent",
    "market": "market-agent",
    "report": "report-agent",
}


@dataclass
class TaskResult:
    """單一任務執行結果。"""
    task_id: str
    status: str = "pending"      # pass | fail | skip
    output: str = ""
    duration_ms: int = 0
    retry_count: int = 0
    error: str = ""
    ac_passed: bool = False
    ac_detail: str = ""


@dataclass
class ExecutionContext:
    """執行上下文。"""
    plan: PlanSpec
    progress: Progress
    agents_dir: Path = field(default_factory=lambda: Path("agents"))
    cli_command: str = "kiro-cli"
    gemini_fn: Callable[[str, str], Awaitable[str | None]] | None = None
    on_task_start: Callable[[Task], Awaitable[None]] | None = None
    on_task_done: Callable[[Task, TaskResult], Awaitable[None]] | None = None


async def run_plan(
    plan: PlanSpec,
    ordered_tasks: list[Task],
    resume: bool = True,
    context: ExecutionContext | None = None,
) -> list[TaskResult]:
    """執行整個 plan。

    Args:
        plan: 解析後的 PlanSpec
        ordered_tasks: 拓撲排序後的任務列表
        resume: 是否從 checkpoint 恢復
        context: 執行上下文（None 時自動建立）
    """
    if context is None:
        progress = load_progress(plan.name) if resume else None
        if not progress:
            from datetime import datetime, timezone
            progress = Progress(
                plan_name=plan.name,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        context = ExecutionContext(plan=plan, progress=progress)

    results: list[TaskResult] = []

    for task in ordered_tasks:
        # 已完成的跳過
        if resume and task.id in context.progress.completed:
            prev_status = context.progress.completed[task.id]
            results.append(TaskResult(task_id=task.id, status=prev_status, output="(from checkpoint)"))
            continue

        # 依賴失敗的跳過
        if _has_failed_dependency(task, context.progress):
            result = TaskResult(task_id=task.id, status="skip", error="dependency failed")
            results.append(result)
            context.progress.completed[task.id] = "skip"
            save_progress(context.progress)
            continue

        # 執行
        if context.on_task_start:
            await context.on_task_start(task)

        result = await _execute_with_retry(task, context)
        results.append(result)

        # 更新 checkpoint
        context.progress.completed[task.id] = result.status
        save_progress(context.progress)

        if context.on_task_done:
            await context.on_task_done(task, result)

    return results


async def _execute_with_retry(task: Task, context: ExecutionContext) -> TaskResult:
    """執行任務（含重試）。"""
    last_error = ""

    for attempt in range(MAX_RETRY + 1):
        start = time.monotonic()
        result = await _execute_single(task, context, previous_error=last_error)
        result.duration_ms = int((time.monotonic() - start) * 1000)
        result.retry_count = attempt

        # AC 驗收
        from .verifier import verify_ac
        ac_result = await verify_ac(task, result)
        result.ac_passed = ac_result.passed
        result.ac_detail = ac_result.detail

        if ac_result.passed:
            result.status = "pass"
            log.info("✅ %s: %s (%dms)", task.id, task.title, result.duration_ms)
            return result

        # 失敗
        last_error = ac_result.detail or result.error or "AC not met"
        log.warning("❌ %s attempt %d: %s", task.id, attempt + 1, last_error[:100])

    # 最終失敗
    result.status = "fail"
    result.error = last_error
    log.error("💀 %s: 最終失敗 (%d retries)", task.id, MAX_RETRY)
    return result


async def _execute_single(
    task: Task,
    context: ExecutionContext,
    previous_error: str = "",
) -> TaskResult:
    """執行單一任務（呼叫 CLI 或 Gemini）。"""
    agent_name = ROLE_MAP.get(task.role, "coder-agent")
    agent_dir = context.agents_dir / agent_name

    # 組裝 prompt
    prompt = _build_prompt(task, context, previous_error)

    # 嘗試 kiro-cli
    if shutil.which(context.cli_command):
        output = await _call_cli(prompt, agent_dir, context.cli_command)
        if output is not None:
            return TaskResult(task_id=task.id, output=output)

    # Gemini fallback
    if context.gemini_fn:
        try:
            soul = _load_soul(agent_dir)
            output = await context.gemini_fn(prompt, soul or "你是專業工程師。")
            if output:
                return TaskResult(task_id=task.id, output=output)
        except Exception as e:
            return TaskResult(task_id=task.id, error=f"Gemini failed: {e}")

    return TaskResult(task_id=task.id, error="No executor available (no CLI, no Gemini)")


def _build_prompt(task: Task, context: ExecutionContext, previous_error: str) -> str:
    """組裝執行 prompt。"""
    parts = [
        f"## 任務：{task.title}",
        f"\n預期產出檔案：`{task.output_file}`" if task.output_file else "",
        f"\n驗收條件：{task.ac}" if task.ac else "",
    ]

    # 注入 spec/design context（如有）
    if context.plan.related_spec:
        spec_path = Path(context.plan.related_spec)
        if spec_path.exists():
            spec_content = spec_path.read_text(encoding="utf-8")[:2000]
            parts.append(f"\n## 參考規格（節錄）\n{spec_content}")

    # 重試時注入失敗資訊
    if previous_error:
        parts.append(
            f"\n## ⚠️ 上次嘗試失敗\n"
            f"錯誤：{previous_error}\n"
            f"請修正後重新產出。"
        )

    parts.append("\n## 注意\n- 直接產出可執行的程式碼\n- 確保驗收條件可通過")

    return "\n".join(p for p in parts if p)


async def _call_cli(prompt: str, cwd: Path, cli_command: str) -> str | None:
    """呼叫 kiro-cli。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            cli_command, "chat", "--no-interactive", "-m", prompt,
            cwd=str(cwd) if cwd.exists() else ".",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TASK_TIMEOUT)
        if proc.returncode == 0:
            return stdout.decode("utf-8", errors="ignore")
        return None
    except (asyncio.TimeoutError, FileNotFoundError, OSError) as e:
        log.warning("CLI call failed: %s", e)
        return None


def _load_soul(agent_dir: Path) -> str | None:
    """載入 Agent SOUL.md。"""
    soul_path = agent_dir / ".kiro" / "steering" / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")[:3000]
    return None


def _has_failed_dependency(task: Task, progress: Progress) -> bool:
    """檢查依賴是否有失敗的。"""
    for dep_id in task.depends_on:
        if progress.completed.get(dep_id) == "fail":
            return True
    return False
