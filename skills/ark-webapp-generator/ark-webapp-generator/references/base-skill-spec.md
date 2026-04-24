# BaseSkill + SkillParam 介面規範

> 本文件為 `ark-webapp-generator` 產出 `src/skills/base.py` 的規範依據。
> 借鑑 OpenClaw Tool Interface 標準化設計，升級為嚴格 Pydantic Schema Typed Interface。

---

## 1. 總覽

Skill 插件系統由以下核心元件組成：

| 元件 | 角色 | 模組位置 |
|------|------|---------|
| `SkillType` | Skill 類型列舉 | `src/skills/base.py` |
| `SkillParam` | 參數基底模型（嚴格模式） | `src/skills/base.py` |
| `SkillResult` | 執行結果模型 | `src/skills/base.py` |
| `BaseSkill` | 抽象基底類別（ABC） | `src/skills/base.py` |

所有 Skill 繼承 `BaseSkill`，透過 `SkillRegistry` 自動發現、註冊與呼叫。

---

## 2. SkillType 列舉

```python
from enum import Enum

class SkillType(Enum):
    """Skill 類型列舉。"""
    PYTHON = "python"   # 純 Python 邏輯（爬蟲、資料處理）
    LLM = "llm"         # 需要 LLM 呼叫（Gemini / Ollama）
    MCP = "mcp"         # 外部 MCP 服務封裝
```

### 規範

- 三種類型：`PYTHON`、`LLM`、`MCP`
- 值為小寫字串（`"python"`、`"llm"`、`"mcp"`）
- `SkillRegistry.list_skills()` 與 `to_dict()` 中以 `.value` 輸出

---

## 3. SkillParam 參數基底模型

```python
from pydantic import BaseModel, ConfigDict

class SkillParam(BaseModel):
    """Skill 參數基底（所有 input schema 繼承此類別）。"""
    model_config = ConfigDict(extra="forbid")
```

### 規範

- 繼承 `pydantic.BaseModel`
- 設定 `model_config = ConfigDict(extra="forbid")`：禁止未宣告欄位，傳入多餘參數時拋出 `ValidationError`
- 所有 Skill 的 `input_schema` 必須繼承 `SkillParam`
- 欄位使用 Pydantic `Field` 定義預設值、描述、約束

### 範例：FetchSlotGameParams

```python
from typing import Literal
from datetime import datetime
from pydantic import Field

class FetchSlotGameParams(SkillParam):
    """fetch_slot_game 輸入參數。"""
    source: Literal["vegasslots", "slotcatalog"]
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    provider: str | None = None
```

---

## 4. SkillResult 執行結果模型

```python
from typing import Any
from pydantic import BaseModel, Field

class SkillResult(BaseModel):
    """Skill 執行結果。"""
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict = Field(default_factory=dict)
```

### 規範

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `success` | `bool` | ✅ | 執行是否成功 |
| `data` | `Any` | ❌ | 成功時的回傳資料（dict、list、str 等） |
| `error` | `str \| None` | ❌ | 失敗時的錯誤訊息 |
| `metadata` | `dict` | ❌ | 附加資訊（執行時間、來源、版本等），預設空 dict |

### 使用慣例

- 成功：`SkillResult(success=True, data={...})`
- 失敗：`SkillResult(success=False, error=str(e))`
- Skill 內部捕獲所有例外，不讓例外逃逸

---

## 5. BaseSkill 抽象基底類別

```python
from abc import ABC, abstractmethod
from pydantic import ValidationError

class BaseSkill(ABC):
    """所有 Skill 的抽象基底類別。"""

    # --- 類別屬性（子類別必須宣告） ---
    skill_id: str                                    # 唯一識別碼，snake_case
    skill_type: SkillType                            # PYTHON | LLM | MCP
    description: str = ""                            # 功能描述（繁體中文）
    version: str = "1.0.0"                           # 語意版本號

    # --- 嚴格 Schema（OpenClaw 借鑑） ---
    input_schema: type[SkillParam] | None = None     # Pydantic 輸入模型
    output_schema: type[BaseModel] | None = None     # Pydantic 輸出模型

    # --- 抽象方法 ---
    @abstractmethod
    async def execute(self, params: dict) -> SkillResult:
        """執行 Skill，回傳 SkillResult。子類別必須實作。"""

    # --- 自動驗證 ---
    def validate_params(self, params: dict) -> bool:
        """自動以 input_schema 驗證參數。"""
        ...

    # --- 自動產生 Tool Definition ---
    def to_tool_definition(self) -> dict:
        """自動從 input_schema 產生 Gemini Function Calling tool definition。"""
        ...

    # --- 序列化 ---
    def to_dict(self) -> dict:
        """序列化為字典，供 API 回傳。"""
        ...
```

---

### 5.1 類別屬性規範

| 屬性 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `skill_id` | `str` | ✅ | — | 唯一識別碼，`snake_case` 命名 |
| `skill_type` | `SkillType` | ✅ | — | `PYTHON` / `LLM` / `MCP` |
| `description` | `str` | ❌ | `""` | 功能描述，繁體中文撰寫 |
| `version` | `str` | ❌ | `"1.0.0"` | 語意版本號（`MAJOR.MINOR.PATCH`） |
| `input_schema` | `type[SkillParam] \| None` | ❌ | `None` | Pydantic 輸入模型類別（非實例） |
| `output_schema` | `type[BaseModel] \| None` | ❌ | `None` | Pydantic 輸出模型類別（非實例） |

### 5.2 `execute(params: dict) -> SkillResult`

- 抽象方法，子類別必須實作
- 接收 `dict` 參數，回傳 `SkillResult`
- 使用 `async def`（所有 I/O 操作皆為非同步）
- 內部必須 try/except 捕獲所有例外，回傳 `SkillResult(success=False, error=str(e))`

### 5.3 `validate_params(params: dict) -> bool`

自動以 `input_schema` 驗證參數，取代手動實作。

```python
def validate_params(self, params: dict) -> bool:
    """自動以 input_schema 驗證，無 schema 則回傳 True（向後相容）。"""
    if self.input_schema is None:
        return True
    try:
        self.input_schema(**params)
        return True
    except ValidationError:
        return False
```

#### 行為規範

| 情境 | 行為 |
|------|------|
| `input_schema` 為 `None` | 回傳 `True`（向後相容，無 schema 的舊 Skill 不受影響） |
| 參數符合 schema | 回傳 `True` |
| 參數不符合 schema（型別錯誤、缺少必要欄位） | 回傳 `False` |
| 參數包含未宣告欄位（`extra="forbid"`） | 回傳 `False` |

### 5.4 `to_tool_definition() -> dict`

自動從 `input_schema` 產生 Gemini Function Calling 相容的 tool definition。

```python
def to_tool_definition(self) -> dict:
    """自動從 input_schema 產生 Gemini Function Calling tool definition。"""
    if self.input_schema is None:
        return {
            "name": self.skill_id,
            "description": self.description,
            "parameters": {},
        }
    schema = self.input_schema.model_json_schema()
    return {
        "name": self.skill_id,
        "description": self.description,
        "parameters": {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        },
    }
```

#### 輸出格式

```json
{
  "name": "fetch_slot_game",
  "description": "從 VegasSlotsOnline 抓取老虎機資訊（含圖示、星星評分）",
  "parameters": {
    "type": "object",
    "properties": {
      "source": {
        "enum": ["slotcatalog", "bigwinboard"],
        "title": "Source",
        "type": "string"
      },
      "date": {
        "default": "2026-04-15",
        "title": "Date",
        "type": "string"
      },
      "provider": {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": null,
        "title": "Provider"
      }
    },
    "required": ["source"]
  }
}
```

#### 行為規範

| 情境 | 行為 |
|------|------|
| `input_schema` 為 `None` | 回傳 `{"name": skill_id, "description": ..., "parameters": {}}` |
| `input_schema` 存在 | 從 `model_json_schema()` 提取 `properties` 與 `required` |

#### 一致性保證

- `to_tool_definition()["name"]` 必等於 `skill_id`
- `to_tool_definition()["description"]` 必等於 `description`
- `to_tool_definition()["parameters"]["properties"]` 的 key 集合必等於 `input_schema.model_fields` 的 key 集合
- `to_tool_definition()["parameters"]["required"]` 必等於 `input_schema` 中無預設值的欄位名稱列表

### 5.5 `to_dict() -> dict`

```python
def to_dict(self) -> dict:
    """序列化為字典，供 API 回傳。"""
    return {
        "skill_id": self.skill_id,
        "skill_type": self.skill_type.value,
        "description": self.description,
        "version": self.version,
        "has_schema": self.input_schema is not None,
    }
```

---

## 6. 版本控制規範

每個 Skill 帶 `version` 屬性，遵循語意版本號（Semantic Versioning）：

| 版本段 | 變更時機 | 範例 |
|--------|---------|------|
| `MAJOR` | 不相容的介面變更（input_schema 欄位移除/改名） | `1.0.0` → `2.0.0` |
| `MINOR` | 向後相容的功能新增（新增選填欄位） | `1.0.0` → `1.1.0` |
| `PATCH` | 向後相容的 bug 修復 | `1.0.0` → `1.0.1` |

- 新建 Skill 預設 `version = "1.0.0"`
- `SkillRegistry.list_skills()` 與 `to_dict()` 中暴露版本資訊
- 版本資訊用於追蹤 Skill 演進與 A/B 測試

---

## 7. 完整參考實作

以下為 `src/skills/base.py` 的完整參考程式碼：

```python
"""Skill 統一介面：BaseSkill + SkillParam + SkillResult + SkillType。

OpenClaw 借鑑升級：嚴格 Schema Typed Interface、自動 tool definition 生成、語意版本號。
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SkillType(Enum):
    """Skill 類型列舉。"""
    PYTHON = "python"
    LLM = "llm"
    MCP = "mcp"


class SkillResult(BaseModel):
    """Skill 執行結果。"""
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict = Field(default_factory=dict)


class SkillParam(BaseModel):
    """Skill 參數基底（所有 input schema 繼承此類別）。"""
    model_config = ConfigDict(extra="forbid")


class BaseSkill(ABC):
    """所有 Skill 的抽象基底類別。

    借鑑 OpenClaw Tool Interface 標準化設計，支援：
    - 嚴格 Pydantic Schema（input_schema / output_schema）
    - 自動 validate_params（無 schema 時向後相容）
    - 自動產生 Gemini Function Calling tool definition
    - 語意版本號追蹤
    """

    skill_id: str
    skill_type: SkillType
    description: str = ""
    version: str = "1.0.0"

    input_schema: type[SkillParam] | None = None
    output_schema: type[BaseModel] | None = None

    @abstractmethod
    async def execute(self, params: dict) -> SkillResult:
        """執行 Skill，回傳 SkillResult。子類別必須實作。"""

    def validate_params(self, params: dict) -> bool:
        """自動以 input_schema 驗證，無 schema 則回傳 True（向後相容）。"""
        if self.input_schema is None:
            return True
        try:
            self.input_schema(**params)
            return True
        except ValidationError:
            return False

    def to_tool_definition(self) -> dict:
        """自動從 input_schema 產生 Gemini Function Calling tool definition。"""
        if self.input_schema is None:
            return {
                "name": self.skill_id,
                "description": self.description,
                "parameters": {},
            }
        schema = self.input_schema.model_json_schema()
        return {
            "name": self.skill_id,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            },
        }

    def to_dict(self) -> dict:
        """序列化為字典，供 API 回傳。"""
        return {
            "skill_id": self.skill_id,
            "skill_type": self.skill_type.value,
            "description": self.description,
            "version": self.version,
            "has_schema": self.input_schema is not None,
        }
```

---

## 8. 與 SkillRegistry 的整合

`SkillRegistry` 在呼叫 `invoke()` 時自動執行 `validate_params()`：

```python
# src/skills/registry.py（相關片段）

class SkillRegistry:
    async def invoke(self, skill_id: str, params: dict) -> SkillResult:
        skill = self.get(skill_id)
        if skill is None:
            return SkillResult(success=False, error=f"Skill not found: {skill_id}")

        # 自動驗證參數
        if not skill.validate_params(params):
            return SkillResult(
                success=False,
                error=f"Invalid params for skill: {skill_id}",
            )

        try:
            return await skill.execute(params)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def list_skills(self) -> list[dict]:
        """回傳包含 version 的 Skill 清單。"""
        return [s.to_dict() for s in self._skills.values()]
```

### GeminiAdapter 整合

```python
# src/llm/adapter.py（相關片段）

class GeminiAdapter:
    def skills_to_tools(self, registry: SkillRegistry) -> list[dict]:
        """自動從 SkillRegistry 產生 tool definitions（零手動維護）。"""
        return [
            skill.to_tool_definition()
            for skill in registry._skills.values()
            if skill.input_schema is not None
        ]
```

僅有 `input_schema` 的 Skill 才會被納入 tool definitions，確保 LLM 只能呼叫有嚴格 schema 的 Skill。

---

## 9. 設計決策摘要

| 決策 | 選擇 | 理由 |
|------|------|------|
| 參數基底 | `SkillParam(BaseModel)` + `extra="forbid"` | 禁止未宣告欄位，避免靜默忽略錯誤參數 |
| 驗證方式 | `validate_params()` 自動以 `input_schema` 驗證 | 零手動實作，新增 Skill 只需定義 schema |
| Tool Definition | `to_tool_definition()` 從 schema 自動生成 | 零手動維護 JSON schema，Skill 修改時自動同步 |
| 向後相容 | `input_schema=None` 時 `validate_params()` 回傳 `True` | 舊 Skill 不受影響，可漸進升級 |
| 版本號 | `version="1.0.0"` 語意版本號 | 追蹤 Skill 演進，支援 A/B 測試 |
| 結果模型 | `SkillResult(BaseModel)` | Pydantic 驗證，統一成功/失敗回傳格式 |
| 例外處理 | Skill 內部捕獲，`SkillRegistry` 兜底 | 例外不逃逸，系統穩定性保證 |


---

## 附錄 A：SlotMechanics 與 VibeScore 資料模型規範

> 本附錄定義 `parser_slot_game` 與 `vibe_analyser` Skills 使用的兩個 Pydantic 資料模型。
> 模型位於 `src/server/models/slot_mechanics.py` 與 `src/server/models/vibe_score.py`。

---

### A.1 SlotMechanics — 老虎機數值規格模型

```python
from pydantic import BaseModel, Field


class SlotMechanics(BaseModel):
    """老虎機數值規格。

    由 parser_slot_game Skill 透過正則匹配從遊戲介紹文本中提取，
    包含 RTP、波動率、核心玩法等結構化數值規格。
    """

    game_name: str
    provider: str
    rtp: float | None = None
    volatility: str | None = None       # "low" / "medium" / "high" / "very_high"
    hit_frequency: float | None = None
    max_multiplier: float | None = None
    layout: str | None = None           # "5x3", "6x4 Megaways"
    mechanics: list[str] = Field(default_factory=list)
    theme: str | None = None
    math_logic: str = ""
    market_fit: str = ""
    confidence: float = 0.0             # 0-1
```

#### 欄位規範

| 欄位 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `game_name` | `str` | ✅ | — | 遊戲名稱 |
| `provider` | `str` | ✅ | — | 遊戲廠商名稱 |
| `rtp` | `float \| None` | ❌ | `None` | Return to Player 百分比（如 96.5） |
| `volatility` | `str \| None` | ❌ | `None` | 波動率等級：`"low"` / `"medium"` / `"high"` / `"very_high"` |
| `hit_frequency` | `float \| None` | ❌ | `None` | 中獎頻率（如 0.35 表示 35%） |
| `max_multiplier` | `float \| None` | ❌ | `None` | 最大倍率（如 10000.0） |
| `layout` | `str \| None` | ❌ | `None` | 版面配置（如 `"5x3"`、`"6x4 Megaways"`） |
| `mechanics` | `list[str]` | ❌ | `[]`（空 list） | 核心玩法清單（如 `["Free Spins", "Cascading", "Multiplier"]`） |
| `theme` | `str \| None` | ❌ | `None` | 遊戲主題（如 `"Egyptian"`、`"Fruit"`） |
| `math_logic` | `str` | ❌ | `""` | 數學邏輯分析文字描述 |
| `market_fit` | `str` | ❌ | `""` | 市場適配度分析文字描述 |
| `confidence` | `float` | ❌ | `0.0` | LLM 提取信心度，範圍 0-1（0 = 無信心，1 = 完全確定） |

#### 行為規範

| 情境 | 行為 |
|------|------|
| 僅提供 `game_name` 與 `provider` | 正確建構，所有選填欄位使用預設值 |
| 所有選填欄位為 `None` | `model_dump()` 保留 `None` 值，不省略 |
| `mechanics` 未提供 | 使用 `Field(default_factory=list)` 產生空 list `[]` |
| `confidence` 超出 0-1 範圍 | 由呼叫端（Skill）負責確保範圍，模型本身不做 validator 約束 |
| `model_dump()` → `SlotMechanics(**dict)` | round-trip 產出等價物件（需求 5.1, 5.2） |

#### 使用範例

```python
# 從 Gemini 回傳的 JSON 建構
raw = {
    "game_name": "Gates of Olympus 1000",
    "provider": "Pragmatic Play",
    "rtp": 96.5,
    "volatility": "very_high",
    "hit_frequency": None,
    "max_multiplier": 15000.0,
    "layout": "6x5",
    "mechanics": ["Tumble", "Multiplier", "Free Spins", "Ante Bet"],
    "theme": "Greek Mythology",
    "math_logic": "高波動率搭配累積倍率機制，單次最大倍率 15000x",
    "market_fit": "適合亞洲與歐洲高端玩家市場",
    "confidence": 0.85,
}
mechanics = SlotMechanics(**raw)

# 序列化回 dict
data = mechanics.model_dump()
assert data["game_name"] == "Gates of Olympus 1000"
assert data["mechanics"] == ["Tumble", "Multiplier", "Free Spins", "Ante Bet"]

# round-trip 驗證
assert SlotMechanics(**data) == mechanics
```

---

### A.2 VibeScore — 視覺語感評分模型

```python
from pydantic import BaseModel, Field


class VibeScore(BaseModel):
    """視覺語感評分。

    由 vibe_analyser Skill 透過 Gemini（含 Vision）分析遊戲的
    美術風格、色彩、市場定位等視覺語感，產出結構化評分。
    """

    overall_score: float                # 1-10
    art_style: str
    color_palette: str
    target_market: list[str] = Field(default_factory=list)
    similar_games: list[str] = Field(default_factory=list)
    analysis: str = ""
```

#### 欄位規範

| 欄位 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `overall_score` | `float` | ✅ | — | 整體視覺語感評分，範圍 1-10（1 = 最差，10 = 最佳） |
| `art_style` | `str` | ✅ | — | 美術風格描述（如 `"3D 寫實"`、`"2D 卡通"`、`"像素風"` ） |
| `color_palette` | `str` | ✅ | — | 主色調描述（如 `"金色與深藍"`、`"霓虹色系"` ） |
| `target_market` | `list[str]` | ❌ | `[]`（空 list） | 目標市場清單（如 `["亞洲", "歐洲"]`） |
| `similar_games` | `list[str]` | ❌ | `[]`（空 list） | 風格相似的遊戲清單（如 `["Sweet Bonanza", "Starlight Princess"]`） |
| `analysis` | `str` | ❌ | `""` | 詳細分析文字描述 |

#### 行為規範

| 情境 | 行為 |
|------|------|
| 僅提供 `overall_score`、`art_style`、`color_palette` | 正確建構，`target_market` 與 `similar_games` 使用空 list，`analysis` 使用空字串 |
| `target_market` 或 `similar_games` 未提供 | 使用 `Field(default_factory=list)` 產生空 list `[]`（需求 5.6） |
| `overall_score` 超出 1-10 範圍 | 由呼叫端（Skill）負責確保範圍，模型本身不做 validator 約束 |
| `model_dump()` → `VibeScore(**dict)` | round-trip 產出等價物件（需求 5.3, 5.4） |

#### 使用範例

```python
# 從 Gemini 回傳的 JSON 建構
raw = {
    "overall_score": 8.5,
    "art_style": "3D 寫實風格，光影效果精緻",
    "color_palette": "金色與深藍為主調，搭配閃電特效",
    "target_market": ["亞洲高端市場", "歐洲主流市場"],
    "similar_games": ["Gates of Olympus", "Zeus vs Hades"],
    "analysis": "視覺品質優秀，希臘神話主題成熟，適合追求高品質視覺體驗的玩家群體",
}
vibe = VibeScore(**raw)

# 序列化回 dict
data = vibe.model_dump()
assert data["overall_score"] == 8.5
assert data["target_market"] == ["亞洲高端市場", "歐洲主流市場"]

# round-trip 驗證
assert VibeScore(**data) == vibe

# 最小建構（僅必要欄位）
minimal = VibeScore(overall_score=5.0, art_style="2D 卡通", color_palette="繽紛色系")
assert minimal.target_market == []
assert minimal.similar_games == []
assert minimal.analysis == ""
```

---

### A.3 與 Skill 系統的整合

兩個資料模型在 Skill 系統中的使用方式：

| 模型 | 使用 Skill | 用途 |
|------|-----------|------|
| `SlotMechanics` | `parser_slot_game`（PYTHON Skill） | 正則提取 → `SlotMechanics(**parsed)` 驗證 → `model_dump()` 存入 `SkillResult.data` |
| `SlotMechanics` | `wiki_trend_linker`（PYTHON Skill） | 接收 `SlotMechanics.model_dump()` dict 作為輸入，進行三層匹配 |
| `VibeScore` | `vibe_analyser`（LLM Skill） | Gemini 回傳 JSON → `VibeScore(**json)` 驗證 → `model_dump()` 存入 `SkillResult.data` |
| `SlotMechanics` | `daily_market_alert`（PYTHON Skill） | 接收 `list[SlotMechanics.model_dump()]` 計算統計數據 |

#### Skill 內部使用模式

```python
# parser_slot_game 內部（簡化）
import json
from src.server.models.slot_mechanics import SlotMechanics

raw_json = await gemini_adapter.generate(prompt=..., system=..., tier="BALANCE", temperature=0.3)
try:
    parsed = json.loads(raw_json["text"])
    mechanics = SlotMechanics(**parsed)
    return SkillResult(success=True, data=mechanics.model_dump())
except (json.JSONDecodeError, ValidationError) as e:
    return SkillResult(success=False, error=f"JSON 解析失敗: {e}")
```

---

### A.4 序列化與反序列化保證

以下屬性由 Property Tests（Task 6.1）驗證：

1. **SlotMechanics round-trip**（需求 5.1, 5.2）：對任意有效的 `SlotMechanics` 物件 `m`，`SlotMechanics(**m.model_dump()) == m` 恆成立
2. **VibeScore round-trip**（需求 5.3, 5.4）：對任意有效的 `VibeScore` 物件 `v`，`VibeScore(**v.model_dump()) == v` 恆成立
3. **SlotMechanics None 保留**（需求 5.5）：選填欄位為 `None` 時，`model_dump()` 保留 `None` 值
4. **VibeScore 空 list 預設**（需求 5.6）：`target_market` 與 `similar_games` 未提供時，預設為空 list `[]`
