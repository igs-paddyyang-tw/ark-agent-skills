"""任務持久化（TaskStore）— In-memory 任務狀態儲存 + 狀態機。

設計原則：
  - 純 in-memory，輕量無外部依賴
  - task_id 唯一鍵，chat_id 索引（可查某使用者最近任務）
  - 每個 TaskRecord 記錄：goal / steps / 各 step 狀態 / 時間戳
  - 自動 TTL 清理（預設 24 小時），避免無限增長

狀態機：
  planning → running → done / failed / partial

Step 狀態：
  pending → running → done / failed / skipped

使用方式：
  store = get_store()
  record = store.create(task_id="t-001", chat_id=123, goal="做某事", step_labels=["步驟1", "步驟2"])
  store.update_step(task_id="t-001", step_idx=0, status="running")
  store.update_step(task_id="t-001", step_idx=0, status="done")
  store.update_status(task_id="t-001", status="done")
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

# TTL：task 保留時間（秒），超過自動清理
TASK_TTL_SEC = 86400  # 24 小時


@dataclass
class StepRecord:
    """單一步驟的狀態紀錄。"""
    label: str                    # 步驟描述（建議截斷 50 字）
    status: str = "pending"       # pending | running | done | failed | skipped
    started_at: float = 0.0
    ended_at: float = 0.0

    @property
    def elapsed_sec(self) -> int:
        """已執行秒數（running 時為即時計算）。"""
        if self.status == "running" and self.started_at:
            return int(time.monotonic() - self.started_at)
        if self.ended_at and self.started_at:
            return int(self.ended_at - self.started_at)
        return 0

    @property
    def icon(self) -> str:
        """狀態圖示。"""
        return {
            "pending": "⬜", "running": "⏳", "done": "✅",
            "failed": "❌", "skipped": "⏭",
        }.get(self.status, "❓")


@dataclass
class TaskRecord:
    """單一任務的完整紀錄。"""
    task_id: str
    chat_id: int
    goal: str
    steps: list[StepRecord] = field(default_factory=list)
    status: str = "planning"      # planning | running | done | failed | partial
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    current_step_idx: int = -1    # 目前執行中的 step index（-1 = 尚未開始）

    def touch(self) -> None:
        """更新 updated_at 時間戳。"""
        self.updated_at = time.time()

    @property
    def short_id(self) -> str:
        """取 task_id 後 6 碼作為顯示用短 ID。"""
        return self.task_id[-6:] if len(self.task_id) >= 6 else self.task_id

    @property
    def updated_ago_sec(self) -> int:
        """距離上次更新的秒數。"""
        return int(time.time() - self.updated_at)

    def render(self) -> str:
        """渲染人類可讀的任務狀態報告（零 LLM、純模板）。"""
        status_label = {
            "planning": "規劃中", "running": "執行中",
            "done": "已完成", "failed": "失敗", "partial": "部分完成",
        }.get(self.status, self.status)

        goal_short = self.goal[:40] + ("…" if len(self.goal) > 40 else "")
        lines = [f"📋 任務 #{self.short_id}（{goal_short}）"]
        lines.append(f"狀態：{status_label}")

        if self.steps:
            done_count = sum(1 for s in self.steps if s.status == "done")
            total = len(self.steps)
            if self.status == "running":
                lines[-1] += f"（Step {done_count + 1}/{total}）"

            for i, step in enumerate(self.steps):
                prefix = "├" if i < len(self.steps) - 1 else "└"
                suffix = ""
                if step.status == "running" and step.elapsed_sec > 0:
                    suffix = f"（已執行 {step.elapsed_sec}s）"
                lines.append(f"{prefix} {step.icon} {step.label[:40]}{suffix}")

        # 最後更新時間
        ago = self.updated_ago_sec
        if ago < 60:
            ago_str = f"{ago} 秒前"
        elif ago < 3600:
            ago_str = f"{ago // 60} 分鐘前"
        else:
            ago_str = f"{ago // 3600} 小時前"
        lines.append(f"最後更新：{ago_str}")

        return "\n".join(lines)


class TaskStore:
    """In-memory 任務狀態儲存。

    Thread-safe 不保證（設計為單 event loop 使用）。
    若需跨進程共享，可替換為 SQLite / Redis 實作。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}       # task_id → TaskRecord
        self._chat_tasks: dict[int, list[str]] = {}   # chat_id → [task_id]（最新在後）

    # ── 寫入 ─────────────────────────────────────────────

    def create(
        self,
        task_id: str,
        chat_id: int,
        goal: str,
        step_labels: list[str] | None = None,
    ) -> TaskRecord:
        """建立新 task 記錄。"""
        self._evict()
        record = TaskRecord(
            task_id=task_id,
            chat_id=chat_id,
            goal=goal,
            steps=[StepRecord(label=lbl) for lbl in (step_labels or [])],
        )
        self._tasks[task_id] = record
        self._chat_tasks.setdefault(chat_id, []).append(task_id)
        return record

    def update_status(self, task_id: str, status: str) -> None:
        """更新 task 整體狀態。"""
        if rec := self._tasks.get(task_id):
            rec.status = status
            rec.touch()

    def update_step(
        self,
        task_id: str,
        step_idx: int,
        status: str,
        label: str | None = None,
    ) -> None:
        """更新指定 step 狀態（自動擴充 steps 列表）。"""
        rec = self._tasks.get(task_id)
        if not rec:
            return
        # 自動擴充
        while len(rec.steps) <= step_idx:
            rec.steps.append(StepRecord(label=f"Step {len(rec.steps) + 1}"))
        step = rec.steps[step_idx]
        if label:
            step.label = label[:50]
        old_status = step.status
        step.status = status
        if status == "running" and old_status != "running":
            step.started_at = time.monotonic()
            rec.current_step_idx = step_idx
        elif status in ("done", "failed", "skipped") and step.started_at:
            step.ended_at = time.monotonic()
        rec.touch()

    def set_steps(self, task_id: str, labels: list[str]) -> None:
        """設定完整步驟列表（Plan 完成後呼叫）。保留已存在 step 的狀態。"""
        if rec := self._tasks.get(task_id):
            existing = {s.label: s for s in rec.steps}
            rec.steps = [existing.get(lbl, StepRecord(label=lbl)) for lbl in labels]
            rec.touch()

    # ── 查詢 ─────────────────────────────────────────────

    def get(self, task_id: str) -> Optional[TaskRecord]:
        """以 task_id 查詢。"""
        return self._tasks.get(task_id)

    def get_latest(self, chat_id: int) -> Optional[TaskRecord]:
        """取某 chat 最新的 task（無論狀態）。"""
        self._evict()
        task_ids = self._chat_tasks.get(chat_id, [])
        for tid in reversed(task_ids):
            if rec := self._tasks.get(tid):
                return rec
        return None

    def get_running(self, chat_id: int) -> list[TaskRecord]:
        """取某 chat 所有執行中的 task。"""
        return [
            rec for tid in self._chat_tasks.get(chat_id, [])
            if (rec := self._tasks.get(tid)) and rec.status in ("planning", "running")
        ]

    # ── TTL 清理 ─────────────────────────────────────────

    def _evict(self) -> None:
        """清理超過 TTL 的過期 task。"""
        cutoff = time.time() - TASK_TTL_SEC
        expired = [tid for tid, rec in self._tasks.items() if rec.updated_at < cutoff]
        for tid in expired:
            rec = self._tasks.pop(tid, None)
            if rec:
                ids = self._chat_tasks.get(rec.chat_id, [])
                if tid in ids:
                    ids.remove(tid)


# ── 模組級單例 ────────────────────────────────────────────

_store: TaskStore | None = None


def get_store() -> TaskStore:
    """取得全域 TaskStore 單例。"""
    global _store
    if _store is None:
        _store = TaskStore()
    return _store
