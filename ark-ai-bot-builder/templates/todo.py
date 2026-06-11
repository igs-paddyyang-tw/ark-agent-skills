"""todo — 待辦清單 CRUD。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

_TODO_PATH = Path("data/todo.json")


class TodoParams(SkillParam):
    action: str = "list"  # list / add / done / remove
    text: str = ""
    index: int = 0


class TodoSkill(BaseSkill):
    skill_id = "todo"
    skill_type = SkillType.PYTHON
    description = "待辦清單管理（list/add/done/remove）"
    version = "1.0.0"
    input_schema = TodoParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = TodoParams(**params)
            todos = self._load()
            if p.action == "add":
                if not p.text:
                    return SkillResult(success=False, error="需提供 text")
                todos.append({"text": p.text, "done": False, "created": datetime.now().isoformat()})
                self._save(todos)
                return SkillResult(success=True, data={"output": f"✅ 已新增：{p.text}", "count": len(todos)})
            elif p.action == "done":
                if 0 < p.index <= len(todos):
                    todos[p.index - 1]["done"] = True
                    self._save(todos)
                    return SkillResult(success=True, data={"output": f"✅ 已完成 #{p.index}"})
                return SkillResult(success=False, error=f"無效索引：{p.index}")
            elif p.action == "remove":
                if 0 < p.index <= len(todos):
                    removed = todos.pop(p.index - 1)
                    self._save(todos)
                    return SkillResult(success=True, data={"output": f"🗑️ 已移除：{removed['text']}"})
                return SkillResult(success=False, error=f"無效索引：{p.index}")
            else:  # list
                if not todos:
                    return SkillResult(success=True, data={"output": "📋 待辦清單為空"})
                lines = []
                for i, t in enumerate(todos, 1):
                    mark = "✅" if t["done"] else "⬜"
                    lines.append(f"{mark} {i}. {t['text']}")
                return SkillResult(success=True, data={"output": "\n".join(lines), "count": len(todos)})
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def _load(self) -> list:
        if _TODO_PATH.exists():
            return json.loads(_TODO_PATH.read_text(encoding="utf-8"))
        return []

    def _save(self, todos: list) -> None:
        _TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TODO_PATH.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")
