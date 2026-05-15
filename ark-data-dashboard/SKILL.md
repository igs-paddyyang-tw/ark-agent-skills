---
author: paddyyang
name: ark-data-dashboard
description: |
  產出博奕遊戲標準化面板，包含遊戲資訊抓取、數值規格解析、網頁視覺化 Dashboard。
  支援老虎機（slot）、撲克（poker）等博奕遊戲類型，資料來源可替換。
  產出標準化 GameInfo 資料模型、遊戲卡片 grid、數值規格卡片、統計圖表。
  使用此 Skill 當使用者提及遊戲面板、game dashboard、博奕分析、
  老虎機資訊、遊戲資料視覺化、遊戲卡片、遊戲統計、
  或任何需要建立博奕遊戲資訊收集與視覺化面板的場景。
---

# ark-data-dashboard

產出博奕遊戲標準化面板，可獨立運作。

核心概念：`資料來源（可替換）→ 標準化 GameInfo 模型 → Dashboard 面板`

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「遊戲面板」、「game dashboard」、「博奕分析」
- 「老虎機資訊」、「遊戲資料視覺化」
- 「遊戲卡片」、「遊戲統計」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 既有專案目錄路徑 |
| `game_type` | `str` | ❌ | `"slot"` | 遊戲類型（slot / poker / baccarat） |

## 前置條件

- 專案目錄下存在 `src/skills/base.py` + `src/skills/registry.py`（Skill 插件系統）
- 專案目錄下存在 `src/server/main.py`（FastAPI Server）

## 產出指引

---

### 步驟 1：產出標準化資料模型

產出 `src/server/models/game_info.py`：

```python
from pydantic import BaseModel, Field

class GameInfo(BaseModel):
    """標準化博奕遊戲資訊（通用於 slot/poker/baccarat 等）。"""
    name: str
    provider: str
    game_type: str = "slot"         # slot / poker / baccarat / roulette
    icon: str = ""
    url: str = ""
    stars: int = 0
    rtp: float | None = None
    volatility: str | None = None   # low / medium / high / very_high
    mechanics: list[str] = Field(default_factory=list)
    theme: str | None = None
    layout: str | None = None       # "5x3", "6x4 Megaways"
    max_multiplier: float | None = None
    confidence: float = 0.0         # 解析信心度 0-1
```

此模型為所有遊戲類型的統一介面，不同遊戲類型共用相同欄位。

### 步驟 2：產出遊戲資訊抓取 Skill

產出 `src/skills/internal/game_fetcher.py`：

```python
class GameFetcherParams(SkillParam):
    source: str = "vegasslots"      # 資料來源（可替換）
    game_type: str = "slot"
    provider: str | None = None     # 篩選廠商

class GameFetcherSkill(BaseSkill):
    skill_id = "game_fetcher"
    skill_type = SkillType.PYTHON
    description = "抓取博奕遊戲資訊（支援多來源）"
```

- 使用 `httpx.AsyncClient` + 瀏覽器 User-Agent headers
- 回傳 `list[GameInfo]` 序列化為 `SkillResult.data`
- 資料來源可替換（預設 VegasSlotsOnline for slot）
- 抓取欄位：name、provider、icon、url、stars
- HTTP 4xx 時回傳 `fallback_url` 而非報錯

### 步驟 3：產出遊戲規格解析 Skill

產出 `src/skills/internal/game_parser.py`：

```python
class GameParserParams(SkillParam):
    game_info: dict                 # 含 name、provider、url

class GameParserSkill(BaseSkill):
    skill_id = "game_parser"
    skill_type = SkillType.PYTHON
    description = "從遊戲詳情頁解析數值規格（RTP、波動率、玩法等）"
```

- 有 `url` 且沒有描述時，自動抓取詳情頁全文
- 正則 + 關鍵字匹配提取：RTP、volatility、max_multiplier、layout、mechanics、theme
- 自動計算 confidence（RTP 0.35 + 波動率 0.25 + 玩法數 × 0.1）
- 回傳 `GameInfo.model_dump()` + `metadata.icon`

---

### 步驟 4：產出 Dashboard API

產出 `src/server/api/dashboard.py`：

```python
router = APIRouter(prefix="/api/v1/dashboard")

@router.get("/games")
async def list_games(source: str = "vegasslots", provider: str | None = None):
    """抓取遊戲清單。"""

@router.get("/games/{game_id}/parse")
async def parse_game(game_id: str, url: str):
    """解析單一遊戲的數值規格。"""

@router.get("/stats")
async def game_stats(source: str = "vegasslots"):
    """遊戲統計（廠商分佈、RTP 分佈等）。"""
```

更新 `src/server/api/router.py` 掛載 dashboard 路由。

---

### 步驟 5：產出 Dashboard 前端

#### 5a. `src/server/templates/dashboard.html`

暗黑科技風格面板頁面：
- 頂部：來源選擇 + 篩選條件
- 主區域：遊戲卡片 grid
- 側邊/底部：統計圖表區

#### 5b. `src/server/static/js/dashboard.js`

前端邏輯：
- 載入遊戲清單 → 渲染卡片 grid（icon + 名稱 + 廠商 + 星星）
- 每張卡片有「🔍 解析」按鈕 → 呼叫 parse API → 展開數值規格卡片
- 統計圖表：廠商分佈（bar）、RTP 分佈（hist）、波動率佔比（pie）
- 圖表串接 `etl_pipeline` + `chart_generator`（如已安裝）

#### 5c. `src/server/static/css/dashboard.css`

面板專用樣式（繼承暗黑科技風格）：
- `.game-grid` — 遊戲卡片網格
- `.game-card` — 卡片（icon + info + 解析按鈕）
- `.game-card__stars` — 星星評分
- `.mech-card` — 數值規格卡片（grid 數值 + 玩法標籤）
- `.stats-panel` — 統計圖表區
- `.analyze-btn` — 解析按鈕

---

### 步驟 6：更新 FastAPI Server

更新 `src/server/main.py`：
- 掛載 `/dashboard` 頁面路由
- 掛載 dashboard API router
- 掛載 `dashboard.css`

---

### 步驟 7：驗證

```bash
# 確認 Skills 可載入
python -c "from src.skills.internal.game_fetcher import GameFetcherSkill; print('OK')"
python -c "from src.skills.internal.game_parser import GameParserSkill; print('OK')"

# 啟動 Server 後瀏覽 /dashboard
uvicorn src.server.main:app --reload --port 8000
```

---

## 遊戲卡片規格

每張遊戲卡片包含：

```
┌──────────────────────────────────────────┐
│ [icon 52x52]  Name                 [🔍]  │
│               Provider                    │
│               ★★★★☆                      │
└──────────────────────────────────────────┘
```

點擊「🔍 解析」後展開數值規格：

```
┌──────────────────────────────────────────┐
│ [icon 56x56]  Name                        │
│               Provider                    │
│ ┌──────┐ ┌──────┐ ┌──────┐               │
│ │ RTP  │ │ 波動率│ │ 倍率 │               │
│ │96.5% │ │ high │ │15000x│               │
│ └──────┘ └──────┘ └──────┘               │
│ [Free Spins] [Tumble] [Multiplier]       │
└──────────────────────────────────────────┘
```

## 支援的遊戲類型

| 類型 | game_type | 預設來源 | 特有欄位 |
|------|-----------|---------|---------|
| 老虎機 | `slot` | VegasSlotsOnline | rtp、volatility、mechanics、layout |
| 撲克 | `poker` | （待擴充） | hand_types、betting_structure |
| 百家樂 | `baccarat` | （待擴充） | house_edge、side_bets |

新增遊戲類型只需：
1. 在 `game_fetcher.py` 加入新的 `_fetch_{type}` 方法
2. 在 `game_parser.py` 加入新的 `_extract_{type}` 方法
3. GameInfo 模型不需修改（通用欄位）

## 與其他 Skill 的串接

Dashboard 可與以下 Skill 串接（如已安裝）：

- `etl_pipeline` — 將遊戲清單轉換為圖表標準格式
- `chart_generator` — 產生統計圖表（廠商分佈、RTP 分佈等）

Workflow YAML 範例：

```yaml
- id: fetch
  type: skill
  skill: game_fetcher
  params:
    source: "vegasslots"
  output: games

- id: stats
  type: skill
  skill: etl_pipeline
  params:
    source: "{{ outputs.games }}"
    group_by: "provider"
    agg: "count"
    chart_type: "bar"
  output: chart_data

- id: chart
  type: skill
  skill: chart_generator
  params:
    chart_type: "{{ outputs.chart_data.chart_type }}"
    title: "廠商分佈"
    x: "{{ outputs.chart_data.x }}"
    y: "{{ outputs.chart_data.y }}"
    output_name: "provider_dist"
  output: chart
```

## 注意事項

- GameInfo 為通用模型，不同遊戲類型共用相同欄位
- 資料來源可替換，預設 VegasSlotsOnline（slot）
- HTTP 4xx 時回傳 fallback_url 而非報錯
- 必須帶瀏覽器 User-Agent headers
- 正則提取可能因網站格式變更而需調整
- Dashboard 頁面繼承暗黑科技風格

## 踩坑紀錄

### Runtime skill_id 已統一（2026-04-17）

game-news-agent 的 runtime 檔名和 skill_id 已改為與 SKILL.md 一致：
- `fetch_slot_catalog.py` → `game_fetcher.py`（skill_id: `game_fetcher`）
- `mechanics_parser.py` → `game_parser.py`（skill_id: `game_parser`）

前端 app.js、chat.py、index.html 的引用也已同步更新。
