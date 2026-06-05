"""Telegram Bot handlers — 自然語言進 Agent CLI。"""
import logging
from pathlib import Path

import yaml
from telegram import Update
from telegram.ext import ContextTypes

from src.skills.registry import SkillRegistry
from src.conversation.planner import ConversationPlanner, PlanAction

logger = logging.getLogger(__name__)

# ── 載入系統提詞 ──────────────────────────────────────────────

_PROMPTS_PATH = Path(__file__).resolve().parents[2] / "config" / "llm_prompts.yaml"


def _load_prompts() -> dict[str, str]:
    defaults = {"default": "你是智能助理，用繁體中文回答。"}
    if not _PROMPTS_PATH.exists():
        return defaults
    try:
        data = yaml.safe_load(_PROMPTS_PATH.read_text(encoding="utf-8"))
        return {"default": data.get("default_system_prompt", defaults["default"]).strip()}
    except Exception:
        return defaults


_SYSTEM_PROMPTS = _load_prompts()

# ── 元件注入 ──────────────────────────────────────────────────

_registry: SkillRegistry | None = None
_planner: ConversationPlanner | None = None


def init_components(registry: SkillRegistry) -> None:
    """初始化共用元件（由 bot/main.py 呼叫）。"""
    global _registry, _planner
    _registry = registry
    _planner = ConversationPlanner(skill_ids=[s["id"] for s in registry.list_skills()])


# ── 指令 Handlers ─────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """歡迎訊息。"""
    await update.message.reply_text(
        "🤖 AI Agent Bot 就緒！\n\n"
        "直接打字跟我說話，我會用 Agent CLI 幫你做事。\n\n"
        "💡 試試看：\n"
        "• 「今天有什麼科技新聞」→ 自動抓取產日報\n"
        "• 「幫我寫一個計算機 Skill」→ 自動產出程式碼\n"
        "• 任何問題 → Agent CLI 深度回答\n\n"
        "📋 指令：\n"
        "  /daily — 手動觸發日報\n"
        "  /skills — 列出已載入 Skills"
    )


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """列出 Skills。"""
    skills = _registry.list_skills() if _registry else []
    lines = [f"📦 {len(skills)} 個 Skills\n"]
    for s in skills:
        lines.append(f"  • {s['id']} — {s['description'][:40]}")
    await update.message.reply_text("\n".join(lines))


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """手動觸發科技日報：scrape → render → 發送 HTML。"""
    if not _registry:
        await update.message.reply_text("❌ Skill 系統未就緒")
        return

    await update.message.reply_text("📡 抓取新聞中...")

    # Step 1: 抓取
    result = await _registry.invoke("news_scraper", {"config_path": "config/news_sources.yaml"})
    if not result.success:
        await update.message.reply_text(f"❌ 抓取失敗：{result.error[:200]}")
        return

    # Step 2: 整理 articles
    articles = []
    for cat, items in result.data.get("categories", {}).items():
        for item in items[:3]:
            articles.append({
                "topic": cat,
                "title": item["title"],
                "what": item.get("description", item["title"]),
                "why": "",
                "summary": item["title"][:30],
                "tags": [],
                "source": "auto",
                "emoji": "📰",
            })

    if not articles:
        await update.message.reply_text("📭 今日無新聞")
        return

    # Step 3: 渲染 HTML
    render_result = await _registry.invoke("news_renderer", {"articles": articles[:5]})
    if render_result.success:
        path = render_result.data["path"]
        await update.message.reply_document(
            document=open(path, "rb"),
            filename=Path(path).name,
            caption=f"📰 科技日報（{render_result.data.get('count', 0)} 則）",
        )
    else:
        await update.message.reply_text(f"❌ 渲染失敗：{render_result.error[:200]}")


# ── 自然語言主流程 ────────────────────────────────────────────


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """自然語言 → Planner → 做事。核心入口。"""
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()

    # 意圖路由
    plan = await _planner.plan(text)

    if plan.action == PlanAction.RESET:
        await msg.reply_text("🔄 已重置")
        return

    if plan.action == PlanAction.EXECUTE:
        # 執行 Skill
        result = await _registry.invoke(plan.skill_id, plan.params)
        if result.success:
            output = result.data.get("output") or result.data.get("code") or str(result.data)
            if len(output) > 4000:
                output = output[:3900] + "\n\n📎 已截斷"
            await msg.reply_text(output)
        else:
            await msg.reply_text(f"❌ {plan.skill_id} 失敗：{result.error[:200]}")
        return

    # ANSWER — 直接走 Agent CLI 對話
    wait_msg = await msg.reply_text("🤖 思考中...")
    result = await _registry.invoke("llm_cli", {"prompt": text, "mode": "chat"})
    if result.success:
        reply = result.data.get("output", "")
        backend = result.data.get("backend", "unknown")
        if len(reply) > 4000:
            reply = reply[:3900] + "\n\n📎 已截斷"
        reply += f"\n\n— 🤖 {backend} CLI"
        await wait_msg.edit_text(reply or "🤔 沒有回應")
    else:
        await wait_msg.edit_text(f"❌ {result.error[:300]}")
