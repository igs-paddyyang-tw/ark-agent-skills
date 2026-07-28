"""失敗模式記憶 — 追蹤重複錯誤，觸發 soft-pause / 通知。"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class FailureRecord:
    """單次失敗記錄。"""
    instance: str
    error_type: str
    message: str
    timestamp: float = field(default_factory=time.time)


class FailureMemory:
    """Per-instance 失敗模式記憶，偵測連續同類錯誤。"""

    def __init__(self, max_records: int = 10, repeat_threshold: int = 2) -> None:
        self._records: dict[str, deque[FailureRecord]] = {}
        self._max = max_records
        self._threshold = repeat_threshold

    def record(self, instance: str, error_type: str, message: str) -> bool:
        """記錄一次失敗，回傳是否觸發重複模式警告。"""
        if instance not in self._records:
            self._records[instance] = deque(maxlen=self._max)
        self._records[instance].append(
            FailureRecord(instance=instance, error_type=error_type, message=message)
        )
        return self._is_repeating(instance)

    def _is_repeating(self, instance: str) -> bool:
        """連續 N 次同類錯誤 → True。"""
        records = self._records.get(instance)
        if not records or len(records) < self._threshold:
            return False
        recent = list(records)[-self._threshold:]
        return all(r.error_type == recent[0].error_type for r in recent)

    def consecutive_count(self, instance: str) -> int:
        """目前連續同類錯誤的次數。"""
        records = self._records.get(instance)
        if not records:
            return 0
        last_type = records[-1].error_type
        count = 0
        for r in reversed(records):
            if r.error_type == last_type:
                count += 1
            else:
                break
        return count

    def clear(self, instance: str) -> None:
        """清除指定 instance 的記錄。"""
        self._records.pop(instance, None)

    def summary(self, instance: str) -> str:
        """產出一行摘要。"""
        records = list(self._records.get(instance, []))[-self._threshold:]
        if not records:
            return ""
        types = [r.error_type for r in records]
        if len(set(types)) == 1:
            return f"⚠️ {instance}: 連續 {len(records)} 次 [{types[0]}] — {records[-1].message}"
        return f"⚠️ {instance}: 最近 {len(records)} 次錯誤 — {records[-1].message}"
