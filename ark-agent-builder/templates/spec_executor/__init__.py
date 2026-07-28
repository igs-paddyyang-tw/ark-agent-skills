"""ark-spec-executor — 讀取 plan.md，自動拆解→角色切換執行→AC 驗收→報告。"""
from __future__ import annotations

from src.skills.base import BaseSkill, SkillResult, SkillType


class SpecExecutorSkill(BaseSkill):
    skill_id = "spec_executor"
    skill_type = SkillType.PYTHON
    description = "讀取 plan.md，自動拆解→角色切換執行→AC 驗收→產出驗收報告"
    version = "1.0.0"

    async def execute(self, params: dict) -> SkillResult:
        from pathlib import Path
        from .parser import parse_plan
        from .scheduler import topological_sort
        from .executor import run_plan
        from .reporter import generate_report

        plan_path = params.get("plan_path", "")
        if not plan_path:
            return SkillResult(success=False, error="Missing plan_path")

        path = Path(plan_path)
        if not path.exists():
            return SkillResult(success=False, error=f"Plan not found: {plan_path}")

        plan = parse_plan(path)
        if not plan.tasks:
            return SkillResult(success=False, error="No tasks found in plan")

        if params.get("dry_run", False):
            return SkillResult(success=True, data={
                "name": plan.name,
                "milestones": plan.milestones,
                "task_count": len(plan.tasks),
                "tasks": [{"id": t.id, "title": t.title, "role": t.role} for t in plan.tasks],
            })

        ordered = topological_sort(plan.tasks)
        milestone_filter = params.get("milestone")
        if milestone_filter:
            ordered = [t for t in ordered if t.milestone == milestone_filter]

        results = await run_plan(plan, ordered, resume=params.get("resume", True))
        report_path = await generate_report(plan, results)

        pass_count = sum(1 for r in results if r.status == "pass")
        total = len(results)

        return SkillResult(success=True, data={
            "report_path": str(report_path),
            "total": total,
            "passed": pass_count,
            "failed": sum(1 for r in results if r.status == "fail"),
            "pass_rate": round(pass_count / total * 100, 1) if total else 0,
        })
