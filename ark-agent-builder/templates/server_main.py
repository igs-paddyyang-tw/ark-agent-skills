"""統一入口 — FastAPI + Telegram Bot + Schedule 一次啟動。"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動所有服務，shutdown 時優雅關閉。"""
    from src.skills.registry import SkillRegistry
    from src.workflow.engine import WorkflowEngine
    from src.scheduler.engine import ScheduleEngine

    registry = SkillRegistry()
    count = registry.auto_discover("src.skills.internal")
    logger.info("📦 Skills loaded: %s", count)

    wf_engine = WorkflowEngine(registry)
    wf_count = wf_engine.load_dir(Path("workflows"))
    logger.info("📋 Workflows loaded: %s", wf_count)

    schedule_engine = ScheduleEngine(wf_engine)
    sch_count = schedule_engine.load_schedules(Path("workflows/schedules"))
    schedule_engine.start()
    logger.info("⏰ Schedules loaded: %s", sch_count)

    bot_app = None
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        from src.bot.main import create_app
        bot_app = create_app(registry=registry)
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("🤖 Telegram Bot started polling")
    else:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN 未設定，Bot 不啟動")

    app.state.registry = registry
    app.state.workflow_engine = wf_engine
    app.state.schedule_engine = schedule_engine

    yield

    if bot_app:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
    schedule_engine.stop()


app = FastAPI(title="AI Agent", version="0.2.0", lifespan=lifespan)

# ── API Routes ──
from src.server.api.router import api_router  # noqa: E402
app.include_router(api_router)


# ── Page Routes ──
@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"active": "dashboard"})


@app.get("/wiki", response_class=HTMLResponse)
async def page_wiki(request: Request):
    return templates.TemplateResponse(request, "wiki.html", {"active": "wiki"})


@app.get("/schedules", response_class=HTMLResponse)
async def page_schedules(request: Request):
    return templates.TemplateResponse(request, "schedules.html", {"active": "schedules"})


@app.get("/workflows", response_class=HTMLResponse)
async def page_workflows(request: Request):
    return templates.TemplateResponse(request, "workflows.html", {"active": "workflows"})


@app.get("/skills", response_class=HTMLResponse)
async def page_skills(request: Request):
    return templates.TemplateResponse(request, "skills.html", {"active": "skills"})


@app.get("/analytics", response_class=HTMLResponse)
async def page_analytics(request: Request):
    return templates.TemplateResponse(request, "analytics.html", {"active": "analytics"})


@app.get("/sessions", response_class=HTMLResponse)
async def page_sessions(request: Request):
    return templates.TemplateResponse(request, "sessions.html", {"active": "sessions"})


@app.get("/logs", response_class=HTMLResponse)
async def page_logs(request: Request):
    return templates.TemplateResponse(request, "logs.html", {"active": "logs"})


@app.get("/config", response_class=HTMLResponse)
async def page_config(request: Request):
    return templates.TemplateResponse(request, "config.html", {"active": "config"})
