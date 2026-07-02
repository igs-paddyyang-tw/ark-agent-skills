"""FastAPI — 課程 A 簡易 API。"""
from fastapi import FastAPI
from src.skills.registry import SkillRegistry
from src.wiki.engine import WikiEngine
from pydantic import BaseModel

app = FastAPI(title="a-agent")
engine = WikiEngine()


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "a-agent"}


@app.get("/api/v1/skills")
async def list_skills():
    registry = SkillRegistry()
    registry.auto_discover("src.skills.internal")
    return {"skills": registry.list_skills()}


class QueryRequest(BaseModel):
    q: str


@app.post("/api/v1/wiki/query")
async def wiki_query(req: QueryRequest):
    result = await engine.query(req.q)
    return result


@app.post("/api/v1/wiki/ingest")
async def wiki_ingest():
    ingested = engine.ingest()
    return {"ingested": ingested, "count": len(ingested)}


@app.get("/api/v1/wiki/lint")
async def wiki_lint():
    issues = engine.lint()
    return {"issues": issues, "healthy": len(issues) == 0}
