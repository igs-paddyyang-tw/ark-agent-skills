"""Memory API 端點：/api/v1/memory/* + /api/v1/skills/*"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.memory.recall import recall
from src.memory.indexer import rebuild_all, index_agent

router = APIRouter(prefix="/api/v1", tags=["memory"])


# ─── Request Models ───

class RecallRequest(BaseModel):
    agent: str
    query: str
    k: int = 5


class ConsolidateRequest(BaseModel):
    agent: str


class ApproveRequest(BaseModel):
    proposal_id: str


class RejectRequest(BaseModel):
    proposal_id: str
    reason: str = ""


# ─── Memory Endpoints ───

@router.post("/memory/recall")
async def api_recall(req: RecallRequest):
    """查詢記憶 FTS5 索引。"""
    results = recall(agent=req.agent, query=req.query, k=req.k)
    return {"results": [r.to_dict() for r in results]}


@router.get("/memory/daily")
async def api_daily(agent: str, date: str = ""):
    """取得 daily log。"""
    from pathlib import Path
    from datetime import datetime

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    daily_file = Path(f"agents/{agent}/memory/daily/{date}.md")
    if not daily_file.exists():
        return {"entries": [], "date": date}

    content = daily_file.read_text(encoding="utf-8")
    return {"entries": [content], "date": date}


@router.post("/memory/consolidate")
async def api_consolidate(req: ConsolidateRequest):
    """手動觸發 daily → memory.md 蒸餾。"""
    from src.memory.consolidate import consolidate
    result = await consolidate(req.agent)
    return result


@router.post("/memory/rebuild-index")
async def api_rebuild_index():
    """完整重建 memory FTS5 索引。"""
    results = rebuild_all()
    return {"status": "ok", "results": results}


# ─── Skills Endpoints ───

@router.get("/skills/list")
async def api_skills_list(agent: str = ""):
    """列出 skills。"""
    from src.memory.skill_manage import list_skills
    skills = list_skills(agent)
    return {"skills": skills}


@router.get("/skills/pending")
async def api_skills_pending():
    """待審清單。"""
    from src.memory.skill_manage import list_pending
    proposals = list_pending()
    return {"proposals": proposals}


@router.post("/skills/approve")
async def api_skills_approve(req: ApproveRequest):
    """核准提案。"""
    from src.memory.skill_manage import approve
    result = approve(req.proposal_id)
    return result


@router.post("/skills/reject")
async def api_skills_reject(req: RejectRequest):
    """駁回提案。"""
    from src.memory.skill_manage import reject
    result = reject(req.proposal_id, req.reason)
    return result
