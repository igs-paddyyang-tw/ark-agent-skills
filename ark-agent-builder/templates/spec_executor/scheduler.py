"""Scheduler — DAG 拓撲排序。"""
from __future__ import annotations

from collections import deque
from .parser import Task


class CyclicDependencyError(Exception):
    """環形依賴。"""


def topological_sort(tasks: list[Task]) -> list[Task]:
    """Kahn's algorithm 拓撲排序。

    回傳排序後的 task 列表（同層按原始順序）。
    Raises CyclicDependencyError if cyclic.
    """
    if not tasks:
        return []

    task_map = {t.id: t for t in tasks}
    in_degree: dict[str, int] = {t.id: 0 for t in tasks}
    adjacency: dict[str, list[str]] = {t.id: [] for t in tasks}

    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id in task_map:
                adjacency[dep_id].append(task.id)
                in_degree[task.id] += 1

    # BFS
    queue: deque[str] = deque()
    for tid, degree in in_degree.items():
        if degree == 0:
            queue.append(tid)

    result: list[Task] = []
    while queue:
        tid = queue.popleft()
        result.append(task_map[tid])
        for neighbor in adjacency[tid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(tasks):
        raise CyclicDependencyError(
            f"Cyclic dependency detected: {len(tasks)} tasks but only {len(result)} resolved"
        )

    return result
