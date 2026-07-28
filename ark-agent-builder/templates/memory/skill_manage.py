"""Skill 管理：list / approve / reject + proposals.json 狀態追蹤。"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PROPOSALS_FILE = DATA_DIR / "proposals.json"
AGENTS_DIR = BASE_DIR / "agents"

# 審批狀態
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


def _load_proposals() -> list[dict]:
    """載入 proposals.json。"""
    if not PROPOSALS_FILE.exists():
        return []
    try:
        return json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_proposals(proposals: list[dict]) -> None:
    """儲存 proposals.json。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSALS_FILE.write_text(
        json.dumps(proposals, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_skills(agent: str = "") -> list[dict]:
    """列出已生效的 skills。"""
    results = []

    def scan_agent(agent_path: Path, agent_name: str) -> None:
        skills_dir = agent_path / ".kiro" / "skills"
        if not skills_dir.exists():
            return
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            content = skill_file.read_text(encoding="utf-8")
            # 解析基本資訊
            import re
            name = skill_dir.name
            name_match = re.search(r"^name:\s*(.+)", content, re.MULTILINE)
            if name_match:
                name = name_match.group(1).strip().strip("\"'")
            version = "0.0.0"
            ver_match = re.search(r"^version:\s*(.+)", content, re.MULTILINE)
            if ver_match:
                version = ver_match.group(1).strip().strip("\"'")
            origin = "manual"
            origin_match = re.search(r"origin:\s*(.+)", content, re.MULTILINE)
            if origin_match:
                origin = origin_match.group(1).strip()

            results.append({
                "agent": agent_name,
                "name": name,
                "dir_name": skill_dir.name,
                "version": version,
                "origin": origin,
            })

    if agent:
        agent_path = AGENTS_DIR / agent
        if agent_path.exists():
            scan_agent(agent_path, agent)
    else:
        for agent_path in sorted(AGENTS_DIR.iterdir()):
            if agent_path.is_dir() and agent_path.name.endswith("-agent"):
                scan_agent(agent_path, agent_path.name)

    return results


def list_pending() -> list[dict]:
    """列出待審提案。"""
    proposals = _load_proposals()
    return [p for p in proposals if p.get("status") == STATUS_PENDING]


def create_proposal(
    agent: str,
    skill_name: str,
    skill_content: str,
    gist: str,
    source_task: str = "",
) -> dict:
    """建立新提案。"""
    proposals = _load_proposals()
    proposal_id = f"{agent[:3]}-{datetime.now().strftime('%H%M%S')}"

    proposal = {
        "id": proposal_id,
        "agent": agent,
        "skill_name": skill_name,
        "gist": gist,
        "source_task": source_task,
        "status": STATUS_PENDING,
        "created": datetime.now().isoformat(),
        "content": skill_content,
    }

    proposals.append(proposal)
    _save_proposals(proposals)
    log.info("Proposal created: %s (%s)", proposal_id, skill_name)
    return proposal


def approve(proposal_id: str) -> dict[str, Any]:
    """核准提案 → 落地到 .kiro/skills/。"""
    proposals = _load_proposals()
    proposal = next((p for p in proposals if p["id"] == proposal_id), None)

    if not proposal:
        return {"status": "error", "message": f"Proposal {proposal_id} not found"}

    if proposal["status"] != STATUS_PENDING:
        return {"status": "error", "message": f"Proposal is {proposal['status']}, not pending"}

    # 落地
    agent = proposal["agent"]
    skill_name = proposal["skill_name"]
    skill_dir = AGENTS_DIR / agent / ".kiro" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(proposal["content"], encoding="utf-8")

    # 更新狀態
    proposal["status"] = STATUS_APPROVED
    proposal["approved_at"] = datetime.now().isoformat()
    _save_proposals(proposals)

    # Git commit（best effort）
    try:
        subprocess.run(
            ["git", "add", str(skill_file)],
            cwd=str(BASE_DIR), capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", f"skill: approve {skill_name} for {agent}"],
            cwd=str(BASE_DIR), capture_output=True, timeout=10,
        )
    except Exception as e:
        log.debug("Git commit skipped: %s", e)

    # 重建索引（best effort）
    try:
        from src.memory.indexer import index_agent
        index_agent(agent)
    except Exception as e:
        log.debug("Index rebuild skipped: %s", e)

    # 通知 Agent session 重啟（讓新 Skill 生效）
    try:
        restart_flag = AGENTS_DIR / agent / "memory" / ".restart_requested"
        restart_flag.write_text(proposal_id, encoding="utf-8")
        log.info("Restart flag set for %s", agent)
    except Exception as e:
        log.debug("Restart flag skipped: %s", e)

    log.info("Approved: %s → %s", proposal_id, skill_file)
    return {"status": "approved", "skill_path": str(skill_file)}


def reject(proposal_id: str, reason: str = "") -> dict[str, Any]:
    """駁回提案。"""
    proposals = _load_proposals()
    proposal = next((p for p in proposals if p["id"] == proposal_id), None)

    if not proposal:
        return {"status": "error", "message": f"Proposal {proposal_id} not found"}

    proposal["status"] = STATUS_REJECTED
    proposal["rejected_at"] = datetime.now().isoformat()
    proposal["reject_reason"] = reason
    _save_proposals(proposals)

    # 記入 daily log（best effort）
    try:
        from src.memory.daily_log import write_daily_log
        import asyncio
        asyncio.create_task(write_daily_log(
            agent_name=proposal["agent"],
            task_id=f"reject-{proposal_id}",
            conversation=f"Skill 提案 {proposal['skill_name']} 被駁回：{reason}",
        ))
    except Exception:
        pass

    log.info("Rejected: %s (reason: %s)", proposal_id, reason)
    return {"status": "rejected", "proposal_id": proposal_id}
