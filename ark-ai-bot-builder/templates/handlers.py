"""Telegram Bot handlers — 雙模式：預設 Agent CLI + /chat Chatbot。"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.skills.registry import SkillRegistry
from src.conversation.planner import ConversationPlanner, PlanAction

logger = logging.getLogger(__name__)

# ── 載入系統提詞 ──────────────────────────────────────────────

_PROMPTS_PATH = Path(__file__).resolve().parents[2] / "config" / "llm_prompts.yaml"


def _load_prompts() -> dict[str, str]:
    defaults = {"default": "你是智能助理，用繁體中文回答。簡潔有用。"}
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
    await update.message.reply_text(
        "🤖 AI Agent Bot 就緒！\n\n"
        "💬 **兩種模式：**\n\n"
        "🔹 **預設 — Agent CLI 模式**\n"
        "  直接打字 → Kiro CLI 深度回答（8-30s）\n"
        "  具備完整 context、檔案操作、工具呼叫\n\n"
        "🔸 **/chat — Chatbot 模式**\n"
        "  /chat 問題 → Gemini + Skill 快速回應（1-5s）\n"
        "  意圖路由 + 記憶 + 本地 Skill 執行\n\n"
        "📋 其他指令：\n"
        "  /daily — 科技日報\n"
        "  /skills — 列出 Skills\n"
        "  /help — 模式說明",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 **模式說明**\n\n"
        "**Agent CLI（預設）**— 直接打字\n"
        "• 走 kiro-cli chat，有完整 .kiro/ context\n"
        "• 可讀寫檔案、搜尋、深度推理\n"
        "• 延遲 8-30 秒\n\n"
        "**/chat — Chatbot 模式**\n"
        "• 走 Gemini API + Planner + Skill\n"
        "• 關鍵字自動觸發 Skill（日報/程式碼）\n"
        "• 延遲 1-5 秒\n\n"
        "**硬指令：**\n"
        "/daily — 產出科技日報\n"
        "/skills — 列出 Skills\n"
        "/chat — Chatbot 快速模式",
        parse_mode="Markdown",
    )


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    skills = _registry.list_skills() if _registry else []
    from src.skills.tracker import SkillTracker
    tracker = SkillTracker()
    stats_map = {s["id"]: s for s in tracker.summary()}
    lines = [f"📦 {len(skills)} 個 Skills\n"]
    for s in skills:
        sid = s["id"]
        st = stats_map.get(sid)
        if st:
            lines.append(f"  • {sid} — {st['success_rate']}% ({st['total']}次)")
        else:
            lines.append(f"  • {sid} — {s['description'][:30]}")
    await update.message.reply_text("\n".join(lines))


async def cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """顯示今日 API 使用量 + 7 天趨勢 + 費用估算。"""
    from src.bot.utils import TraceLogger
    tracer = TraceLogger()
    usage = tracer.get_today_usage()

    # 7 天趨勢
    from datetime import datetime, timedelta
    trend_bars = ""
    max_calls = 1
    week_data = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        day_path = tracer.DIR / f"{day}.jsonl"
        calls = 0
        if day_path.exists():
            calls = sum(1 for l in day_path.read_text(encoding="utf-8").splitlines() if l.strip())
        week_data.append(calls)
        max_calls = max(max_calls, calls)
    bars = "▁▂▃▄▅▆▇█"
    trend_bars = "".join(bars[min(int(c / max_calls * 7), 7)] if c else "▁" for c in week_data)

    # per-backend 費用估算
    cost_lines = ""
    if usage["calls"] > 0:
        # 從今日 trace 統計 backend 分佈
        import json
        today_path = tracer.DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        backends: dict[str, int] = {}
        if today_path.exists():
            for line in today_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    b = entry.get("backend", "unknown")
                    backends[b] = backends.get(b, 0) + entry.get("tokens_est", 0)
        rates = {"kiro": 0, "gemini": 0.00015, "gemini-api": 0.00015, "openai": 0.002}
        total_cost = sum(tokens / 1000 * rates.get(b, 0) for b, tokens in backends.items())
        cost_lines = f"\n💰 估算費用：${total_cost:.4f}"
        for b, tokens in backends.items():
            cost_lines += f"\n  • {b}: {tokens:,} tok"

    await update.message.reply_text(
        f"📊 今日用量\n\n"
        f"  呼叫次數：{usage['calls']}\n"
        f"  預估 tokens：{usage['tokens_est']:,}\n"
        f"  總耗時：{usage['total_duration']}s\n\n"
        f"📈 7 天趨勢：{trend_bars}"
        f"{cost_lines}"
    )


async def cmd_trace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """顯示最近 5 次呼叫軌跡。"""
    from src.bot.utils import TraceLogger
    recent = TraceLogger().get_recent(5)
    if not recent:
        await update.message.reply_text("📋 今日無呼叫紀錄")
        return
    lines = ["📋 最近呼叫：\n"]
    for r in reversed(recent):
        status = "✅" if r["success"] else "❌"
        lines.append(f"  {status} {r['mode']} | {r['backend']} | {r['duration_s']}s | ~{r['tokens_est']}tok")
    await update.message.reply_text("\n".join(lines))


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """知識庫問答：/ask 無參數列目錄，有參數則搜尋。"""
    query = " ".join(context.args) if context.args else ""
    if not _registry:
        await update.message.reply_text("❌ 系統未就緒")
        return

    action = "list" if not query else "search"
    result = await _registry.invoke("wiki_query", {"query": query, "action": action})
    if result.success:
        output = result.data.get("output", "（無結果）")
        if len(output) > 4000:
            from src.bot.utils import split_message
            for chunk in split_message(output):
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(output)
    else:
        await update.message.reply_text(f"❌ {result.error[:200]}")


async def cmd_wiki(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """知識庫查詢：/wiki 關鍵字 或 /wiki list 或 /wiki distill。"""
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("用法：`/wiki 關鍵字` 或 `/wiki list` 或 `/wiki distill`", parse_mode="Markdown")
        return
    if not _registry:
        await update.message.reply_text("❌ 系統未就緒")
        return

    cmd = text.strip().lower()
    if cmd == "distill":
        await update.message.reply_text("🧪 開始蒸餾 raw/ → wiki/（kiro-cli，約 1-5 分鐘）...")
        result = await _registry.invoke("wiki_distill", {"timeout": 300})
        if result.success:
            await update.message.reply_text(result.data.get("output", "✅ 完成"))
        else:
            await update.message.reply_text(f"❌ {result.error[:200]}")
        return

    action = "list" if cmd == "list" else "search"
    result = await _registry.invoke("wiki_query", {"query": text, "action": action})
    if result.success:
        output = result.data.get("output", "")
        if len(output) > 4000:
            from src.bot.utils import split_message
            chunks = split_message(output)
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(output)
    else:
        await update.message.reply_text(f"❌ {result.error[:200]}")


# ── Codegen Prompt 模板 ───────────────────────────────────────

_SKILL_PROMPT = """產出 Python Skill。嚴格遵守以下規則：
- from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType
- skill_id 用英文 snake_case（從需求推導，簡短）
- 必須有 class XxxParams(SkillParam) 作為 input_schema
- 必須有 async def execute(self, params: dict) -> SkillResult
- 主邏輯用 try/except 包裹，失敗回 SkillResult(success=False, error=str(e))
- 可用套件：標準庫 + httpx + beautifulsoup4 + pathlib + re + json
- 檔案輸出路徑用 output/{{skill_id}}/ 目錄
- 繁體中文 docstring
只輸出程式碼，不要解釋。

需求：{prompt}"""

_WORKFLOW_PROMPT = """產出 YAML 工作流。格式：
id: workflow_id_snake_case
name: 工作流名稱
steps:
  - id: step1
    type: skill
    skill: skill_id
    params:
      key: "值或 {{{{ outputs.prev.field }}}}"
    output: step1_result
  - id: step2
    type: skill
    skill: another_skill_id
    params:
      input_path: "{{{{ outputs.step1_result.path }}}}"
    output: step2_result

可用 Skills：{skill_list}
只輸出 YAML，不要解釋。

需求：{prompt}"""

_WORKFLOW_KEYWORDS = ["串成工作流", "組成流程", "workflow", "組合", "串接", "工作流"]


# ── _codegen_and_register ─────────────────────────────────────


async def _codegen_and_register(prompt: str, update: Update) -> None:
    """Gemini 產出 Skill → compile 驗證 → 存檔 → hot_reload。"""
    import re as _re
    from src.llm.gemini_chat import chat

    await update.message.reply_text("⚙️ 產出 Skill 中...")

    code_raw = await chat(_SKILL_PROMPT.format(prompt=prompt))
    code = _extract_code_block(code_raw)

    # 提取 skill_id
    m = _re.search(r'skill_id\s*[=:]\s*["\'](\w+)["\']', code)
    if not m:
        await update.message.reply_text("❌ 無法從產出中提取 skill_id，請重試")
        return
    skill_id = m.group(1)

    # compile 驗證
    try:
        compile(code, f"{skill_id}.py", "exec")
    except SyntaxError as e:
        await update.message.reply_text(f"❌ 語法錯誤：{e.msg} (line {e.lineno})\n請重新描述需求")
        return

    # 衝突檢查
    if _registry.get(skill_id):
        skill_id = f"{skill_id}_v2"
        code = code.replace(m.group(0), f'skill_id = "{skill_id}"', 1)

    # 存檔
    path = Path(f"src/skills/internal/{skill_id}.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")

    # hot_reload
    success = _registry.hot_reload(skill_id)
    if not success:
        await update.message.reply_text(f"⚠️ 檔案已存但載入失敗，請檢查 `{path}`")
        return

    _planner.set_skills([s["id"] for s in _registry.list_skills()])

    await update.message.reply_text(
        f"✅ 已建立 `{skill_id}` Skill\n"
        f"📁 `{path}`\n\n"
        f"💡 使用：`/chat /{skill_id} 參數`",
        parse_mode="Markdown",
    )


# ── _workflow_gen ─────────────────────────────────────────────


async def _workflow_gen(prompt: str, update: Update) -> None:
    """Gemini 產出 Workflow YAML → 驗證 → 存檔。"""
    from src.llm.gemini_chat import chat

    await update.message.reply_text("⚙️ 產出工作流中...")

    skill_list = ", ".join(s["id"] for s in _registry.list_skills())
    yaml_raw = await chat(_WORKFLOW_PROMPT.format(prompt=prompt, skill_list=skill_list))
    yaml_str = _extract_code_block(yaml_raw) or yaml_raw

    try:
        data = yaml.safe_load(yaml_str)
        wf_id = data.get("id", "generated_workflow")
    except Exception as e:
        await update.message.reply_text(f"❌ YAML 解析失敗：{e}")
        return

    path = Path(f"workflows/{wf_id}.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_str, encoding="utf-8")

    steps = data.get("steps", [])
    step_list = "\n".join(f"  {i+1}. `{s.get('skill', '?')}`" for i, s in enumerate(steps))
    await update.message.reply_text(
        f"✅ 已建立工作流 `{wf_id}`\n"
        f"📁 `{path}`\n"
        f"📋 步驟：\n{step_list}\n\n"
        f"💡 執行：`/chat /run {wf_id}`",
        parse_mode="Markdown",
    )


# ── 工具函式 ──────────────────────────────────────────────────


def _extract_code_block(text: str) -> str:
    """從 LLM 回應中提取 code block。"""
    import re as _re
    m = _re.search(r"```(?:python|yaml|yml)?\n(.*?)```", text, _re.DOTALL)
    return m.group(1).strip() if m else text.strip()


# ── /chat — Chatbot 模式（Gemini + Planner + Skill + Memory）──


async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Chatbot 模式：Gemini API + Planner 意圖路由 + Skill 執行。"""
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("用法：`/chat 你的問題`", parse_mode="Markdown")
        return

    if not _registry or not _planner:
        await update.message.reply_text("❌ 系統未就緒")
        return

    # 優先：工作流產出
    if any(kw in text for kw in _WORKFLOW_KEYWORDS):
        await _workflow_gen(text, update)
        return

    # Planner 意圖路由
    plan = await _planner.plan(text)

    if plan.action == PlanAction.EXECUTE:
        if plan.skill_id == "llm_cli" and plan.params.get("mode") == "codegen":
            # codegen → 產出 Skill 並掛載
            await _codegen_and_register(plan.params.get("prompt", text), update)
            return
        # 其他 Skill 正常 invoke
        result = await _registry.invoke(plan.skill_id, plan.params)
        if result.success:
            output = result.data.get("output") or result.data.get("code") or result.data.get("path") or str(result.data)
            if len(output) > 4000:
                output = output[:3900] + "\n\n📎 已截斷"
            await update.message.reply_text(f"⚡ {output}")
        else:
            await update.message.reply_text(f"❌ {plan.skill_id}：{result.error[:200]}")
        return

    # ANSWER — Gemini API 對話（快速）
    try:
        from src.llm.gemini_chat import chat, is_available
        if is_available():
            reply = await chat(text, _SYSTEM_PROMPTS["default"])
            if len(reply) > 4000:
                reply = reply[:3900] + "\n\n📎 已截斷"
            await update.message.reply_text(reply)
            return
    except Exception:
        pass

    # Fallback: 走 Agent CLI
    result = await _registry.invoke("llm_cli", {"prompt": text, "mode": "chat", "user_id": update.effective_user.id})
    if result.success:
        await update.message.reply_text(result.data.get("output", "🤔"))
    else:
        await update.message.reply_text(f"❌ {result.error[:200]}")


# ── /daily — 科技日報 ─────────────────────────────────────────


async def _translate_articles(articles: list) -> list:
    """用 Gemini API 翻譯英文標題為繁體中文。"""
    try:
        from src.llm.gemini_chat import chat, is_available
        if not is_available():
            return articles
        titles = [a["title"] for a in articles]
        prompt = (
            "將以下英文新聞標題翻譯為繁體中文，每行一個，保持順序，只輸出翻譯結果：\n"
            + "\n".join(titles)
        )
        result = await chat(prompt)
        lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
        for i, art in enumerate(articles):
            if i < len(lines) and lines[i]:
                art["title"] = lines[i]
                art["what"] = lines[i]
                art["summary"] = lines[i][:30]
    except Exception:
        pass
    return articles


async def _generate_article_images(articles: list) -> list:
    """用 Gemini 為每篇文章產 SVG 配圖（輕量、內嵌友好）。"""
    try:
        from src.llm.gemini_chat import chat, is_available
        if not is_available():
            return articles
        for art in articles:
            try:
                prompt = (
                    f"產出一個 300x300 的 SVG 插圖，主題：{art['title']}。"
                    f"風格：扁平化科技風、簡約幾何圖形、3-4 色、無文字。"
                    f"只輸出 <svg>...</svg> 標籤，不要任何解釋。"
                )
                svg = await chat(prompt)
                # 提取 <svg>...</svg>
                import re
                m = re.search(r'(<svg[\s\S]*?</svg>)', svg)
                if m:
                    import base64
                    svg_data = m.group(1)
                    b64 = base64.b64encode(svg_data.encode()).decode()
                    art["img"] = f"data:image/svg+xml;base64,{b64}"
            except Exception:
                pass
    except Exception:
        pass
    return articles


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """科技日報：scrape → translate → render → 發送。"""
    if not _registry:
        await update.message.reply_text("❌ Skill 系統未就緒")
        return

    await update.message.reply_text("📡 抓取新聞中...")

    result = await _registry.invoke("news_scraper", {"config_path": "config/news_sources.yaml"})
    if not result.success:
        await update.message.reply_text(f"❌ 抓取失敗：{result.error[:200]}")
        return

    articles = []
    for cat, items in result.data.get("categories", {}).items():
        for item in items[:3]:
            articles.append({
                "topic": cat, "title": item["title"],
                "what": item.get("description", item["title"]),
                "why": "", "summary": item["title"][:30],
                "tags": [], "source": "auto",
            })

    if not articles:
        await update.message.reply_text("📭 今日無新聞")
        return

    articles = await _translate_articles(articles[:5])
    articles = await _generate_article_images(articles)

    render_result = await _registry.invoke("news_renderer", {"articles": articles[:5]})
    if render_result.success:
        path = render_result.data["path"]
        await update.message.reply_document(
            document=open(path, "rb"),
            filename=Path(path).name,
            caption=f"📰 科技日報（{render_result.data.get('count', 0)} 則）",
            read_timeout=60, write_timeout=60,
        )
    else:
        await update.message.reply_text(f"❌ 渲染失敗：{render_result.error[:200]}")


# ── Callback Handler（InlineKeyboard 回調）────────────────────


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 InlineKeyboard 按鈕回調。"""
    query = update.callback_query
    await query.answer()

    if query.data == "dismiss":
        await query.message.delete()
        return

    if query.data == "mem_save":
        from src.conversation.memory_store import MemoryStore
        updates = context.user_data.get("_pending_memory", {})
        uid = context.user_data.get("_pending_memory_uid", 0)
        if updates and uid:
            store = MemoryStore()
            for k, v in updates.items():
                store.update(uid, k, v)
            try:
                await query.message.edit_text("✅ 已記住你的偏好！")
            except Exception:
                pass
        else:
            try:
                await query.message.edit_text("⚠️ 無待儲存的偏好")
            except Exception:
                pass
        return

    if query.data.startswith("save_skill:"):
        # 從 user_data 取最後的 code reply
        code_reply = context.user_data.get("last_code_reply", "")
        prompt = context.user_data.get("last_prompt", "")
        if not code_reply:
            try:
                await query.message.edit_text("⚠️ 找不到程式碼內容")
            except Exception:
                pass
            return
        try:
            await query.message.edit_text("⚙️ 正在轉換為 Skill...")
        except Exception:
            pass
        await _codegen_and_register(prompt, update)


# ── Auto Fix Skill ────────────────────────────────────────────


async def _auto_fix_skill(skill_id: str, error: str, params: dict) -> bool:
    """Gemini 分析錯誤 → 修正 Skill → hot_reload → 回傳是否成功。"""
    try:
        from src.llm.gemini_chat import chat, is_available
        if not is_available():
            return False
        path = Path(f"src/skills/internal/{skill_id}.py")
        if not path.exists():
            return False
        code = path.read_text(encoding="utf-8")
        fix_prompt = (
            f"修正以下 Python Skill 的錯誤，只輸出修正後的完整程式碼。\n"
            f"錯誤訊息：{error[:200]}\n"
            f"呼叫參數：{params}\n"
            f"程式碼：\n```python\n{code}\n```"
        )
        fixed_raw = await chat(fix_prompt)
        fixed = _extract_code_block(fixed_raw)
        # 驗證
        compile(fixed, f"{skill_id}.py", "exec")
        path.write_text(fixed, encoding="utf-8")
        return _registry.hot_reload(skill_id)
    except Exception:
        return False


async def _evolve_skill(skill_id: str) -> bool:
    """Skill 演化：LLM 完整重寫（不只 patch）。"""
    try:
        from src.llm.gemini_chat import chat, is_available
        from src.skills.tracker import SkillTracker
        if not is_available():
            return False
        path = Path(f"src/skills/internal/{skill_id}.py")
        if not path.exists():
            return False
        code = path.read_text(encoding="utf-8")
        prompt = (
            f"這個 Skill 連續失敗多次，請完整重寫（不只修 bug，重新思考實作方式）。\n"
            f"保持相同的 skill_id 和 input_schema 介面。只輸出程式碼。\n"
            f"```python\n{code}\n```"
        )
        new_code = await chat(prompt)
        new_code = _extract_code_block(new_code)
        compile(new_code, f"{skill_id}.py", "exec")
        path.write_text(new_code, encoding="utf-8")
        success = _registry.hot_reload(skill_id)
        if success:
            SkillTracker().mark_evolved(skill_id)
        return success
    except Exception:
        return False


# ── Memory Nudge ──────────────────────────────────────────────


async def _memory_nudge(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """每 10 輪觸發：LLM 萃取偏好 → InlineKeyboard 確認 → 寫入 YAML。"""
    try:
        from src.llm.gemini_chat import chat, is_available
        if not is_available():
            return
        history = context.user_data.get("_recent_prompts", [])
        if len(history) < 5:
            return
        prompt = (
            "分析以下對話記錄，萃取使用者偏好（最多 3 條）。\n"
            "只回傳 key: value 格式，可用 key：language, role, style, tech_stack, 常用功能, 備註\n"
            f"\n對話：\n" + "\n".join(history[-15:])
        )
        result = await chat(prompt)
        if not result or ":" not in result:
            return

        # 解析 key: value
        updates = {}
        for line in result.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                updates[k.strip()] = v.strip()
        if not updates:
            return

        # 暫存供 callback 使用
        context.user_data["_pending_memory"] = updates
        context.user_data["_pending_memory_uid"] = user_id

        # 發 InlineKeyboard 確認
        preview = "\n".join(f"• {k}: {v}" for k, v in updates.items())
        chat_id = context.user_data.get("_chat_id")
        if chat_id:
            from telegram import Bot
            bot: Bot = context.bot
            await bot.send_message(
                chat_id=chat_id,
                text=f"💡 我注意到你的偏好：\n\n{preview}\n\n要我記住嗎？",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ 記住", callback_data="mem_save"),
                    InlineKeyboardButton("❌ 不用", callback_data="dismiss"),
                ]]),
            )
    except Exception:
        pass


# ── 預設：Agent CLI 模式 ─────────────────────────────────────


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """執行工作流：/run workflow_id [params]。"""
    if not context.args:
        await update.message.reply_text("用法：`/run workflow_id key=value`", parse_mode="Markdown")
        return
    wf_id = context.args[0]
    # 簡易 params 解析：key=value
    params = {}
    for arg in context.args[1:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k] = v

    try:
        from src.workflow.engine import WorkflowEngine
        # 嘗試載入並執行
        wf_engine = WorkflowEngine(_registry)
        wf_path = Path(f"workflows/{wf_id}.yaml")
        if not wf_path.exists():
            await update.message.reply_text(f"❌ 工作流不存在：`{wf_id}`")
            return
        await update.message.reply_text(f"⚙️ 執行工作流 `{wf_id}`...")
        ctx = await wf_engine.run(wf_id, params)
        # 取最後一步的輸出
        last_output = list(ctx.outputs.values())[-1] if ctx.outputs else {}
        result_text = last_output.get("path") or last_output.get("output") or str(last_output)[:500]
        await update.message.reply_text(f"✅ 完成\n\n{result_text}")
    except ImportError:
        await update.message.reply_text("❌ WorkflowEngine 未安裝")
    except Exception as e:
        await update.message.reply_text(f"❌ 執行失敗：{str(e)[:200]}")


async def cmd_invoke_skill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """動態 Skill 執行：/skill_id key=value key=value。"""
    if not _registry:
        return
    msg = update.effective_message
    if not msg or not msg.text:
        return

    import time as _time
    from src.skills.tracker import SkillTracker

    # 提取 /command
    parts = msg.text.strip().split(None, 1)
    skill_id = parts[0][1:]  # 去掉 /
    args_str = parts[1] if len(parts) > 1 else ""

    # 檢查是否為已註冊 Skill
    skill = _registry.get(skill_id)
    if not skill:
        return

    # 解析 key=value 參數
    params = {}
    if args_str:
        import re as _re
        kv_pairs = _re.findall(r'(\w+)=(\S+)', args_str)
        if kv_pairs:
            params = {k: v for k, v in kv_pairs}
        else:
            params = {"prompt": args_str}

    tracker = SkillTracker()
    t0 = _time.time()
    result = await _registry.invoke(skill_id, params)
    duration = _time.time() - t0
    tracker.record(skill_id, result.success, duration, result.error if not result.success else "")

    if not result.success:
        # 自動修正重試
        fixed = await _auto_fix_skill(skill_id, result.error, params)
        if fixed:
            result = await _registry.invoke(skill_id, params)
            if result.success:
                tracker.record(skill_id, True, _time.time() - t0, "")
                output = result.data.get("output") or result.data.get("path") or result.data.get("code") or str(result.data)
                if len(output) > 4000:
                    output = output[:3900] + "\n\n📎 已截斷"
                await msg.reply_text(f"🔧 自動修正後成功\n\n⚡ {output}")
                return
        # P2.3: 檢查是否需要演化
        stats = tracker.get(skill_id)
        if stats and stats.needs_evolution():
            evolved = await _evolve_skill(skill_id)
            if evolved:
                await msg.reply_text(f"🧬 `{skill_id}` 已自動演化重寫，請重試", parse_mode="Markdown")
                return
        await msg.reply_text(f"❌ {skill_id}：{result.error[:200]}")
        return

    output = result.data.get("output") or result.data.get("path") or result.data.get("code") or str(result.data)
    if len(output) > 4000:
        output = output[:3900] + "\n\n📎 已截斷"
    await msg.reply_text(f"⚡ {output}")


# ── 生命週期指令 ──────────────────────────────────────────────


async def cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/retry — 重新生成最後一次回答。"""
    last_prompt = context.user_data.get("_last_prompt")
    if not last_prompt:
        await update.message.reply_text("⚠️ 沒有可重試的對話")
        return
    # 模擬重新發送
    context.user_data["_recent_prompts"] = context.user_data.get("_recent_prompts", [])[:-1]
    update.message.text = last_prompt
    await handle_message(update, context)


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/undo — 撤銷最後一輪對話。"""
    from src.skills.internal.llm_cli import _kiro_sessions
    user_id = update.effective_user.id
    prompts = context.user_data.get("_recent_prompts", [])
    if prompts:
        prompts.pop()
    context.user_data.pop("_last_prompt", None)
    await update.message.reply_text("↩️ 已撤銷最後一輪")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/new — 開新 session。"""
    from src.skills.internal.llm_cli import _kiro_sessions
    user_id = update.effective_user.id
    _kiro_sessions.pop(user_id, None)  # 直接清除 TTL entry
    context.user_data["_recent_prompts"] = []
    context.user_data.pop("_last_prompt", None)
    await update.message.reply_text("🆕 已開新 session")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """預設模式：所有訊息直接送 kiro-cli chat（Agent CLI）。"""
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    if not text or not _registry:
        return

    import time as _time
    from src.bot.utils import ProgressReporter, split_message, TraceLogger
    from src.bot.chat_history import save_user_message, save_bot_message, get_context

    # 記錄玩家訊息
    save_user_message(msg.message_id, msg.chat_id, msg.from_user.id, text)

    wait_msg = await msg.reply_text("🤖 分析問題中...")
    t0 = _time.time()

    # 記錄供 Memory Nudge 使用
    history = context.user_data.setdefault("_recent_prompts", [])
    history.append(text)
    if len(history) > 30:
        context.user_data["_recent_prompts"] = history[-30:]
    context.user_data["_chat_id"] = msg.chat_id
    context.user_data["_last_prompt"] = text

    # 串流進度 callback（節流 1.5s）
    import asyncio
    _last_edit = [0.0]

    async def _on_progress(stage: str, line: str) -> None:
        now = _time.time()
        if now - _last_edit[0] > 1.5:
            elapsed_so_far = round(now - t0, 0)
            try:
                await wait_msg.edit_text(f"{stage}\n⏱ {elapsed_so_far:.0f}s")
            except Exception:
                pass
            _last_edit[0] = now

    # 注入最近 3 輪對話上下文 + 使用者記憶
    chat_ctx = get_context(msg.chat_id, rounds=3)
    from src.conversation.memory_store import MemoryStore
    mem_ctx = MemoryStore().get_context_str(msg.from_user.id)
    prompt_with_ctx = text
    prefix_parts = []
    if mem_ctx:
        prefix_parts.append(f"[使用者偏好]\n{mem_ctx}")
    if chat_ctx:
        prefix_parts.append(f"[對話上下文]\n{chat_ctx}")
    if prefix_parts:
        prompt_with_ctx = "\n---\n".join(prefix_parts) + f"\n---\n當前問題：{text}"

    result = await _registry.invoke("llm_cli", {
        "prompt": prompt_with_ctx, "mode": "chat",
        "user_id": msg.from_user.id, "on_progress": _on_progress,
    })
    elapsed = round(_time.time() - t0, 1)

    # Trace
    try:
        tracer = TraceLogger()
        tracer.log(
            user_id=msg.from_user.id, mode="agent_cli",
            backend=result.data.get("backend", "kiro") if result.success else "error",
            duration=elapsed, success=result.success,
            prompt_len=len(text), reply_len=len(result.data.get("output", "")) if result.success else 0,
        )
    except Exception:
        pass

    if result.success:
        reply = result.data.get("output", "")
        backend = result.data.get("backend", "kiro")
        footer = f"\n\n— {backend} | {elapsed}s"

        chunks = split_message(reply + footer)
        try:
            await wait_msg.edit_text(chunks[0] or "🤔 沒有回應")
        except Exception:
            await msg.reply_text(chunks[0] or "🤔 沒有回應")
        for chunk in chunks[1:]:
            await msg.reply_text(chunk)

        # 記錄 Bot 回覆（用 wait_msg 的 message_id）
        save_bot_message(wait_msg.message_id, msg.chat_id, context.bot.id, reply, reply_to_id=msg.message_id)

        # M2: 含 code block → GrowthDetector 偵測重複 → 建議存成 Skill
        if "```" in reply and len(reply) > 300:
            from src.bot.growth import GrowthDetector
            detector = GrowthDetector()
            should_suggest = detector.record(text, reply)
            if should_suggest:
                await msg.reply_text(
                    "💡 這是你第 2 次產出類似程式碼，建議轉為可重用 Skill！",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ 轉成 Skill", callback_data=f"save_skill:{msg.message_id}"),
                        InlineKeyboardButton("❌ 不用", callback_data="dismiss"),
                    ]]),
                )
            else:
                await msg.reply_text(
                    "💡 回答含程式碼，要存成 Skill 嗎？",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ 存成 Skill", callback_data=f"save_skill:{msg.message_id}"),
                        InlineKeyboardButton("❌ 不用", callback_data="dismiss"),
                    ]]),
                )
            context.user_data["last_code_reply"] = reply
            context.user_data["last_prompt"] = text

        # M5: Memory Nudge（每 10 輪觸發）
        _nudge_count = context.user_data.get("_nudge_count", 0) + 1
        context.user_data["_nudge_count"] = _nudge_count
        if _nudge_count % 10 == 0:
            asyncio.create_task(_memory_nudge(msg.from_user.id, context))
    else:
        try:
            await wait_msg.edit_text(f"❌ {result.error[:300]}")
        except Exception:
            await msg.reply_text(f"❌ {result.error[:300]}")
