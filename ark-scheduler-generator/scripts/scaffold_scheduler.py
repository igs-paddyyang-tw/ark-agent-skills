"""scaffold_scheduler.py — 一鍵產出 Workflow + 排程引擎。

用法：python scripts/scaffold_scheduler.py [project_dir]
產出：src/workflow/ + src/scheduler/ + workflows/（共 8 個檔案）
"""
import sys
from pathlib import Path

FILES: dict[str, str] = {}

FILES["src/workflow/__init__.py"] = 'from src.workflow.engine import WorkflowEngine\nfrom src.workflow.context import RunContext\n'

FILES["src/workflow/context.py"] = '''"""RunContext — 工作流執行上下文。"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RunContext:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_id: str = ""
    params: dict = field(default_factory=dict)
    status: RunStatus = RunStatus.PENDING
    outputs: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def set_output(self, step_id: str, data: Any) -> None:
        self.outputs[step_id] = data

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "workflow_id": self.workflow_id, "status": self.status.value, "outputs": self.outputs, "errors": self.errors}
'''

FILES["src/workflow/engine.py"] = '''"""WorkflowEngine — YAML 工作流執行引擎。"""

import os
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from src.skills.registry import SkillRegistry


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RunContext:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_id: str = ""
    params: dict = field(default_factory=dict)
    status: RunStatus = RunStatus.PENDING
    outputs: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def set_output(self, step_id: str, data: Any) -> None:
        self.outputs[step_id] = data


class WorkflowEngine:
    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._workflows: dict[str, dict] = {}

    def load(self, yaml_path: Path) -> dict:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        self._workflows[data["id"]] = data
        return data

    def load_dir(self, dir_path: Path) -> int:
        count = 0
        if not dir_path.exists():
            return 0
        for f in dir_path.glob("*.yaml"):
            self.load(f)
            count += 1
        return count

    async def run(self, workflow_id: str, params: dict | None = None) -> RunContext:
        ctx = RunContext(workflow_id=workflow_id, params=params or {})
        wf = self._workflows.get(workflow_id)
        if not wf:
            ctx.status = RunStatus.FAILED
            ctx.errors.append(f"Workflow not found: {workflow_id}")
            return ctx

        ctx.status = RunStatus.RUNNING
        for step in wf.get("steps", []):
            skill_id = step["skill"]
            step_params = self._resolve_params(step.get("params", {}), ctx)
            result = await self._registry.invoke(skill_id, step_params)
            if result.success:
                ctx.set_output(step["id"], result.data)
            else:
                ctx.errors.append(f"Step {step['id']} failed: {result.error}")
                ctx.status = RunStatus.FAILED
                return ctx

        ctx.status = RunStatus.COMPLETED
        return ctx

    def _resolve_params(self, params: dict, ctx: RunContext) -> dict:
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and "{{" in v:
                resolved[k] = self._interpolate(v, ctx)
            elif isinstance(v, str) and v.startswith("${"):
                resolved[k] = os.getenv(v[2:-1], v)
            else:
                resolved[k] = v
        return resolved

    def _interpolate(self, template: str, ctx: RunContext) -> Any:
        match = re.match(r"\\{\\{\\s*outputs\\.(\\w+)\\s*\\}\\}", template)
        if match:
            return ctx.outputs.get(match.group(1), {})
        return template
'''

FILES["src/scheduler/__init__.py"] = 'from src.scheduler.engine import ScheduleEngine\n'

FILES["src/scheduler/engine.py"] = '''"""ScheduleEngine — APScheduler 排程引擎。"""

import logging
from pathlib import Path

import yaml

from src.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class ScheduleEngine:
    def __init__(self, workflow_engine: WorkflowEngine) -> None:
        self._wf = workflow_engine
        self._schedules: list[dict] = []
        self._scheduler = None

    def load_schedules(self, dir_path: Path) -> int:
        if not dir_path.exists():
            return 0
        for f in dir_path.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            self._schedules.append(data)
        return len(self._schedules)

    def start(self) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.warning("apscheduler not installed, scheduler disabled")
            return

        self._scheduler = AsyncIOScheduler()
        for s in self._schedules:
            if not s.get("enabled", True):
                continue
            cron = s.get("cron", "")
            parts = cron.split()
            if len(parts) == 5:
                trigger = CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4])
                self._scheduler.add_job(self._run_workflow, trigger, args=[s["workflow_id"], s.get("params", {})])
        self._scheduler.start()
        logger.info(f"Scheduler started with {len(self._schedules)} jobs")

    async def _run_workflow(self, workflow_id: str, params: dict) -> None:
        ctx = await self._wf.run(workflow_id, params)
        if ctx.errors:
            logger.error(f"Workflow {workflow_id} failed: {ctx.errors}")

    def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
'''

FILES["workflows/hello.yaml"] = '''id: hello
name: 測試工作流
steps:
  - id: greet
    type: skill
    skill: echo
    params:
      message: "Hello from workflow!"
    output: greeting
'''

FILES["workflows/daily_news.yaml"] = '''id: daily_news
name: 每日科技日報
steps:
  - id: scrape
    type: skill
    skill: news_scraper
    params:
      config_path: "config/news_sources.yaml"
    output: scraped

  - id: parse
    type: skill
    skill: news_parser
    params:
      data: "{{ outputs.scraped }}"
    output: parsed

  - id: render
    type: skill
    skill: news_renderer
    params:
      data: "{{ outputs.scraped }}"
    output: html_file

  - id: send
    type: skill
    skill: telegram_send_file
    params:
      chat_id: "${TELEGRAM_CHAT_ID}"
      file_path: "{{ outputs.html_file.path }}"
    output: sent
'''

FILES["workflows/schedules/daily_news.yaml"] = '''id: daily_news_schedule
workflow_id: daily_news
cron: "0 9 * * *"
enabled: true
timezone: Asia/Taipei
params: {}
'''


def scaffold(project_dir: Path) -> list[str]:
    created = []
    for rel_path, content in FILES.items():
        full = project_dir / rel_path
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        created.append(str(rel_path))
    return created


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    files = scaffold(target)
    print(f"✅ scaffold_scheduler: 產出 {len(files)} 個檔案到 {target}")
    for f in files:
        print(f"   {f}")
