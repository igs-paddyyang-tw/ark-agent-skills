"""Reporter — 產出驗收報告。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .parser import PlanSpec
from .executor import TaskResult

log = logging.getLogger("spec_executor.reporter")

REPORTS_DIR = Path("docs/reports")


async def generate_report(plan: PlanSpec, results: list[TaskResult]) -> Path:
    """產出驗收報告 Markdown。

    Returns:
        報告檔案路徑
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 統計
    total = len(results)
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    skipped = sum(1 for r in results if r.status == "skip")
    pass_rate = round(passed / total * 100, 1) if total else 0
    total_duration = sum(r.duration_ms for r in results)
    duration_str = _format_duration(total_duration)

    # 組裝報告
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plan_name = plan.name.replace(" ", "-").lower()

    lines = [
        "---",
        f'title: "{plan.name} 驗收報告"',
        "type: report",
        f"created: {now}",
        f"plan: {plan.path}",
        "---",
        "",
        "# 驗收報告",
        "",
        "## 摘要",
        "",
        "| 指標 | 值 |",
        "|------|-----|",
        f"| 總任務 | {total} |",
        f"| 通過 | {passed} |",
        f"| 失敗 | {failed} |",
        f"| 跳過 | {skipped} |",
        f"| 通過率 | {pass_rate}% |",
        f"| 總耗時 | {duration_str} |",
        "",
        "## 任務結果",
        "",
        "| # | 任務 | 角色 | 狀態 | AC 驗證 | 耗時 | 備註 |",
        "|---|------|------|------|---------|------|------|",
    ]

    # 找到 task 對應的原始 Task 物件
    task_map = {t.id: t for t in plan.tasks}

    for r in results:
        task = task_map.get(r.task_id)
        title = task.title if task else r.task_id
        role = task.role if task else "?"
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️"}.get(r.status, "❓")
        ac_info = r.ac_detail[:40] if r.ac_detail else "—"
        duration = f"{r.duration_ms}ms" if r.duration_ms else "—"
        note = r.error[:30] if r.error else "—"

        lines.append(
            f"| {r.task_id} | {title[:30]} | {role} | {status_icon} {r.status} | {ac_info} | {duration} | {note} |"
        )

    # 未通過清單
    failed_results = [r for r in results if r.status == "fail"]
    if failed_results:
        lines.append("")
        lines.append("## 未通過清單")
        lines.append("")
        for r in failed_results:
            task = task_map.get(r.task_id)
            ac = task.ac if task else "?"
            lines.append(f"### {r.task_id} {task.title if task else ''}")
            lines.append(f"- **AC**：{ac}")
            lines.append(f"- **失敗原因**：{r.error or r.ac_detail}")
            if r.retry_count > 0:
                lines.append(f"- **重試次數**：{r.retry_count}")
            lines.append("")

    # 結論
    lines.append("")
    lines.append("## 結論")
    lines.append("")
    if pass_rate >= 90:
        lines.append(f"✅ 通過率 {pass_rate}%，品質達標。")
    elif pass_rate >= 70:
        lines.append(f"⚠️ 通過率 {pass_rate}%，需修復 {failed} 個任務。")
    else:
        lines.append(f"❌ 通過率 {pass_rate}%，需重大修復。建議對齊 spec 後重跑。")

    # 寫入
    report_path = REPORTS_DIR / f"{plan_name}-acceptance.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Report generated: %s (pass_rate=%.1f%%)", report_path, pass_rate)
    return report_path


def _format_duration(ms: int) -> str:
    """格式化毫秒為可讀字串。"""
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"
