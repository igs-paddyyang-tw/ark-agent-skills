"""Telegram handlers for memory commands: /recall, /skills, /consolidate + 審批 callback。"""
from __future__ import annotations

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# 管理者白名單（從環境變數讀取，逗號分隔）
ADMIN_CHAT_IDS: set[int] = set()
_admin_env = os.getenv("ADMIN_CHAT_IDS", "")
if _admin_env:
    ADMIN_CHAT_IDS = {int(x.strip()) for x in _admin_env.split(",") if x.strip().isdigit()}


def _get_current_agent(context: ContextTypes.DEFAULT_TYPE) -> str:
    """取得使用者目前選擇的 Agent（支援 Default 模式）。"""
    from src.agent.session import session_manager
    user_id = context._user_id if hasattr(context, '_user_id') else None
    if user_id:
        session = session_manager.get_or_create(user_id)
        if session.is_default_mode:
            return "_default"
        return (session.agent_name or "admin") + "-agent"
    agent = context.user_data.get("current_agent", "default")
    if agent == "default":
        return "_default"
    return agent + "-agent"


# ─── /recall ───

async def cmd_recall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查詢 memory FTS5 索引。用法：/recall <query>"""
    if not context.args:
        await update.message.reply_text("用法：`/recall <查詢關鍵詞>`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    agent = _get_current_agent(context)

    from src.memory.recall import recall
    results = recall(agent=agent, query=query, k=5)

    if not results:
        await update.message.reply_text(f"🔍 查無結果：`{query}`", parse_mode="Markdown")
        return

    lines = [f"🔍 **recall** `{query}` ({agent}):\n"]
    for i, r in enumerate(results, 1):
        source_emoji = {"daily": "📅", "memory": "🧠", "wiki": "📚", "skill": "⚙️"}.get(r.source, "📄")
        lines.append(f"{i}. {source_emoji} **{r.title}** ({r.date})")
        lines.append(f"   {r.body[:100]}...")
        lines.append(f"   score: {r.score:.3f}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─── /skills ───

async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """列出 skills。用法：/skills [pending]"""
    sub = context.args[0] if context.args else ""

    if sub == "pending":
        from src.memory.skill_manage import list_pending
        pending = list_pending()
        if not pending:
            await update.message.reply_text("✅ 無待審提案")
            return
        lines = ["📋 **待審提案**:\n"]
        for p in pending:
            lines.append(f"• `{p['id']}` [{p['agent']}] {p['skill_name']}")
            lines.append(f"  📎 {p['gist'][:60]}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    agent = _get_current_agent(context)
    from src.memory.skill_manage import list_skills
    skills = list_skills(agent)

    if not skills:
        await update.message.reply_text(f"⚙️ {agent} 尚無 skills")
        return

    lines = [f"⚙️ **{agent} Skills**:\n"]
    for s in skills:
        origin_mark = "🤖" if s["origin"] == "auto" else "👤"
        lines.append(f"• {origin_mark} `{s['name']}` v{s['version']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─── /consolidate ───

async def cmd_consolidate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """手動觸發 daily → memory.md 蒸餾。"""
    agent = _get_current_agent(context)
    await update.message.reply_text(f"🧠 正在蒸餾 {agent} 的記憶...")

    from src.memory.consolidate import consolidate
    result = await consolidate(agent)

    status = result.get("status", "unknown")
    if status == "updated":
        msg = f"✅ {agent} memory.md 已更新\n📏 {result['old_size']} → {result['new_size']} chars"
    elif status == "no_change":
        msg = f"ℹ️ {agent} 無新的持久事實"
    elif status == "no_data":
        msg = f"⚠️ {agent} 近 7 天無 daily log"
    else:
        msg = f"❌ 蒸餾失敗：{result.get('message', '')}"

    await update.message.reply_text(msg)


# ─── 審批推送 ───

async def send_approval_card(
    bot,
    proposal: dict,
    chat_id: int | None = None,
) -> None:
    """推送審批卡片到管理者。"""
    if chat_id is None:
        if not ADMIN_CHAT_IDS:
            log.warning("No ADMIN_CHAT_IDS configured, cannot send approval card")
            return
        chat_id = next(iter(ADMIN_CHAT_IDS))

    text = (
        f"🧩 **Skill 推薦** `{proposal['id']}` [{proposal['agent']}]\n"
        f"**{proposal['skill_name']}**\n\n"
        f"📎 {proposal['gist'][:200]}\n"
        f"📊 來源：{proposal.get('source_task', 'unknown')}\n"
        f"⏰ {proposal['created']}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 核准", callback_data=f"skill_approve:{proposal['id']}"),
            InlineKeyboardButton("❌ 駁回", callback_data=f"skill_reject:{proposal['id']}"),
        ],
    ])

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


# ─── 審批 Callback ───

async def callback_skill_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理審批 Inline Button callback。"""
    query = update.callback_query
    await query.answer()

    # 驗證管理者白名單
    user_id = query.from_user.id
    if ADMIN_CHAT_IDS and user_id not in ADMIN_CHAT_IDS:
        await query.edit_message_text("⛔ 你沒有審批權限")
        return

    data = query.data  # format: "skill_approve:{id}" or "skill_reject:{id}"
    parts = data.split(":")
    if len(parts) != 2:
        return

    action, proposal_id = parts

    if action == "skill_approve":
        from src.memory.skill_manage import approve
        result = approve(proposal_id)
        if result.get("status") == "approved":
            await query.edit_message_text(
                f"✅ 已核准 `{proposal_id}`\n📁 {result.get('skill_path', '')}",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(f"❌ 核准失敗：{result.get('message', '')}")

    elif action == "skill_reject":
        from src.memory.skill_manage import reject
        result = reject(proposal_id, reason="TG 按鈕駁回")
        await query.edit_message_text(f"❌ 已駁回 `{proposal_id}`", parse_mode="Markdown")
