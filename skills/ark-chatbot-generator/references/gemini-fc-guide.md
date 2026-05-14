# Gemini Function Calling 整合指引

GeminiAdapter 是 Phase 2 新增的 LLM 整合層，專用於 Gemini 的 Function Calling 場景。
本地 Ollama 用於一般 LLM 生成（透過既有 `LLMAdapter`），GeminiAdapter 專用於 FC。

## MODEL_TIERS 對應表

```python
MODEL_TIERS: dict[str, str] = {
    "FAST": "gemini-2.0-flash-lite",
    "BALANCE": "gemini-2.5-flash",
    "HEAVY": "gemini-2.5-pro",
}
```

| Tier | 模型 | 用途 | 特性 |
|------|------|------|------|
| FAST | gemini-2.0-flash-lite | Intent 分類、簡單問答 | 低延遲、低成本 |
| BALANCE | gemini-2.5-flash | Function Calling、一般生成 | 平衡效能與品質 |
| HEAVY | gemini-2.5-pro | 複雜推理、長文分析 | 最高品質 |

---

## GeminiAdapter 類別

```python
# src/llm/adapter.py — Phase 2 新增

import logging
from google import genai

logger = logging.getLogger(__name__)

MODEL_TIERS: dict[str, str] = {
    "FAST": "gemini-2.0-flash-lite",
    "BALANCE": "gemini-2.5-flash",
    "HEAVY": "gemini-2.5-pro",
}


class GeminiAdapter:
    """Gemini LLM 呼叫介面，支援一般文字生成與 Function Calling。"""

    def __init__(self, api_key: str | None = None, default_tier: str = "BALANCE"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.default_tier = default_tier
        self._client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def generate(
        self,
        prompt: str,
        system: str = "",
        tier: str = "BALANCE",
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        """一般文字生成。

        Args:
            prompt: 使用者 prompt
            system: System prompt
            tier: 模型 tier（FAST / BALANCE / HEAVY）
            temperature: 生成溫度

        Returns:
            {"text": str, "model": str, "tokens": int}
        """
        model_name = MODEL_TIERS.get(tier, MODEL_TIERS["BALANCE"])
        try:
            response = await self._client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                ),
            )
            return {
                "text": response.text,
                "model": model_name,
                "tokens": response.usage_metadata.total_token_count
                         if response.usage_metadata else 0,
            }
        except Exception as e:
            logger.error(f"Gemini generate 失敗: {e}")
            return {
                "text": "抱歉，目前無法處理您的請求。請稍後再試。",
                "model": model_name,
                "tokens": 0,
            }

    async def function_call(
        self,
        user_message: str,
        tools: list[dict],
        system: str = "",
        tier: str = "BALANCE",
        **kwargs,
    ) -> dict:
        """Function Calling — 讓 Gemini 決定呼叫哪個 Skill。

        Args:
            user_message: 使用者訊息
            tools: 候選 tool definitions（受控模式，非全部）
            system: System prompt
            tier: 模型 tier

        Returns:
            action="call" 時：
                {"action": "call", "skill_id": str, "params": dict}
            action="reply" 時：
                {"action": "reply", "text": str}
        """
        model_name = MODEL_TIERS.get(tier, MODEL_TIERS["BALANCE"])
        try:
            # 將 tool definitions 轉換為 Gemini Tool 格式
            gemini_tools = self._to_gemini_tools(tools)

            response = await self._client.aio.models.generate_content(
                model=model_name,
                contents=user_message,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system or self._default_fc_system_prompt(),
                    tools=gemini_tools,
                    temperature=0.3,  # FC 使用低溫度確保穩定
                ),
            )

            # 解析回應：判斷是 function_call 還是 text reply
            return self._parse_fc_response(response)

        except Exception as e:
            logger.error(f"Gemini function_call 失敗: {e}")
            return {
                "action": "reply",
                "text": "抱歉，目前無法處理您的請求。請稍後再試。",
            }

    def skills_to_tools(self, registry: "SkillRegistry") -> list[dict]:
        """自動從 SkillRegistry 產生 tool definitions。

        僅有 input_schema 的 Skill 才會被納入（OpenClaw 借鑑：schema-driven）。
        Tool definitions 從 Skill 的 Pydantic input_schema 自動生成，
        新增或修改 Skill 時無需手動維護 JSON schema。

        Returns:
            tool definitions 清單
        """
        return [
            skill.to_tool_definition()
            for skill in registry._skills.values()
            if skill.input_schema is not None
        ]
```

---

## 受控模式（Controlled Function Calling）

### 核心概念

傳統 FC 將所有 Skills 的 tool definitions 一次傳給 LLM，當 Skills 數量增加時：
- LLM 容易選錯 Skill（幻覺風險）
- Token 消耗增加
- 回應延遲增加

受控模式的策略：
1. `[3] Conversation Layer` 先判斷使用者意圖，匹配候選 Skill
2. `[4] Skill Resolver` 篩選出 1-3 個候選 Skills
3. `[5] Function Calling` 僅傳入候選 tools（而非全部）

### 流程

```
使用者：「幫我查今天 Pragmatic Play 的新遊戲」
       ↓
[3] ConversationPlanner 判斷：
    - 意圖：skill_call
    - 候選 Skill：fetch_slot_game（confidence=0.9）
    - 已知參數：provider="Pragmatic Play"
    - 缺失參數：無（source 有預設值）
    → ExecutionPlan(skill_id="fetch_slot_game", params={...}, confidence=0.9)
       ↓
[4] SkillResolver 篩選：
    - 精確匹配 fetch_slot_game
    → candidate_tools = [fetch_slot_game.to_tool_definition()]
       ↓
[5] FunctionCaller 呼叫 Gemini FC：
    - 僅傳入 1 個 tool definition（而非全部 7 個）
    → {"action": "call", "skill_id": "fetch_slot_game", "params": {...}}
```

### 降級策略

當 `ConversationPlanner` 無法匹配 Skill（`confidence=0`）時：
- 傳入全部 tool definitions（`skills_to_tools(registry)`）
- 讓 Gemini 自行判斷

---

## Tool Definition 自動生成

Tool definitions 從 Skill 的 Pydantic `input_schema` 自動生成，
透過 `BaseSkill.to_tool_definition()` 方法。

### 範例

```python
# Skill 定義
class FetchSlotGameParams(SkillParam):
    source: Literal["slotcatalog", "bigwinboard"]
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    provider: str | None = None

class FetchSlotGameSkill(BaseSkill):
    skill_id = "fetch_slot_game"
    description = "從 SlotCatalog / Bigwinboard 抓取今日新上架老虎機資訊"
    input_schema = FetchSlotGameParams
```

自動產生的 tool definition：

```json
{
    "name": "fetch_slot_game",
    "description": "從 SlotCatalog / Bigwinboard 抓取今日新上架老虎機資訊",
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "enum": ["slotcatalog", "bigwinboard"],
                "type": "string"
            },
            "date": {
                "type": "string"
            },
            "provider": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": null
            }
        },
        "required": ["source"]
    }
}
```

### 轉換為 Gemini Tool 格式

```python
def _to_gemini_tools(self, tool_defs: list[dict]) -> list:
    """將內部 tool definitions 轉換為 Gemini SDK 的 Tool 格式。"""
    declarations = []
    for td in tool_defs:
        declarations.append(
            genai.types.FunctionDeclaration(
                name=td["name"],
                description=td["description"],
                parameters=td.get("parameters", {}),
            )
        )
    return [genai.types.Tool(function_declarations=declarations)]
```

---

## FC 回應解析

```python
def _parse_fc_response(self, response) -> dict:
    """解析 Gemini FC 回應。

    Gemini 回應可能包含：
    1. function_call — LLM 決定呼叫某個 tool
    2. text — LLM 決定直接回答

    Returns:
        action="call" 時：{"action": "call", "skill_id": str, "params": dict}
        action="reply" 時：{"action": "reply", "text": str}
    """
    # 檢查是否有 function call
    for part in response.candidates[0].content.parts:
        if hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            return {
                "action": "call",
                "skill_id": fc.name,
                "params": dict(fc.args) if fc.args else {},
            }

    # 無 function call → 直接回答
    return {
        "action": "reply",
        "text": response.text or "我不確定如何處理這個請求。",
    }
```

---

## 錯誤處理與降級

| 錯誤情境 | 處理方式 |
|---------|---------|
| `GEMINI_API_KEY` 未設定 | `_client = None`，所有呼叫回傳降級靜態回應 |
| API 呼叫逾時 | 記錄 `logger.error()`，回傳降級回應 |
| API 回傳錯誤 | 記錄錯誤，回傳 `{"action": "reply", "text": "抱歉..."}` |
| FC 回傳無效 skill_id | 由 `[6] ParameterResolver` 或 `SkillRegistry.get()` 攔截 |
| FC 回傳無效 params | 由 `[6] ParameterResolver` 校正或拒絕 |
| kiro-cli 未安裝 | `KiroAdapter._available = False`，Kiro 指令回覆提示 |
| kiro-cli 未登入 | `KiroAdapter._available = False`，同上 |
| kiro-cli 執行超時 | 回傳超時訊息，不影響其他後端 |

降級靜態回應範本：
```python
FALLBACK_RESPONSES = {
    "generate": "抱歉，目前無法處理您的請求。請稍後再試。",
    "function_call": "抱歉，目前無法處理您的請求。請稍後再試。",
    "intent_classify": "我不確定您的意圖，請嘗試使用 /help 查看可用指令。",
    "kiro_unavailable": "❌ Kiro CLI 不可用，請確認已安裝並登入。可使用 /help 查看其他可用指令。",
}
```

---

## 預設 System Prompt

```python
def _default_fc_system_prompt(self) -> str:
    """Function Calling 預設 System Prompt。"""
    return (
        "你是一個老虎機趨勢分析助理。"
        "根據使用者的問題，判斷是否需要呼叫工具（Skill）來回答。\n"
        "如果使用者的問題可以透過工具回答，請呼叫對應的工具。\n"
        "如果使用者的問題是一般性問題，請直接回答。\n"
        "回答時使用繁體中文。"
    )
```

---

## 與既有 LLMAdapter 的關係

| 項目 | KiroAdapter（獨立 Agent） | GeminiAdapter（Phase 2 新增） | LLMAdapter（既有） |
|------|--------------------------|---------------------------|-------------------|
| 後端 | kiro-cli（subprocess） | Gemini Cloud API | Ollama 本地部署 |
| 用途 | 程式碼分析、檔案操作、複雜推理 | Function Calling + 一般對話 | 一般 LLM 生成（QA、摘要、分析） |
| 模型 | Kiro 內建 AI agent | gemini-2.5-flash / 2.5-pro | gemma4:e4b / 26b |
| 延遲 | 30-120 秒 | 1-5 秒 | 2-10 秒 |
| 位置 | `src/llm/kiro_adapter.py` | `src/llm/gemini_adapter.py` | `src/llm/adapter.py`（既有） |
| 觸發 | `/ask_kiro` 指令 或 `LLM_BACKEND=kiro` | 預設主要後端 | `OLLAMA_ENABLED=true` 備援 |
| FC 支援 | ❌ 不支援 | ✅ 支援 | ❌ 不支援 |
| 前置條件 | kiro-cli 已安裝且已登入 | GEMINI_API_KEY | Ollama 服務運行中 |

三者透過 `LLMRouter`（`src/llm/llm_router.py`）統一路由：
- `LLMRouter.generate()` — 根據 `LLM_BACKEND` 決定優先順序，自動 fallback
- `LLMRouter.function_call()` — FC 僅走 Gemini，不可用時降級靜態回應
- Kiro 指令（`/ask_kiro` 等）不經過 LLMRouter，直接走 KiroAdapter

GeminiAdapter 新增時不覆蓋既有 `LLMAdapter` 程式碼。
KiroAdapter 獨立為 `kiro_adapter.py`，不影響既有架構。
