"""Plan Parser — 解析 plan.md 為結構化 PlanSpec。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Task:
    """單一任務。"""
    id: str                         # "1.1"
    milestone: str                  # "M1"
    title: str                      # "DB migration"
    output_file: str                # "coordinator/db/migrations/003.sql"
    estimated: str                  # "20min"
    ac: str                         # "表建立成功"
    role: str = ""                  # "coder" (推斷或顯式)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class PlanSpec:
    """解析後的 Plan 規格。"""
    name: str                       # plan 名稱
    path: str                       # 原始檔案路徑
    milestones: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    related_spec: str | None = None
    related_design: str | None = None


def parse_plan(plan_path: Path) -> PlanSpec:
    """解析 plan.md → PlanSpec。

    支援格式：
    - frontmatter（title, related_spec, related_design）
    - ## N. M{N}：{name} 或 ## M{N}：{name}
    - | # | 任務 | 產出檔案 | 估時 | AC | 表格
    """
    content = plan_path.read_text(encoding="utf-8")

    # frontmatter
    name = _extract_frontmatter(content, "title") or plan_path.stem
    related_spec = _extract_frontmatter(content, "related_spec")
    related_design = _extract_frontmatter(content, "related_design")

    plan = PlanSpec(
        name=name,
        path=str(plan_path),
        related_spec=related_spec,
        related_design=related_design,
    )

    # 解析 milestones + tasks
    current_milestone = ""
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # 偵測 milestone 標題
        ms_match = re.match(
            r"^##\s+\d*\.?\s*M(\d+)[：:](.+?)(?:\（.*?\）)?$", line
        )
        if ms_match:
            ms_num = ms_match.group(1)
            current_milestone = f"M{ms_num}"
            if current_milestone not in plan.milestones:
                plan.milestones.append(current_milestone)
            i += 1
            continue

        # 偵測任務表格（header 行）
        if _is_task_table_header(line):
            i += 1  # skip separator ---
            if i < len(lines) and "|---" in lines[i]:
                i += 1
            # 讀取表格行
            while i < len(lines) and lines[i].strip().startswith("|"):
                task = _parse_task_row(lines[i], current_milestone)
                if task:
                    plan.tasks.append(task)
                i += 1
            continue

        i += 1

    # 推斷依賴：同 milestone 內按序號前後
    _infer_dependencies(plan.tasks)

    # 推斷角色
    for task in plan.tasks:
        if not task.role:
            task.role = _infer_role(task)

    return plan


def _extract_frontmatter(content: str, key: str) -> str | None:
    """從 frontmatter 提取欄位。"""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end < 0:
        return None
    fm = content[3:end]
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.MULTILINE)
    if m:
        val = m.group(1).strip().strip('"').strip("'")
        return val if val and val != "null" else None
    return None


def _is_task_table_header(line: str) -> bool:
    """判斷是否為任務表 header。"""
    line_lower = line.lower().strip()
    # 至少包含 # | 任務 | AC
    return (
        line_lower.startswith("|")
        and ("任務" in line_lower or "task" in line_lower)
        and ("ac" in line_lower or "驗收" in line_lower)
    )


def _parse_task_row(line: str, milestone: str) -> Task | None:
    """解析單行任務表格。"""
    cells = [c.strip() for c in line.split("|")]
    # 移除首尾空 cell（split "|...|" 會產生）
    cells = [c for c in cells if c or False]  # 保留非空

    if len(cells) < 4:
        return None

    # 嘗試匹配：# | 任務 | 產出檔案 | 估時 | AC
    task_id = cells[0].strip()
    title = cells[1].strip()
    output_file = cells[2].strip().strip("`") if len(cells) > 2 else ""
    estimated = cells[3].strip() if len(cells) > 3 else ""
    ac = cells[4].strip() if len(cells) > 4 else ""

    # 驗證 task_id 格式
    if not re.match(r"\d+\.\d+", task_id):
        return None

    return Task(
        id=task_id,
        milestone=milestone or f"M{task_id.split('.')[0]}",
        title=title,
        output_file=output_file,
        estimated=estimated,
        ac=ac,
    )


def _infer_dependencies(tasks: list[Task]) -> None:
    """推斷依賴：同 milestone 內按序號前後。"""
    by_milestone: dict[str, list[Task]] = {}
    for t in tasks:
        by_milestone.setdefault(t.milestone, []).append(t)

    for ms_tasks in by_milestone.values():
        for i, task in enumerate(ms_tasks):
            if i > 0:
                task.depends_on = [ms_tasks[i - 1].id]


def _infer_role(task: Task) -> str:
    """從 output_file 和 title 推斷角色。"""
    path = task.output_file.lower()
    title = task.title.lower()

    # 測試相關
    if "test" in path or "測試" in title or "test" in title:
        return "qa"

    # AI / 設計相關
    if any(kw in path for kw in ("design", "spec", "prompt", "llm")):
        return "ai-dev"
    if any(kw in title for kw in ("設計", "prompt", "llm", "ai", "rerank")):
        return "ai-dev"

    # 預設 coder
    return "coder"
