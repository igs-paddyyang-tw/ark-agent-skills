#!/usr/bin/env python3
"""scaffold_scheduler.py — 確定性產出 Workflow + 排程引擎。

使用方式：
    python scaffold_scheduler.py <project_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

WF_INIT = '"""Workflow 模組。"""\n'

WF_ENGINE = '''\
"""WorkflowEngine — YAML 工作流解析與執行。"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


class RunContext:
    """工作流執行上下文。"""

    def __init__(self, workflow_id: str, params: dict | None = None):
        self.run_id = uuid.uuid4().hex[:8]
        self.workflow_id = workflow_id
        self.params = params or {}
        self.outputs: dict[str, any] = {}
        self.errors: list[str] = []
        self.status = "running"

    def set_output(self, step_id: str, data) -> None:
        self.outputs[step_id] = data

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "workflow_id": self.workflow_id,
                "status": self.status, "outputs": self.outputs, "errors": self.errors}


class WorkflowEngine:
    """載入 YAML 工作流並依序執行 Skill 步驟。"""

    def __init__(self, registry=None):
        self._registry = registry
        self._workflows: dict[str, dict] = {}

    def load(self, yaml_path: Path) -> dict:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        self._workflows[data["id"]] = data
        return data

    def load_dir(self, directory: Path) -> int:
        count = 0
        if not directory.exists():
            return 0
        for f in directory.glob("*.yaml"):
            if f.name.startswith("_"):
                continue
            self.load(f)
            count += 1
        return count

    def list_workflows(self) -> list[dict]:
        return [{"id": w["id"], "name": w.get("name", w["id"])} for w in self._workflows.values()]

    async def run(self, workflow_id: str, params: dict | None = None) -> RunContext:
        wf = self._workflows.get(workflow_id)
        if not wf:
            ctx = RunContext(workflow_id, params)
            ctx.status = "failed"
            ctx.errors.append(f"Workflow not found: {workflow_id}")
            return ctx

        ctx = RunContext(workflow_id, params)
        steps = wf.get("steps", [])

        for step in steps:
            step_type = step.get("type", "skill")
            if step_type == "skill":
                await self._exec_skill(step, ctx)
            if ctx.status == "failed":
                break

        if ctx.status != "failed":
            ctx.status = "completed"
        return ctx

    async def _exec_skill(self, step: dict, ctx: RunContext) -> None:
        skill_id = step.get("skill")
        params = self._resolve_params(step.get("params", {}), ctx)
        output_key = step.get("output", step.get("id", skill_id))

        if not self._registry:
            ctx.errors.append("No registry")
            ctx.status = "failed"
            return

        result = await self._registry.invoke(skill_id, params)
        if result.success:
            ctx.set_output(output_key, result.data)
        else:
            ctx.errors.append(f"Step {step.get(\'id\')}: {result.error}")
            ctx.status = "failed"

    def _resolve_params(self, params: dict, ctx: RunContext) -> dict:
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                resolved[k] = os.environ.get(v[2:-1], "")
            elif isinstance(v, str) and "{{" in v:
                resolved[k] = self._resolve_template(v, ctx)
            else:
                resolved[k] = v
        return resolved

    def _resolve_template(self, template: str, ctx: RunContext) -> any:
        m = re.match(r"\\{\\{\\s*outputs\\.(\\w+)(?:\\.(\\w+))?\\s*\\}\\}", template)
        if m:
            key = m.group(1)
            sub = m.group(2)
            val = ctx.outputs.get(key)
            if sub and isinstance(val, dict):
                return val.get(sub)
            return val
        return template
'''

SCHED_INIT = '"""排程模組。"""\n'

SCHED_ENGINE = '''\
"""ScheduleEngine — APScheduler 排程引擎。"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


class ScheduleEngine:
    """載入排程定義，使用 APScheduler 執行。"""

    def __init__(self, workflow_engine=None):
        self._workflow_engine = workflow_engine
        self._schedules: list[dict] = []
        self._scheduler = None

    def load_schedules(self, directory: Path) -> int:
        if not directory.exists():
            return 0
        count = 0
        for f in directory.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data:
                self._schedules.append(data)
                count += 1
        return count

    def start(self) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            log.warning("apscheduler 未安裝，排程功能停用")
            return

        self._scheduler = AsyncIOScheduler()
        for sched in self._schedules:
            if not sched.get("enabled", True):
                continue
            cron = sched.get("cron", "0 9 * * *")
            parts = cron.split()
            if len(parts) >= 5:
                trigger = CronTrigger(
                    minute=parts[0], hour=parts[1],
                    day=parts[2], month=parts[3], day_of_week=parts[4],
                )
                self._scheduler.add_job(
                    self._run_workflow, trigger,
                    args=[sched.get("workflow_id", ""), sched.get("params", {})],
                    id=sched.get("id", sched.get("workflow_id")),
                )
        self._scheduler.start()
        log.info("ScheduleEngine started (%d schedules)", len(self._schedules))

    def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            log.info("ScheduleEngine stopped")

    async def _run_workflow(self, workflow_id: str, params: dict) -> None:
        if self._workflow_engine:
            ctx = await self._workflow_engine.run(workflow_id, params)
            log.info("Scheduled %s: %s", workflow_id, ctx.status)

    def list_schedules(self) -> list[dict]:
        return self._schedules
'''

HELLO_YAML = '''\
id: hello
name: Hello World 測試工作流
steps:
  - id: greet
    type: skill
    skill: echo
    params:
      message: "Hello from WorkflowEngine!"
    output: greeting
'''

DAILY_NEWS_YAML = '''\
id: daily_news
name: 科技日報產出
steps:
  - id: scrape
    type: skill
    skill: news_scraper
    params:
      url: "https://techcrunch.com/category/artificial-intelligence/"
    output: raw_html

  - id: parse
    type: skill
    skill: news_parser
    params:
      html: "{{ outputs.raw_html }}"
    output: markdown

  - id: render
    type: skill
    skill: news_renderer
    params:
      data: "{{ outputs.markdown }}"
      template: "templates/tech-daily.html"
    output: html_file
'''

SCHEDULE_YAML = '''\
id: daily_news_schedule
workflow_id: daily_news
cron: "0 9 * * *"
enabled: true
timezone: Asia/Taipei
params: {}
'''

FILES: dict[str, str] = {
    "src/workflow/__init__.py": WF_INIT,
    "src/workflow/engine.py": WF_ENGINE,
    "src/scheduler/__init__.py": SCHED_INIT,
    "src/scheduler/engine.py": SCHED_ENGINE,
    "workflows/hello.yaml": HELLO_YAML,
    "workflows/daily_news.yaml": DAILY_NEWS_YAML,
    "workflows/schedules/daily_news.yaml": SCHEDULE_YAML,
}


def scaffold(project_dir: Path) -> list[str]:
    """產出 Workflow + 排程檔案。"""
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
        print("使用方式: python scaffold_scheduler.py <project_dir>")
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
