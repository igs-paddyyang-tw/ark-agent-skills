# 對話管線架構規範

Telegram Bot 訊息處理採用依賴注入 + PlanAction 分派模式。
核心流程：SessionManager → ConversationPlanner（LLM 意圖解析 + 五層參數填充）→ PlanAction 分派。
Kiro CLI 指令走獨立路徑，不經過對話管線。

關鍵設計：「先釐清再做」— ConversationPlanner 判斷參數是否充足，
不足時透過 InlineKeyboard 追問，充足時才執行工作流。

## 管線總覽

```
Telegram 使用者輸入
       ↓
[0] 群組 @mention 過濾
    — 群組訊息：一律記錄到 FTS5（conversation_history）
    — 無 @mention → 不回話（return）
    — 有 @mention → 移除 @bot_username → 繼續管線
    — 私訊 → 白名單檢查
       ↓
[1] Bot Gateway（TG Adapter）
    — 接收 Update、驗證權限、提取文字/圖片/指令
    — 進階指令（/totp /news /agent）→ 需 is_allowed()（群組+私訊都需白名單）
       ↓
[2] Intent Router（LLM + Rule Hybrid）
    — 規則優先：/help, /skills, /invoke, /run → 直接路由
    — Kiro 指令：/ask_kiro, /read, /write, /ls, /analyze 等 → KiroAdapter
    — 自然語言：LLM 分類意圖（skill_call / direct_reply / workflow_trigger / clarify）
       ↓
[3] Conversation Layer（先釐清再做）
    — Session Manager：載入/建立多輪 context
    — Conversational Planner：判斷資訊是否充足
      → 充足：產出 ExecutionPlan（skill_id + params），進入 [4]
      → 不足：產出 ClarifyRequest（追問問題），直接跳到 [8] 回應
    — memory.md：使用者偏好（UserProfiler 自動更新）
    — MemorySearch：FTS5 跨 session 召回（注入 system prompt）
       ↓
[4] Skill Resolver（Tool Filter + Ranking）
    — 根據 ExecutionPlan 從 SkillRegistry 篩選候選 Skills
    — 依 skill_type、description 相關度排序，產出 candidate_tools
       ↓
[5] LLMRouter + Function Calling（Controlled）
    — LLMRouter 根據 LLM_BACKEND 決定後端優先順序
    — FC 僅走 Gemini（Kiro/Ollama 不支援 FC）
    — 僅傳入 candidate_tools（非全部 Skills），降低幻覺風險
    — 回傳 {"action": "call", "skill_id", "params"} 或 {"action": "reply", "text"}
       ↓
[6] Parameter Resolver（校正 + 驗證）
    — 對 LLM 回傳的 params 做型別校正（str→int、日期格式化）
    — 呼叫 skill.validate_params() 驗證，失敗則回退請使用者補充資訊
       ↓
[7] Skill Registry（執行 + 追蹤）
    — SkillRegistry.invoke(skill_id, validated_params)
    — SkillTracker.record(skill_id, success, duration, error)
    — 連續失敗 3 次 → needs_evolution() → 觸發自動重寫
       ↓
[8] Response Formatter
    — 根據 skill_type 選擇格式化策略（表格、Markdown、圖片 caption）
    — 處理 TG 訊息長度限制（4096 字元分段、1024 caption 限制）
    — 也處理 ClarifyRequest 的追問格式化
       ↓
[9] Memory System（4-layer）
    — FTS5 索引（conversation_history + conversation_fts）
    — MemoryStore 寫入（per-user .md）
    — UserProfiler（每 10 輪觸發）
    — 背景觸發 EntityMemory（實體提取 → Wiki）
       ↓
Telegram 回應
```

### Kiro 指令獨立路徑

Kiro CLI 操作指令不走上述九層管線，而是由 `kiro_handlers.py` 直接處理：

```
/ask_kiro <問題>
       ↓
[1] Bot Gateway — 驗證使用者
       ↓
[K] KiroAdapter — subprocess kiro-cli chat
       ↓
[8] Response Formatter — 分段發送
       ↓
Telegram 回應
```

Kiro 指令清單：`/ask_kiro`、`/resume_kiro`、`/kiro_sessions`、
`/read`、`/write`、`/ls`、`/rm`、`/analyze`、`/kiro_version`、`/kiro_doctor`。
詳見 `references/kiro-mcp-spec.md`。

---

## 各層詳細規範

### [1] BotGateway — TG Adapter

```python
# src/bot/pipeline.py

@dataclass
class BotMessage:
    """從 Telegram Update 提取的標準化訊息。"""
    user_id: str
    username: str | None
    text: str
    image_url: str | None       # 圖片 file_id（若有）
    is_command: bool
    raw_update: Any             # 原始 Update 物件

class BotGateway:
    """[1] TG Adapter：接收 Update，驗證使用者，提取訊息內容。"""

    def __init__(self, allowed_user_ids: list[str] | None = None):
        self.allowed_user_ids = allowed_user_ids

    async def receive(self, update: Update) -> BotMessage | None:
        """接收 Telegram Update，驗證使用者白名單，提取訊息。

        Returns:
            BotMessage — 驗證通過的標準化訊息
            None — 未授權使用者或無效 Update
        """
        ...
```

驗證邏輯：
- `ALLOWED_USER_IDS` 為空或未設定 → 允許所有使用者
- `ALLOWED_USER_IDS` 已設定 → 僅允許白名單中的 user_id
- 無效 Update（無 message 或無 text）→ 回傳 `None`

### [2] IntentRouter — 意圖路由

```python
from enum import Enum

class IntentType(Enum):
    COMMAND_HELP = "command_help"
    COMMAND_SKILLS = "command_skills"
    COMMAND_INVOKE = "command_invoke"
    COMMAND_RUN = "command_run"
    COMMAND_KIRO = "command_kiro"          # Kiro CLI 操作指令
    SKILL_CALL = "skill_call"
    DIRECT_REPLY = "direct_reply"
    WORKFLOW_TRIGGER = "workflow_trigger"
    CLARIFY_RESPONSE = "clarify_response"

@dataclass
class Intent:
    intent_type: IntentType
    confidence: float           # 0-1
    raw_text: str
    command_args: str | None    # 指令參數（如 /invoke 後的 skill_id + params）

    @property
    def is_command(self) -> bool:
        return self.intent_type.value.startswith("command_")

class IntentRouter:
    """[2] 意圖路由：規則優先 + LLM 分類。"""

    def __init__(self, llm: GeminiAdapter | None = None):
        self.llm = llm

    async def route(self, message: BotMessage) -> Intent:
        """路由訊息意圖。規則優先，自然語言走 LLM。"""
        # 規則路由（零延遲）
        if message.text.startswith("/help"):
            return Intent(IntentType.COMMAND_HELP, 1.0, message.text, None)
        if message.text.startswith("/skills"):
            return Intent(IntentType.COMMAND_SKILLS, 1.0, message.text, None)
        if message.text.startswith("/invoke"):
            args = message.text[len("/invoke"):].strip()
            return Intent(IntentType.COMMAND_INVOKE, 1.0, message.text, args)
        if message.text.startswith("/run"):
            args = message.text[len("/run"):].strip()
            return Intent(IntentType.COMMAND_RUN, 1.0, message.text, args)

        # Kiro CLI 指令路由（由 kiro_handlers.py 處理）
        kiro_commands = (
            "/ask_kiro", "/resume_kiro", "/kiro_sessions",
            "/read", "/write", "/ls", "/rm", "/analyze",
            "/kiro_version", "/kiro_doctor",
        )
        for kc in kiro_commands:
            if message.text.startswith(kc):
                args = message.text[len(kc):].strip()
                return Intent(IntentType.COMMAND_KIRO, 1.0, message.text, args)

        # 自然語言 → LLM 分類
        if self.llm:
            return await self._classify_with_llm(message)

        # 無 LLM → 預設為 SKILL_CALL
        return Intent(IntentType.SKILL_CALL, 0.5, message.text, None)
```

設計決策：
- `/` 指令走規則路由，零延遲、零 token 消耗
- 自然語言走 LLM 分類，回傳 `SKILL_CALL`、`DIRECT_REPLY`、`WORKFLOW_TRIGGER` 或 `CLARIFY_RESPONSE`
- 無 LLM 時降級為 `SKILL_CALL`（confidence=0.5）

### [3] Conversation Layer — 先釐清再做

詳見 `planner.py` 的 `ConversationPlanner` 設計。

核心流程：
1. 從 Session 載入多輪 context
2. 從 `data/memory/memory_{user_id}.md` 載入使用者偏好
3. 結合 intent + context + 偏好，嘗試填充目標 Skill 的 `input_schema`
4. 所有 required 欄位都有值 → `ExecutionPlan`
5. 有缺失 → `ClarifyRequest`（產出自然語言追問）

```python
@dataclass
class ExecutionPlan:
    """資訊充足，可以執行。"""
    skill_id: str
    params: dict
    confidence: float           # 0-1

@dataclass
class ClarifyRequest:
    """資訊不足，需要追問。"""
    question: str               # 追問問題（自然語言）
    missing_fields: list[str]   # 缺少的參數欄位名稱
    partial_params: dict        # 已收集到的部分參數
```

memory.md 格式（OpenClaw 風格檔案式記憶）：

```markdown
---
user_id: "123456789"
updated: "2026-04-15T08:30:00"
---

## 偏好設定
- 預設 source: slotcatalog
- 關注廠商: IGT, Aristocrat, Pragmatic Play
- 報表語言: 繁體中文
- 預設 RTP 天數: 7

## 最近關注
- Gates of Hades（Pragmatic Play）— 2026-04-15

## 對話摘要
- 2026-04-15：詢問今日新遊戲，關注高波動率機種
```

### [4] SkillResolver — Skill 篩選與排序

```python
class SkillResolver:
    """[4] Skill 篩選與排序：根據 ExecutionPlan 產出候選 tools。"""

    def resolve(self, plan: ExecutionPlan, registry: SkillRegistry) -> list[dict]:
        """篩選候選 Skills 並產出 tool definitions。

        策略：
        1. plan.skill_id 非空 → 精確匹配該 Skill
        2. plan.skill_id 為空 → 依 description 相關度排序前 5 個
        3. 回傳 tool definitions（供 Gemini FC 使用）
        """
        if plan.skill_id:
            skill = registry.get(plan.skill_id)
            if skill and skill.input_schema:
                return [skill.to_tool_definition()]
        # 全部候選
        return [
            s.to_tool_definition()
            for s in registry._skills.values()
            if s.input_schema is not None
        ]
```

### [5] FunctionCaller — Gemini Function Calling（受控）

```python
@dataclass
class FunctionCallResult:
    action: str                 # "call" | "reply"
    skill_id: str | None = None
    params: dict | None = None
    text: str | None = None

class FunctionCaller:
    """[5] Gemini Function Calling（受控）：僅傳入候選 tools。

    FC 僅走 Gemini（Kiro/Ollama 不支援 FC）。
    透過 LLMRouter.function_call() 呼叫，自動處理 Gemini 不可用的降級。
    """

    def __init__(self, llm_router: "LLMRouter"):
        self.llm_router = llm_router

    async def call(self, message: str, tools: list[dict]) -> FunctionCallResult:
        """呼叫 Gemini FC，僅傳入候選 tools。"""
        result = await self.llm_router.function_call(message, tools)
        return FunctionCallResult(
            action=result["action"],
            skill_id=result.get("skill_id"),
            params=result.get("params"),
            text=result.get("text"),
        )
```

關鍵：僅傳入 `candidate_tools` 而非全部 Skills 的 tool definitions，降低 LLM 幻覺風險。

### [6] ParameterResolver — 參數校正與驗證

```python
class ParameterResolver:
    """[6] 參數校正與驗證。"""

    def resolve(self, skill: BaseSkill, raw_params: dict) -> dict | None:
        """校正 LLM 回傳的參數型別，再以 Skill 的 validate_params 驗證。

        校正規則：
        - str 數字 → int/float（依 schema 型別）
        - 日期字串格式化（YYYY-MM-DD）
        - 空字串 → None（選填欄位）

        Returns:
            dict — 校正後的有效參數
            None — 驗證失敗
        """
        corrected = self._type_correct(skill, raw_params)
        if skill.validate_params(corrected):
            return corrected
        return None
```

### [7] Skill Registry（執行）

直接使用既有的 `SkillRegistry.invoke(skill_id, validated_params)`。
例外由 `invoke()` 兜底捕獲，回傳 `SkillResult(success=False, error=str(e))`。

### [8] ResponseFormatter — 回應格式化

```python
@dataclass
class TGMessage:
    """Telegram 訊息封裝。"""
    text: str | None = None
    image_path: str | None = None
    parse_mode: str = "Markdown"

    async def send(self, update: Update) -> None:
        """發送訊息到 Telegram。"""
        if self.image_path:
            await update.message.reply_photo(photo=open(self.image_path, "rb"),
                                              caption=self.text[:1024] if self.text else None)
        elif self.text:
            await update.message.reply_text(self.text, parse_mode=self.parse_mode)

class ResponseFormatter:
    """[8] 回應格式化。"""

    MAX_MESSAGE_LENGTH = 4096
    MAX_CAPTION_LENGTH = 1024

    def format(self, result: SkillResult, skill_type: SkillType) -> list[TGMessage]:
        """根據 skill_type 選擇格式化策略。"""
        ...

    def format_clarify(self, clarify: ClarifyRequest) -> list[TGMessage]:
        """格式化追問訊息。"""
        return [TGMessage(text=f"❓ {clarify.question}")]

    def _split_message(self, text: str) -> list[str]:
        """將超長訊息分段（每段 ≤ 4096 字元）。"""
        ...
```

格式化策略：
- `SkillType.PYTHON` → 表格或 JSON 格式
- `SkillType.LLM` → Markdown 格式
- 有圖片 → `send_photo` + caption
- 超長訊息 → 分段發送

### [9] Memory System — 三層記憶

詳見 `references/memory-spec.md`。

整合流程（在 `handlers.py` 的 `handle_message` 最後執行）：

```python
# [9] Memory System — 非同步寫入
await memory.ingest_turn(msg, fc_result, result if fc_result.action == "call" else None)
```

`ingest_turn` 內部：
1. 寫入 `HybridMemoryRetrieval`（向量 + BM25 索引）
2. 更新 `HierarchicalMemory`（壓縮摘要）
3. 背景觸發 `EntityMemory`（實體提取 → Wiki 更新）
4. 更新 `data/memory/memory_{user_id}.md`（使用者偏好持久化）

---

## 設計決策摘要

| 層級 | 決策 | 理由 |
|------|------|------|
| [2] Intent Router | 規則優先於 LLM | `/` 指令不需浪費 LLM token，確定性路由 |
| [2] Intent Router | Kiro 指令獨立路徑 | kiro-cli 延遲高（30-120s），不走九層管線 |
| [3] Conversation Layer | 先釐清再做 | 避免 LLM 猜測缺失參數導致錯誤執行 |
| [3] memory.md | OpenClaw 風格檔案式記憶 | 使用者偏好持久化，減少重複追問 |
| [3] ConversationPlanner | 不改動現有 Skill | 純粹在管線中間插入，input_schema 不變 |
| [4] Skill Resolver | 篩選後再送 FC | 減少 tool definitions 數量，降低選錯機率 |
| [5] Function Calling | 受控模式，透過 LLMRouter | 僅傳入候選 tools，FC 僅走 Gemini |
| [5] LLMRouter | 統一路由 + fallback | 根據 LLM_BACKEND 決定後端，自動降級 |
| [6] Parameter Resolver | 獨立校正層 | LLM 回傳型別不一定正確，需校正後再驗證 |
| [8] Response Formatter | 策略模式 | 不同 skill_type 輸出格式差異大 |
| [9] Memory | 非同步寫入 | 記憶更新不阻塞回應 |

---

## handlers.py 主流程虛擬碼

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """九層管線主流程。"""
    gateway = context.bot_data["gateway"]
    router = context.bot_data["intent_router"]
    planner = context.bot_data["planner"]
    resolver = context.bot_data["skill_resolver"]
    llm_router = context.bot_data["llm_router"]
    caller = FunctionCaller(llm_router)
    param_resolver = context.bot_data["param_resolver"]
    formatter = context.bot_data["formatter"]
    memory = context.bot_data["memory"]

    # [1] Gateway
    msg = await gateway.receive(update)
    if not msg:
        return

    # [2] Intent Router
    intent = await router.route(msg)
    if intent.is_command:
        if intent.intent_type == IntentType.COMMAND_KIRO:
            # Kiro 指令由 kiro_handlers.py 的 CommandHandler 處理，
            # 不會走到這裡（已在 main.py 註冊獨立 handler）
            return
        return await _handle_command(intent, update, context)

    # [3] Conversation Layer — 先釐清再做
    plan = await planner.plan(msg, intent, context.bot_data["registry"])
    if isinstance(plan, ClarifyRequest):
        messages = formatter.format_clarify(plan)
        for tg_msg in messages:
            await tg_msg.send(update)
        await memory.ingest_turn(msg, plan, None)
        return

    # [4] + [5] Skill Resolver + Function Calling（透過 LLMRouter）
    if plan.confidence == 0:
        gemini = llm_router.gemini
        if gemini:
            all_tools = gemini.skills_to_tools(context.bot_data["registry"])
            fc_result = await caller.call(msg.text, all_tools)
        else:
            fc_result = FunctionCallResult(action="reply", text="LLM 不可用，請使用 /invoke 手動呼叫 Skill。")
    else:
        candidate_tools = resolver.resolve(plan, context.bot_data["registry"])
        fc_result = await caller.call(msg.text, candidate_tools)

    if fc_result.action == "reply":
        # 一般對話回覆 — 透過 LLMRouter 路由（根據 LLM_BACKEND）
        if not fc_result.text or fc_result.text.strip() == "":
            result = await llm_router.generate(prompt=msg.text)
            fc_result = FunctionCallResult(action="reply", text=result["text"])
        await update.message.reply_text(fc_result.text)
    elif fc_result.action == "call":
        # [6] Parameter Resolver
        skill = context.bot_data["registry"].get(fc_result.skill_id)
        params = param_resolver.resolve(skill, fc_result.params)
        if params is None:
            await update.message.reply_text("請補充更多資訊...")
            return

        # [7] Execute
        result = await context.bot_data["registry"].invoke(fc_result.skill_id, params)

        # [8] Response Formatter
        messages = formatter.format(result, skill.skill_type)
        for tg_msg in messages:
            await tg_msg.send(update)

    # [9] Memory System
    await memory.ingest_turn(msg, fc_result, result if fc_result.action == "call" else None)
```
