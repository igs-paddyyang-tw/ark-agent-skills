"""核心路徑單元測試。"""
import asyncio
import json
import tempfile
from pathlib import Path

import pytest

# ── SkillRegistry ──


def test_registry_auto_discover():
    from src.skills.registry import SkillRegistry
    reg = SkillRegistry()
    count = reg.auto_discover("src.skills.internal")
    assert count >= 9
    assert reg.get("echo") is not None


def test_registry_invoke_echo():
    from src.skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.auto_discover("src.skills.internal")
    result = asyncio.run(reg.invoke("echo", {"message": "hi"}))
    assert result.success
    assert result.data["echo"] == "hi"


def test_registry_invoke_not_found():
    from src.skills.registry import SkillRegistry
    reg = SkillRegistry()
    result = asyncio.run(reg.invoke("nonexistent", {}))
    assert not result.success
    assert "not found" in result.error


# ── WorkflowEngine ──


def test_workflow_load_and_run():
    from src.skills.registry import SkillRegistry
    from src.workflow.engine import WorkflowEngine
    reg = SkillRegistry()
    reg.auto_discover("src.skills.internal")
    engine = WorkflowEngine(reg)
    engine.load_dir(Path("workflows"))
    ctx = asyncio.run(engine.run("hello"))
    assert ctx.status.value == "completed"
    assert ctx.outputs["greeting"]["echo"] == "Hello from WorkflowEngine!"


def test_workflow_not_found():
    from src.skills.registry import SkillRegistry
    from src.workflow.engine import WorkflowEngine
    reg = SkillRegistry()
    engine = WorkflowEngine(reg)
    ctx = asyncio.run(engine.run("nonexistent_wf"))
    assert ctx.status.value == "failed"
    assert ctx.errors


def test_workflow_condition():
    from src.skills.registry import SkillRegistry
    from src.workflow.engine import WorkflowEngine, RunContext
    reg = SkillRegistry()
    reg.auto_discover("src.skills.internal")
    engine = WorkflowEngine(reg)

    # 手動建一個 condition workflow
    wf = {
        "id": "test_cond",
        "steps": [{
            "id": "check",
            "type": "condition",
            "condition": "params.get('x') == 1",
            "then": {"id": "yes", "type": "skill", "skill": "echo", "params": {"message": "YES"}, "output": "r"},
            "else": {"id": "no", "type": "skill", "skill": "echo", "params": {"message": "NO"}, "output": "r"},
        }],
    }
    engine._workflows["test_cond"] = wf
    ctx = asyncio.run(engine.run("test_cond", {"x": 1}))
    assert ctx.outputs["r"]["echo"] == "YES"


# ── MemoryStore ──


def test_memory_store_crud():
    from src.conversation.memory_store import MemoryStore
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(Path(d))
        store.update(999, "language", "繁體中文")
        store.update(999, "tech_stack", ["Python"])
        profile = store.load(999)
        assert profile["language"] == "繁體中文"
        assert profile["tech_stack"] == ["Python"]
        ctx = store.get_context_str(999)
        assert "繁體中文" in ctx


def test_memory_store_empty():
    from src.conversation.memory_store import MemoryStore
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(Path(d))
        assert store.load(123) == {}
        assert store.get_context_str(123) == ""


# ── SkillTracker ──


def test_skill_tracker_record():
    from src.skills.tracker import SkillTracker
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        p = Path(f.name)
    try:
        t = SkillTracker(p)
        t.record("test_skill", True, 0.1)
        t.record("test_skill", True, 0.2)
        t.record("test_skill", False, 0.5, "err")
        s = t.get("test_skill")
        assert s.total == 3
        assert s.success == 2
        assert s.fail == 1
        assert s.consecutive_fails == 1
    finally:
        p.unlink(missing_ok=True)


def test_skill_tracker_evolution():
    from src.skills.tracker import SkillTracker
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        p = Path(f.name)
    try:
        t = SkillTracker(p)
        for _ in range(4):
            t.record("bad_skill", False, 1.0, "always fail")
        assert t.get("bad_skill").needs_evolution()
        t.mark_evolved("bad_skill")
        assert t.get("bad_skill").consecutive_fails == 0
    finally:
        p.unlink(missing_ok=True)


# ── GrowthDetector ──


def test_growth_detector():
    from src.bot.growth import GrowthDetector
    g = GrowthDetector()
    # 清除之前的狀態
    g._patterns = {}
    assert g.record("test prompt", "code") is False
    assert g.record("test prompt", "code") is True
    s = g.get_suggestion("test prompt")
    assert s is not None
    assert s["count"] == 2
    g.clear(s["hash"])
    assert g.get_suggestion("test prompt") is None


# ── Planner ──


def test_planner_keyword_route():
    from src.conversation.planner import ConversationPlanner, PlanAction
    p = ConversationPlanner(skill_ids=["news_scraper", "llm_cli", "echo"])
    # echo 在 _QUICK_ROUTE 中
    plan = asyncio.run(p.plan("echo 測試"))
    assert plan.action == PlanAction.EXECUTE
    assert plan.skill_id == "echo"


def test_planner_command_route():
    from src.conversation.planner import ConversationPlanner, PlanAction
    p = ConversationPlanner(skill_ids=["echo", "llm_cli"])
    plan = asyncio.run(p.plan("/echo hello"))
    assert plan.action == PlanAction.EXECUTE
    assert plan.skill_id == "echo"


def test_planner_fallback_answer():
    from src.conversation.planner import ConversationPlanner, PlanAction
    p = ConversationPlanner(skill_ids=["echo"])
    plan = asyncio.run(p.plan("今天天氣如何"))
    assert plan.action == PlanAction.ANSWER
