"""Tool: execute_skill — 載入並執行 Skill。"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]


def _find_skill(name: str) -> Path | None:
    """搜尋 Skill 路徑（根 .kiro/skills/ + agents/*/. kiro/skills/）。"""
    # 根目錄 skills
    root_path = BASE_DIR / ".kiro" / "skills" / name / "SKILL.md"
    if root_path.exists():
        return root_path

    # Agent skills
    agents_dir = BASE_DIR / "agents"
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir():
                skill_path = agent_dir / ".kiro" / "skills" / name / "SKILL.md"
                if skill_path.exists():
                    return skill_path

    return None


def _list_skill_names() -> list[str]:
    """列出所有可用 Skill 名稱。"""
    names = []

    # 根目錄
    root_skills = BASE_DIR / ".kiro" / "skills"
    if root_skills.exists():
        for d in sorted(root_skills.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                names.append(d.name)

    # Agent skills
    agents_dir = BASE_DIR / "agents"
    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            if agent_dir.is_dir():
                skills_dir = agent_dir / ".kiro" / "skills"
                if skills_dir.exists():
                    for d in sorted(skills_dir.iterdir()):
                        if d.is_dir() and (d / "SKILL.md").exists():
                            if d.name not in names:
                                names.append(d.name)

    return names


async def handle_execute_skill(args: dict) -> str:
    """載入指定 Skill 的 SKILL.md 內容，回傳給 LLM 按步驟執行。"""
    name = args.get("skill_name", "").strip()
    if not name:
        return f"Error: skill_name 不能為空。可用的 Skills：{_list_skill_names()}"

    skill_path = _find_skill(name)
    if not skill_path:
        available = _list_skill_names()
        return f"Skill '{name}' 不存在。可用的 Skills：{available}"

    content = skill_path.read_text(encoding="utf-8")
    return f"## Skill: {name}\n\n以下是執行步驟，請照做：\n\n{content}"


def register_tools():
    from src.llm.tool_registry import Tool, registry

    # 取得 skills 清單作為 description 補充
    skills = _list_skill_names()
    skills_hint = f"目前可用：{', '.join(skills[:10])}" if skills else "目前無可用 Skill"

    registry.register(Tool(
        name="execute_skill",
        description=f"載入並執行指定的 Skill（SKILL.md 指令文件）。{skills_hint}",
        parameters={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Skill 名稱（如 ark-wiki-engine）",
                },
            },
            "required": ["skill_name"],
        },
        handler=handle_execute_skill,
    ))
