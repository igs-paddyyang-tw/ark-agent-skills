"""scaffold_project.py — 一鍵產出 ai-bot Web 骨架 + Skill 系統。

用法：python scripts/scaffold_project.py [project_dir]
產出：31 個檔案（src/skills/ + src/server/ + tests/ + 設定檔）
"""
import sys
from pathlib import Path

FILES: dict[str, str] = {}

# ── src/__init__.py ──
FILES["src/__init__.py"] = '"""ai-bot 頂層套件。"""\n'

# ── src/skills/base.py ──
FILES["src/skills/base.py"] = '''"""BaseSkill 插件系統。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel


class SkillType(str, Enum):
    PYTHON = "python"
    LLM = "llm"
    MCP = "mcp"


class SkillParam(BaseModel):
    """Skill 輸入參數基底類別。"""
    pass


@dataclass
class SkillResult:
    """Skill 執行結果。"""
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""


class BaseSkill(ABC):
    """Skill 基底類別。"""
    skill_id: str = ""
    skill_type: SkillType = SkillType.PYTHON
    description: str = ""
    version: str = "1.0.0"
    input_schema: type[SkillParam] | None = None

    def validate_params(self, params: dict) -> bool:
        if not self.input_schema:
            return True
        try:
            self.input_schema(**params)
            return True
        except Exception:
            return False

    @abstractmethod
    async def execute(self, params: dict) -> SkillResult:
        ...

    def to_tool_definition(self) -> dict:
        schema = {}
        if self.input_schema:
            schema = self.input_schema.model_json_schema()
        return {"name": self.skill_id, "description": self.description, "parameters": schema}
'''

# ── src/skills/registry.py ──
FILES["src/skills/registry.py"] = '''"""SkillRegistry — 註冊、查詢、執行 Skills。"""

import importlib
import logging
import pkgutil
import sys
from typing import Any

from src.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> BaseSkill | None:
        return self._skills.get(skill_id)

    def list_skills(self) -> list[dict[str, Any]]:
        return [{"id": s.skill_id, "type": s.skill_type.value, "description": s.description} for s in self._skills.values()]

    async def invoke(self, skill_id: str, params: dict) -> SkillResult:
        skill = self.get(skill_id)
        if not skill:
            return SkillResult(success=False, error=f"Skill not found: {skill_id}")
        if not skill.validate_params(params):
            return SkillResult(success=False, error=f"Invalid params for skill: {skill_id}")
        try:
            return await skill.execute(params)
        except Exception as e:
            return SkillResult(success=False, error=f"Skill execution error: {e}")

    def hot_reload(self, skill_id: str) -> bool:
        module_name = f"src.skills.internal.{skill_id}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill and getattr(attr, "skill_id", ""):
                    self.register(attr())
                    return True
        except Exception as e:
            logger.error(f"Hot reload failed for {skill_id}: {e}")
        return False

    def auto_discover(self, package_name: str) -> int:
        count = 0
        try:
            pkg = importlib.import_module(package_name)
        except ImportError as e:
            logger.warning(f"Cannot import {package_name}: {e}")
            return 0
        for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
            try:
                mod = importlib.import_module(f"{package_name}.{module_name}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill and attr.skill_id:
                        self.register(attr())
                        count += 1
            except Exception as e:
                logger.warning(f"Failed to load {module_name}: {e}")
        return count
'''

# ── src/skills/__init__.py ──
FILES["src/skills/__init__.py"] = '''from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType
from src.skills.registry import SkillRegistry

__all__ = ["BaseSkill", "SkillParam", "SkillResult", "SkillType", "SkillRegistry"]
'''

# ── src/skills/internal/__init__.py ──
FILES["src/skills/internal/__init__.py"] = ""
FILES["src/skills/external/__init__.py"] = ""

# ── src/skills/internal/echo.py ──
FILES["src/skills/internal/echo.py"] = '''from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class EchoParams(SkillParam):
    """echo 輸入參數。"""
    message: str = "Hello"


class EchoSkill(BaseSkill):
    skill_id = "echo"
    skill_type = SkillType.PYTHON
    description = "回聲測試 — 回傳輸入訊息"
    version = "1.0.0"
    input_schema = EchoParams

    async def execute(self, params: dict) -> SkillResult:
        validated = EchoParams(**params)
        return SkillResult(success=True, data={"echo": validated.message})
'''

# ── src/server/__init__.py ──
FILES["src/server/__init__.py"] = ""
FILES["src/server/core/__init__.py"] = ""
FILES["src/server/api/__init__.py"] = ""

# ── src/server/main.py ──
FILES["src/server/main.py"] = '''"""FastAPI App 入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.skills.registry import SkillRegistry
from src.server.api.chat import router as chat_router

registry = SkillRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    count = registry.auto_discover("src.skills.internal")
    print(f"✅ Loaded {count} skills")
    yield


app = FastAPI(title="ai-bot", lifespan=lifespan)
app.include_router(chat_router)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "skills": len(registry.list_skills())}
'''

# ── src/server/api/chat.py ──
FILES["src/server/api/chat.py"] = '''"""Chat API。"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(req: ChatRequest):
    from src.server.main import registry
    msg = req.message.strip()
    if msg.startswith("/"):
        parts = msg[1:].split(" ", 1)
        skill_id = parts[0]
        result = await registry.invoke(skill_id, {"message": parts[1] if len(parts) > 1 else ""})
        return {"reply": result.data if result.success else result.error}
    return {"reply": msg}
'''

# ── 設定檔 ──
FILES["requirements.txt"] = """fastapi>=0.115.0
uvicorn>=0.30.0
jinja2>=3.1.0
httpx>=0.27.0
python-dotenv>=1.0.0
pydantic>=2.0.0
beautifulsoup4>=4.12.0
python-telegram-bot==21.10
pyyaml>=6.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
"""

FILES[".env.example"] = """HOST=0.0.0.0
PORT=8000
DEBUG=true
TELEGRAM_BOT_TOKEN=
GEMINI_API_KEY=
AI_BOT_WORKSPACE=.
"""

FILES[".gitignore"] = """.venv/
__pycache__/
.env
.pytest_cache/
artifacts/
data/
output/
"""

FILES["tests/__init__.py"] = ""

# ── src/server/api/health.py ──
FILES["src/server/api/health.py"] = '''"""Health API。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/v1/health")
async def health():
    return {"status": "ok"}
'''

# ── src/server/api/skills.py ──
FILES["src/server/api/skills.py"] = '''"""Skills API。"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")


class InvokeRequest(BaseModel):
    skill_id: str
    params: dict = {}


@router.get("/skills")
async def list_skills():
    from src.server.main import registry
    return {"skills": registry.list_skills()}


@router.post("/skills/invoke")
async def invoke_skill(req: InvokeRequest):
    from src.server.main import registry
    result = await registry.invoke(req.skill_id, req.params)
    return {"success": result.success, "data": result.data, "error": result.error}
'''

# ── src/server/api/router.py ──
FILES["src/server/api/router.py"] = '''"""API Router 彙整。"""

from fastapi import APIRouter
from src.server.api.health import router as health_router
from src.server.api.skills import router as skills_router
from src.server.api.chat import router as chat_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(skills_router)
api_router.include_router(chat_router)
'''

# ── src/server/core/config.py ──
FILES["src/server/core/config.py"] = '''"""Settings（python-dotenv）。"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()
'''

# ── src/server/core/errors.py ──
FILES["src/server/core/errors.py"] = '''"""自訂例外。"""


class AibiError(Exception):
    pass


class NotFoundError(AibiError):
    def __init__(self, resource: str = ""):
        super().__init__(f"Not found: {resource}")


class ValidationError(AibiError):
    def __init__(self, detail: str = ""):
        super().__init__(f"Validation error: {detail}")
'''

# ── src/server/templates/base.html ──
FILES["src/server/templates/base.html"] = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{% block title %}ai-bot{% endblock %}</title>
<link rel="stylesheet" href="/static/css/style.css?v=1">
</head>
<body>
{% block content %}{% endblock %}
<script src="/static/js/app.js?v=1"></script>
</body>
</html>
'''

# ── src/server/templates/index.html ──
FILES["src/server/templates/index.html"] = '''{% extends "base.html" %}
{% block title %}ai-bot Chat{% endblock %}
{% block content %}
<div class="chat-container">
  <header class="chat-header"><h1>🤖 ai-bot</h1><span class="status-dot"></span></header>
  <div id="messages" class="messages"></div>
  <form id="chat-form" class="input-bar">
    <input id="input" type="text" placeholder="輸入訊息..." autocomplete="off">
    <button type="submit">EXECUTE</button>
  </form>
</div>
{% endblock %}
'''

# ── src/server/static/css/style.css ──
FILES["src/server/static/css/style.css"] = '''* { box-sizing: border-box; margin: 0; padding: 0; }
:root { --bg: #0f172a; --surface: #1e293b; --text: #e2e8f0; --accent: #22d3ee; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, sans-serif; height: 100vh; display: flex; justify-content: center; }
.chat-container { width: 100%; max-width: 720px; display: flex; flex-direction: column; height: 100vh; }
.chat-header { padding: 16px; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 12px; }
.chat-header h1 { font-size: 1.2em; color: var(--accent); }
.status-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; }
.messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 8px; }
.msg { padding: 10px 14px; border-radius: 8px; max-width: 80%; }
.msg.user { background: #1d4ed8; align-self: flex-end; }
.msg.bot { background: var(--surface); align-self: flex-start; }
.input-bar { display: flex; padding: 12px; border-top: 1px solid #334155; gap: 8px; }
.input-bar input { flex: 1; background: var(--surface); border: 1px solid #475569; border-radius: 6px; padding: 10px; color: var(--text); }
.input-bar button { background: var(--accent); color: #0f172a; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; cursor: pointer; }
'''

# ── src/server/static/js/app.js ──
FILES["src/server/static/js/app.js"] = '''const form = document.getElementById("chat-form");
const input = document.getElementById("input");
const messages = document.getElementById("messages");

function addMsg(text, cls) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMsg(text, "user");
  input.value = "";
  try {
    const res = await fetch("/api/v1/chat", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: text}) });
    const data = await res.json();
    addMsg(typeof data.reply === "object" ? JSON.stringify(data.reply, null, 2) : data.reply, "bot");
  } catch (err) {
    addMsg("❌ " + err.message, "bot");
  }
});
'''

# ── tests/conftest.py ──
FILES["tests/conftest.py"] = '''"""共用 fixtures。"""
import pytest
from fastapi.testclient import TestClient
from src.server.main import app


@pytest.fixture
def client():
    return TestClient(app)
'''

# ── tests/test_health.py ──
FILES["tests/test_health.py"] = '''"""Health API 測試。"""


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
'''

# ── tests/test_skills.py ──
FILES["tests/test_skills.py"] = '''"""Skills 測試。"""
import pytest
from src.skills.registry import SkillRegistry
from src.skills.internal.echo import EchoSkill


@pytest.fixture
def registry():
    r = SkillRegistry()
    r.register(EchoSkill())
    return r


def test_register_and_get(registry):
    assert registry.get("echo") is not None


def test_list_skills(registry):
    skills = registry.list_skills()
    assert len(skills) == 1
    assert skills[0]["id"] == "echo"


@pytest.mark.asyncio
async def test_invoke(registry):
    result = await registry.invoke("echo", {"message": "hi"})
    assert result.success
    assert result.data["echo"] == "hi"
'''

# ── pytest.ini ──
FILES["pytest.ini"] = '''[pytest]
asyncio_mode = auto
testpaths = tests
'''

# ── README.md ──
FILES["README.md"] = '''# ai-bot

Gemini CLI 驅動的自進化 Telegram Bot + FastAPI 服務。

## 快速開始

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入 tokens
uvicorn src.server.main:app --reload --port 8000
```

## API

- `GET /api/v1/health` — 健康檢查
- `GET /api/v1/skills` — 列出 Skills
- `POST /api/v1/skills/invoke` — 執行 Skill
- `POST /api/v1/chat` — 對話
'''

# ── src/server/models/__init__.py ──
FILES["src/server/models/__init__.py"] = ""

# ── .kiro/ 預設配置 ──
FILES[".kiro/steering/AGENTS.md"] = '''# 全域行為準則

> 所有回覆使用**繁體中文**。

## 工具使用
- 產出檔案用 fs_write，路徑相對於專案根目錄
- 新 Skill 放入 src/skills/internal/
- 修改後確認 import 不報錯

## 回報格式

```
✅ 完成：{做了什麼}
📁 產出：{檔案路徑}
```
'''

FILES[".kiro/steering/MEMORY.md"] = '''# 🧠 專案記憶

> 每完成一個段落必須更新。

---

## 專案快照

- **專案名稱：** ai-bot
- **技術棧：** Python 3.12 / FastAPI / Telegram Bot / Gemini CLI

---

## 待辦

- [ ] 初始化完成，等待第一個任務

---

## 近期進度

（尚無）
'''

FILES[".kiro/steering/SOUL.md"] = '''# 🤖 AI Bot — 科技日報助手

> 所有回覆使用繁體中文。

## 你的身份
- 科技日報 AI Bot，能對話、產出程式碼、自動抓取新聞
- 支援 Skill 系統：使用者說需求 → 你產出 Skill → auto_discover 載入

## 核心能力
1. 自然語言對話（意圖路由）
2. 產出 BaseSkill .py 檔案（放入 src/skills/internal/）
3. 抓取新聞 → LLM 結構化 → HTML 日報
4. Workflow 排程自動化

## 產出 Skill 規則
- 繼承 BaseSkill（from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType）
- 必須有 skill_id、description、input_schema、execute
- 存放路徑：src/skills/internal/{skill_id}.py
- Python 3.12 語法、繁中 docstring
'''

FILES[".kiro/steering/USER.md"] = '''# USER.md — 使用者百科

> 由 Agent 自動整理並持續更新。

## 個人特徵與偏好

- **偏好語言：** 繁體中文
- **技術偏好：** Python / FastAPI / async
'''

FILES[".kiro/agents/ai-bot.json"] = '''{
  "name": "ai-bot",
  "description": "科技日報 AI Bot — 對話、產出 Skill、自動化新聞",
  "prompt": "file://.kiro/steering/SOUL.md",
  "model": "claude-sonnet-4",
  "tools": ["*"],
  "allowedTools": ["*"],
  "resources": [
    "file://.kiro/steering/**/*.md",
    "skill://.kiro/skills/**/SKILL.md"
  ]
}
'''

FILES[".kiro/prompts/gen-skill.md"] = '''# @gen-skill — 產出新 Skill

根據使用者需求產出 BaseSkill .py 檔案。

{{user_input}}

---

請產出：
1. SkillParam 子類別（輸入參數）
2. BaseSkill 子類別（skill_id + execute）
3. 存入 src/skills/internal/{skill_id}.py
'''

FILES[".kiro/prompts/daily-news.md"] = '''# @daily-news — 產出科技日報

執行每日新聞工作流：
1. 抓取 config/news_sources.yaml 中的來源
2. 解析為 Markdown 素材
3. LLM 結構化（topic/title/what/why/summary/tags）
4. 渲染 HTML 日報
5. 推送到 Telegram
'''

FILES[".kiro/settings/mcp.json"] = '{}\n'

FILES[".kiro/skills/.gitkeep"] = ""

# ── .agents/ 預設配置（同 .kiro/ 結構） ──
FILES[".agents/steering/AGENTS.md"] = FILES[".kiro/steering/AGENTS.md"]
FILES[".agents/steering/SOUL.md"] = FILES[".kiro/steering/SOUL.md"]
FILES[".agents/steering/MEMORY.md"] = FILES[".kiro/steering/MEMORY.md"]
FILES[".agents/agents/ai-bot.json"] = FILES[".kiro/agents/ai-bot.json"]
FILES[".agents/prompts/gen-skill.md"] = FILES[".kiro/prompts/gen-skill.md"]
FILES[".agents/prompts/daily-news.md"] = FILES[".kiro/prompts/daily-news.md"]
FILES[".agents/skills/.gitkeep"] = ""


def scaffold(project_dir: Path) -> list[str]:
    """產出所有檔案，回傳已建立的檔案路徑清單。已存在的檔案跳過不覆寫。"""
    created = []
    for rel_path, content in FILES.items():
        full = project_dir / rel_path
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        created.append(str(rel_path))
    return created


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    files = scaffold(target)
    print(f"✅ scaffold_project: 產出 {len(files)} 個檔案到 {target}")
    for f in files:
        print(f"   {f}")
