"""Bot 指令處理 — Inline Button Agent 切換 + Memory 管理。

對話流程：
  /agents → Inline Keyboard → 選 Agent → 對話 → 自動寫 memory
"""
from __future__ import annotations

import os
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.agent.session import session_manager
from src.agent.memory import save_memory
from src.agent.cli import AVAILABLE_AGENTS, is_cli_available, agent_cli_chat

# ── 載入 SOUL（fallback 模式用）──
_SOUL_DIR = Path("agents/admin-agent/.kiro/steering")


def _load_soul(agent_id: str) -> str:
    """載入指定 Agent 的 SOUL.md。"""
    path = Path(f"agents/{agent_id}-agent/.kiro/steering/SOUL.md")
    if path.exists():
        return path.read_text(encoding="utf-8")
    # fallback 到根 .kiro/
    root_soul = Path(".kiro/steering/SOUL.md")
    return root_soul.read_text(encoding="utf-8") if root_soul.exists() else ""


# ── 指令 ─────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = session_manager.get_or_create(user_id)
    agent = AVAILABLE_AGENTS[session.current_agent]
    mode = "🧠 Agent CLI" if is_cli_available() else "⚡ Gemini API"
    await update.message.reply_text(
        f"🤖 AI Agent 已就緒！\n\n"
        f"• 模式：{mode}\n"
        f"• Agent：{agent['emoji']} {agent['name']}\n\n"
        "📌 /agents → 選擇 Agent\n"
        "💬 直接打字 → 對話\n"
        "📋 /help → 指令清單"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 指令清單：\n\n"
        "/start — 歡迎訊息\n"
        "/agents — 🔘 選擇 Agent（按鈕）\n"
        "/mode — 查看執行模式\n"
        "/history — 查看對話歷史\n"
        "/help — 本清單\n\n"
        "💬 直接輸入文字即可對話"
    )


async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """顯示 Inline Keyboard 選擇 Agent。"""
    user_id = update.effective_user.id
    session = session_manager.get_or_create(user_id)
    current = session.current_agent

    def btn(agent_id):
        info = AVAILABLE_AGENTS[agent_id]
        prefix = "→ " if current == agent_id else ""
        return InlineKeyboardButton(
            f"{prefix}{info['emoji']} {agent_id.capitalize()}",
            callback_data=f"switch_agent:{agent_id}",
        )

    keyboard = [
        [btn("admin"), btn("pm")],
        [btn("ai-dev"), btn("coder")],
        [btn("qa"), btn("data")],
        [btn("market"), btn("report")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    agent = AVAILABLE_AGENTS[current]
    await update.message.reply_text(
        f"當前：{agent['emoji']} {agent['name']}\n\n選擇要對話的 Agent：",
        reply_markup=reply_markup,
    )


async def callback_switch_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline Button 回調 — 切換 Agent。"""
    query = update.callback_query
    await query.answer()

    agent_id = query.data.split(":")[1]  # "switch_agent:news" → "news"
    user_id = query.from_user.id

    if agent_id not in AVAILABLE_AGENTS:
        await query.edit_message_text("❌ 無效的 Agent")
        return

    session = session_manager.switch_agent(user_id, agent_id)
    info = AVAILABLE_AGENTS[agent_id]
    await query.edit_message_text(
        f"✅ 已切換到 {info['emoji']} **{info['name']}**\n\n"
        f"{info['desc']}\n\n"
        f"現在開始對話吧！",
        parse_mode="Markdown",
    )


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """顯示當前執行模式。"""
    if is_cli_available():
        await update.message.reply_text(
            "🧠 **Agent CLI 模式**\n\n"
            "• kiro-cli 已安裝 ✅\n"
            "• .kiro/ 配置全部生效\n"
            "• 對話由 kiro-cli 驅動",
            parse_mode="Markdown",
        )
    else:
        has_key = "✅" if os.getenv("GEMINI_API_KEY") else "❌"
        await update.message.reply_text(
            f"⚡ **Gemini API 模式**\n\n"
            f"• Gemini Key: {has_key}\n"
            f"• SOUL.md 作為 system prompt\n\n"
            "升級：`npm i -g kiro-cli && kiro-cli login`",
            parse_mode="Markdown",
        )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """顯示近期對話歷史。"""
    user_id = update.effective_user.id
    session = session_manager.get_or_create(user_id)
    if not session.history:
        await update.message.reply_text("📭 目前沒有對話歷史")
        return
    lines = [f"📜 對話歷史（{AVAILABLE_AGENTS[session.current_agent]['emoji']} {session.current_agent}）：\n"]
    for turn in session.history[-6:]:  # 最近 6 輪
        prefix = "👤" if turn.role == "user" else "🤖"
        content = turn.content[:80] + "..." if len(turn.content) > 80 else turn.content
        lines.append(f"{prefix} {content}")
    await update.message.reply_text("\n".join(lines))


# ── 自然語言路由 ─────────────────────────────────────────


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """主對話處理：session 驅動 + 多輪記憶 + memory 寫入。"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    session = session_manager.get_or_create(user_id)
    current_agent = session.current_agent

    # 記錄 user 這輪
    session.add_turn("user", text)

    # ── 1. 關鍵字快速路由 ──
    if any(kw in text for kw in ["新聞", "news", "今天新聞"]):
        reply = await _handle_news()
        if reply:
            session.add_turn("agent", reply)
            await save_memory(current_agent, user_id, text, reply)
            await update.message.reply_text(reply, parse_mode="Markdown", disable_web_page_preview=True)
            return

    # ── 2. Agent CLI 模式 ──
    reply: str | None = None
    if is_cli_available():
        await update.message.reply_text("🧠 思考中...")
        reply = await agent_cli_chat(text, agent_id=current_agent)

    # ── 3. Gemini API fallback ──
    if not reply:
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                from src.llm.gemini_chat import gemini_chat
                soul = _load_soul(current_agent)
                # 注入對話歷史
                context_str = session.get_context()
                full_system = f"{soul}\n\n{context_str}" if context_str else soul
                reply = await gemini_chat(text, system=full_system)
            except Exception as e:
                reply = f"⚠️ 錯誤: {e}"
        else:
            reply = (
                f"🔄 echo: {text}\n\n"
                "💡 開啟 AI：填入 GEMINI_API_KEY 或安裝 kiro-cli"
            )

    # ── 4. 回覆 + 記憶 ──
    if reply:
        session.add_turn("agent", reply)
        await save_memory(current_agent, user_id, text, reply)
        await update.message.reply_text(reply)


# ── Skill 處理 ───────────────────────────────────────────


async def _handle_news() -> str | None:
    """新聞 Skill 快速路徑。"""
    try:
        from src.skills.internal.news import NewsSkill
        skill = NewsSkill()
        result = await skill.execute({"max_items": 5})
        if result.success:
            lines = [f"📰 *{result.data['source']}* — {result.data['count']} 則\n"]
            for i, art in enumerate(result.data["articles"], 1):
                lines.append(f"{i}. [{art['title']}]({art['url']}) (⬆️{art['score']})")
            return "\n".join(lines)
        return f"⚠️ {result.error}"
    except Exception as e:
        return f"⚠️ 新聞抓取失敗: {e}"
