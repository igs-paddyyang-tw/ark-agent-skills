# Workflow YAML 格式規範

本文件定義 WorkflowEngine 使用的 YAML 工作流格式，所有工作流檔案存放於 `workflows/` 目錄下。

---

## 頂層結構

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `id` | `str` | ✅ | 工作流唯一識別碼（snake_case，全域唯一） |
| `name` | `str` | ❌ | 工作流顯示名稱（繁體中文） |
| `description` | `str` | ❌ | 工作流描述 |
| `steps` | `list[Step]` | ✅ | 步驟清單，依序執行 |

```yaml
id: daily_slot_report           # str, 必要, 唯一
name: 每日老虎機趨勢報表         # str
description: |                  # str
  從 SlotCatalog 抓取新遊戲，逐一解析數值、
  比對 Wiki、分析語感，最後繪製趨勢圖表並推送報表。
steps:                          # list[Step]
  - ...
```

---

## Step 結構

每個步驟包含以下共用欄位：

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `id` | `str` | ✅ | 步驟唯一識別碼（在工作流內唯一） |
| `type` | `str` | ✅ | 步驟類型：`skill` / `condition` / `loop` / `parallel` |

---

### 步驟類型 1：`skill`（呼叫單一 Skill）

透過 `SkillRegistry.invoke(skill_id, params)` 呼叫指定 Skill。

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `skill` | `str` | ✅ | SkillRegistry 中的 `skill_id` |
| `params` | `dict` | ❌ | 傳入 Skill 的參數，支援 Jinja2 模板 |
| `output` | `str` | ❌ | 結果存入 `RunContext.outputs` 的 key |

```yaml
- id: fetch
  type: skill
  skill: fetch_slot_game
  params:
    source: "slotcatalog"
    date: "{{ params.date | default('today') }}"
  output: raw_games
```

執行後 `RunContext.outputs["raw_games"]` 即為 `SkillResult.data`。

---

### 步驟類型 2：`condition`（條件分支）

評估條件表達式，根據結果選擇執行 `then` 或 `else` 分支。

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `condition` | `str` | ✅ | Python 條件表達式（使用 `eval` + `{"__builtins__": {}}`） |
| `then` | `Step` | ✅ | 條件為 True 時執行的步驟 |
| `else` | `Step` | ❌ | 條件為 False 時執行的步驟 |

```yaml
- id: check_games
  type: condition
  condition: "len(outputs.get('raw_games', {}).get('games', [])) > 0"
  then:
    id: parse_games
    type: skill
    skill: parser_slot_game
    params:
      game_info: "{{ outputs.raw_games.games[0] }}"
    output: parsed_first
  else:
    id: no_games
    type: skill
    skill: echo
    params:
      message: "今日無新遊戲上架"
    output: no_games_msg
```

安全性：`eval()` 的 globals 設定為 `{"__builtins__": {}}`，僅允許存取 `outputs` 與 `params`。

---

### 步驟類型 3：`loop`（迴圈執行）

迭代 `items` 清單，對每個項目執行子步驟。

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `items` | `str` | ✅ | Jinja2 表達式，解析為可迭代清單 |
| `item_var` | `str` | ❌ | 迴圈變數名稱（預設 `"item"`） |
| `step` | `Step` | ✅ | 對每個項目執行的子步驟 |
| `output` | `str` | ❌ | 收集所有迭代結果的 key |

```yaml
- id: parse
  type: loop
  items: "{{ outputs.fetch.games }}"
  item_var: game
  step:
    id: parse_single
    type: skill
    skill: parser_slot_game
    params:
      game_info: "{{ game }}"
      tier: "BALANCE"
    output: parsed_game
  output: parsed_results
```

執行後 `RunContext.outputs["parsed_results"]` 為所有迭代結果的 `list`。

---

### 步驟類型 4：`parallel`（平行執行）

使用 `asyncio.gather` 同時執行所有子步驟。

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `steps` | `list[Step]` | ✅ | 平行執行的子步驟清單 |
| `output` | `str` | ❌ | 收集所有結果的 key |

```yaml
- id: analyze_parallel
  type: parallel
  steps:
    - id: link_wiki
      type: skill
      skill: wiki_trend_linker
      params:
        mechanics: "{{ outputs.parsed_results[0] }}"
      output: wiki_links
    - id: vibe_check
      type: skill
      skill: vibe_analyser
      params:
        game_info: "{{ outputs.fetch.games[0] }}"
      output: vibe_result
  output: parallel_results
```

---

## Jinja2 模板語法

步驟的 `params` 欄位支援 Jinja2 模板語法，可引用 `RunContext` 中的資料：

| 語法 | 說明 | 範例 |
|------|------|------|
| `{{ outputs.X }}` | 引用步驟 X 的輸出 | `{{ outputs.raw_games.games }}` |
| `{{ outputs.X.field }}` | 引用步驟 X 輸出的特定欄位 | `{{ outputs.fetch.count }}` |
| `{{ params.Y }}` | 引用工作流輸入參數 | `{{ params.provider }}` |
| `{{ item }}` | 在 `loop` 中引用當前迭代項目 | `{{ game.name }}` |
| `{{ X \| default(V) }}` | 預設值 filter | `{{ params.days \| default(7) }}` |

模板環境設定：
- `jinja2.Environment(undefined=jinja2.StrictUndefined)` — 未定義變數拋出錯誤
- 模板 context 包含：`outputs`（RunContext.outputs）、`params`（工作流輸入參數）、迴圈變數

---

## 完整範例：daily_slot_report.yaml

```yaml
id: daily_slot_report
name: 每日老虎機趨勢報表
description: |
  從 SlotCatalog 抓取今日新上架老虎機，逐一解析數值規格、
  比對 Wiki 知識庫、分析視覺語感，繪製 RTP 趨勢圖表，
  最後渲染報表並推送至 Telegram。

steps:
  # 步驟 1：抓取今日新遊戲
  - id: fetch
    type: skill
    skill: fetch_slot_game
    params:
      source: "{{ params.source | default('slotcatalog') }}"
      date: "{{ params.date | default('today') }}"
      provider: "{{ params.provider | default(None) }}"
    output: fetch

  # 步驟 2：逐一解析數值規格
  - id: parse
    type: loop
    items: "{{ outputs.fetch.games }}"
    item_var: game
    step:
      id: parse_single
      type: skill
      skill: parser_slot_game
      params:
        game_info: "{{ game }}"
        tier: "BALANCE"
      output: parsed
    output: parse

  # 步驟 3：逐一比對 Wiki 知識庫
  - id: link
    type: loop
    items: "{{ outputs.parse }}"
    item_var: mechanics
    step:
      id: link_single
      type: skill
      skill: wiki_trend_linker
      params:
        mechanics: "{{ mechanics }}"
        max_links: 5
      output: linked
    output: link

  # 步驟 4：逐一分析視覺語感
  - id: vibe
    type: loop
    items: "{{ outputs.parse }}"
    item_var: mechanics
    step:
      id: vibe_single
      type: skill
      skill: vibe_analyser
      params:
        game_info:
          name: "{{ mechanics.game_name }}"
          description: "{{ mechanics.math_logic }}"
        tier: "BALANCE"
      output: vibe_score
    output: vibe

  # 步驟 5：繪製 RTP 趨勢圖表
  - id: chart
    type: skill
    skill: rtp_trend_visualizer
    params:
      provider: "{{ params.provider | default('all') }}"
      days: "{{ params.days | default(7) }}"
    output: chart

  # 步驟 6：渲染報表並推送
  - id: alert
    type: skill
    skill: daily_market_alert
    params:
      games: "{{ outputs.parse }}"
      chat_id: "{{ params.notify_chat_id }}"
      chart_path: "{{ outputs.chart.chart_path | default(None) }}"
    output: alert
```

---

## 驗證規則

WorkflowEngine 在 `load()` 時應驗證：

1. `id` 欄位存在且為非空字串
2. `steps` 欄位存在且為非空 list
3. 每個步驟的 `id` 在工作流內唯一
4. 每個步驟的 `type` 為 `skill` / `condition` / `loop` / `parallel` 之一
5. `skill` 類型步驟必須有 `skill` 欄位
6. `loop` 類型步驟必須有 `items` 和 `step` 欄位
7. `condition` 類型步驟必須有 `condition` 和 `then` 欄位
8. `parallel` 類型步驟必須有 `steps` 欄位
