"""ScheduleEngine — APScheduler 封裝 + YAML 排程載入。"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class ScheduleEngine:
    """排程引擎：載入 YAML 排程定義，透過 APScheduler 定時觸發 Workflow。"""

    def __init__(self, workflow_engine: WorkflowEngine) -> None:
        self._wf = workflow_engine
        self._scheduler = AsyncIOScheduler()
        self._schedules: dict[str, dict] = {}

    def load_schedules(self, dir_path: Path) -> int:
        """載入目錄下所有 .yaml 排程定義。"""
        if not dir_path.exists():
            return 0
        count = 0
        for p in dir_path.glob("*.yaml"):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                sid = data.get("id", p.stem)
                data["id"] = sid
                self._schedules[sid] = data
                if data.get("enabled", False):
                    self._add_job(data)
                count += 1
            except Exception as e:
                logger.warning("載入排程 %s 失敗: %s", p.name, e)
        return count

    def _add_job(self, schedule: dict) -> None:
        """註冊 cron job。"""
        sid = schedule["id"]
        cron_expr = schedule.get("cron", "")
        if not cron_expr:
            return
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.warning("排程 %s cron 格式錯誤: %s", sid, cron_expr)
            return

        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2],
            month=parts[3], day_of_week=parts[4],
        )
        self._scheduler.add_job(
            self._run_workflow, trigger, id=sid, replace_existing=True,
            kwargs={"schedule": schedule},
        )
        logger.info("排程已註冊: %s (%s)", sid, cron_expr)

    async def _run_workflow(self, schedule: dict) -> None:
        """排程觸發時執行對應 workflow。"""
        wf_id = schedule.get("workflow_id", "")
        raw_params = schedule.get("params", {})
        # 解析環境變數
        params = {k: os.environ.get(v[2:-1], "") if isinstance(v, str) and v.startswith("${") and v.endswith("}") else v for k, v in raw_params.items()}

        logger.info("排程觸發: %s → workflow %s", schedule["id"], wf_id)
        try:
            ctx = await self._wf.run(wf_id, params)
            if ctx.errors:
                logger.error("排程 %s 執行有錯誤: %s", schedule["id"], ctx.errors)
            else:
                logger.info("排程 %s 完成", schedule["id"])
        except Exception as e:
            logger.error("排程 %s 執行失敗: %s", schedule["id"], e)

    def start(self) -> None:
        """啟動排程器。"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("排程引擎啟動，%d 個排程已註冊", len(self._schedules))

    def stop(self) -> None:
        """停止排程器。"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("排程引擎已停止")

    def list_schedules(self) -> list[dict]:
        """列出所有排程。"""
        return [
            {"id": s["id"], "workflow_id": s.get("workflow_id", ""), "cron": s.get("cron", ""), "enabled": s.get("enabled", False)}
            for s in self._schedules.values()
        ]
