# 遷移指南：Skill 產出 → ark-team-agent 完整套件

> 將 build_team.py 產出的精簡專案，逐步升級為成熟的 pip 套件。
> 每個階段獨立可用，不需一次全部升級。

---

## 總覽

```
Stage 0: Skill 產出（python start.py）
    ↓ 穩定運行 1~2 週
Stage 1: 加入 Telegram 整合
    ↓ 需要風控時
Stage 2: 加入監控與風控
    ↓ 需要知識累積時
Stage 3: 加入知識演化
    ↓ 需要套件化發布時
Stage 4: 轉為 pip 套件
    ↓ 需要 Web Dashboard 時
Stage 5: 加入 Web 觀測面板
```

---

## Stage 0: Skill 產出（基線）

**你已擁有的能力：**
- CoreDaemon + AgentProcess（agent 生命週期）
- MCP Server（10 tools：reply / send / delegate / status / task / broadcast）
- HTTP API（health / send / status / reply）
- APScheduler 排程
- TelegramAdapter（基礎 @mention 路由）
- 知識庫五件套（per-agent）

**啟動方式：** `python start.py`

**依賴：** pyyaml + python-telegram-bot + fastapi + uvicorn + httpx + python-dotenv + apscheduler

---

## Stage 1: Telegram 深度整合

**新增模組：**

| 檔案 | 來源 | 職責 |
|------|------|------|
| `src/{pkg}/session.py` | 新寫 | Session 管理（Turn-based） |
| `src/{pkg}/chat_router.py` | 新寫 | @mention 解析 + 路由邏輯 |
| `src/{pkg}/planner.py` | 新寫 | 意圖路由（關鍵字 → agent） |

**修改：**
- `telegram_adapter.py`：加入 session tracking + typing indicator + reaction

**獲得能力：**
- 使用者訊息自動路由到正確 agent
- 對話上下文追蹤（避免 agent 失憶）
- Telegram 表情反應回饋（⏳ 處理中、✅ 完成）

**遷移步驟：**
```bash
# 1. 建立模組
touch src/{pkg}/session.py src/{pkg}/chat_router.py src/{pkg}/planner.py

# 2. 從 ark-team-agent 參考實作（不需 1:1 複製）
# session.py: Session dataclass + Turn tracking
# chat_router.py: @mention regex + resolve
# planner.py: keyword → agent mapping

# 3. 修改 telegram_adapter.py
# _on_message() 加入 session.get_or_create() + planner.plan()
```

**驗收：**
- [ ] 使用者可 @agent-name 指定對話
- [ ] 無 @mention 時自動路由到 leader
- [ ] 同一 agent 連續對話保持上下文

---

## Stage 2: 監控與風控

**新增模組：**

| 檔案 | 職責 | 關鍵 class |
|------|------|-----------|
| `cost_guard.py` | 每日成本熔斷 | CostGuard.add_spend() / is_paused() |
| `failure_memory.py` | 重複失敗偵測 | FailureMemory.record() / _is_repeating() |
| `event_log.py` | 事件溯源 | EventLog.record() / query() |
| `message_queue.py` | 訊息 backpressure | MessageQueue.enqueue() / _run_worker() |

**修改：**
- `daemon.py`：加入 cost_guard 檢查 + failure_memory 記錄
- `team_mcp.py`：`record_spend` tool 寫入 cost_guard

**獲得能力：**
- Agent 超支自動暫停（daily_limit_usd）
- 同類錯誤連續 2 次自動停止重試
- 全域事件可追溯（SQLite）
- 訊息佇列防止過載

**遷移步驟：**
```bash
# 1. 建立 state/ 目錄（SQLite 存放處）
mkdir state/

# 2. 建立模組（參考 ark-team-agent 實作）
# cost_guard: daily_limit_usd 超過 → pause instance
# failure_memory: 同 error pattern 2次 → stop retry
# event_log: SQLite 記錄 type/source/detail/timestamp

# 3. config.py 加入 CostGuardConfig dataclass
# 4. daemon.py _health_check 加入 cost_guard.check()
```

**驗收：**
- [ ] `record_spend(5.0, "test")` 後 cost_guard 正確累計
- [ ] 超過 daily_limit 後 agent 暫停
- [ ] event_log 可查到歷史事件

---

## Stage 3: 知識演化

**新增模組：**

| 檔案 | 職責 |
|------|------|
| `skill_growth.py` | 偵測 agent 是否學會新技能 |
| `skill_extractor.py` | 從 output 提煉 skill.md |
| `daily_summary.py` | 每日工作摘要 |
| `conversation_log.py` | 對話記錄歸檔 |

**新增 MCP 工具：**

| 工具 | 用途 |
|------|------|
| wiki_query | 搜尋團隊知識庫 |
| wiki_ingest | 匯入新知識 |

**修改：**
- `team_mcp.py`：加入 wiki_query / wiki_ingest handler
- `scheduler.yaml`：加入 daily-knowledge-digest job

**獲得能力：**
- Agent 自動沉澱知識到 wiki/
- 知識庫可被所有 agent 搜尋
- 每日工作摘要自動產出

**遷移步驟：**
```bash
# 1. team_mcp.py 加入 wiki_query / wiki_ingest
# wiki_query: grep knowledge/shared/wiki/ + knowledge/{agent}/wiki/
# wiki_ingest: 將 raw/ 資料整理到 wiki/ 並更新 index.md

# 2. 建立 skill_growth.py
# 規則：agent 連續 3 次成功解決同類問題 → 建議提煉 skill

# 3. scheduler.yaml 加入
# daily-knowledge-digest: 每日 21:30 觸發整理
```

**驗收：**
- [ ] `wiki_query("架構")` 回傳相關知識頁面
- [ ] `wiki_ingest("knowledge/shared/raw/notes.md")` 成功匯入
- [ ] 每日摘要自動產出到 output/

---

## Stage 4: 轉為 pip 套件

**目標：** 從 `python start.py` 升級為 `pip install` + CLI 入口

**步驟：**

```bash
# 1. 重構目錄
mkdir -p src/ark_team_{name}/
mv src/ark_team_core/*.py src/ark_team_{name}/
mv src/{pkg}/*.py src/ark_team_{name}/

# 2. 更新 pyproject.toml
[project.scripts]
ark-team-{name} = "ark_team_{name}.cli:main"

# 3. 建立 cli.py
# 支援: init / team start / team stop / team status / ls / send

# 4. 安裝
pip install -e .

# 5. 啟動方式改變
ark-team-{name} team start  # 取代 python start.py
```

**獲得能力：**
- CLI 入口（`ark-team-{name}` 指令）
- pip 版本管理（semver）
- 可發布到 PyPI
- `pip install --upgrade` 更新

**注意事項：**
- start.py 保留作為開發快捷入口（直接 `python start.py`）
- CLI 走 setuptools entry_points（正式入口）
- pyproject.toml 的 `[tool.setuptools.packages.find]` 指向 `src/`

---

## Stage 5: Web 觀測面板

**新增模組：**

| 檔案 | 職責 |
|------|------|
| `json_logging.py` | 結構化 JSON 日誌 |
| `heartbeat.py` | 心跳偵測 API |
| `watchdog.py` | 外部看門狗（restart.flag） |

**新增 API 端點：**

| 端點 | 用途 |
|------|------|
| GET /dashboard | Web UI 入口 |
| WS /ws/events | WebSocket 即時事件推送 |
| GET /api/events | SSE 事件串流 |
| GET /api/metrics | Prometheus 格式指標 |

**獲得能力：**
- 瀏覽器即時監控面板
- WebSocket 事件推送
- 結構化日誌（JSON Lines）
- 外部看門狗自動重啟

---

## 各階段依賴變化

| Stage | 新增依賴 | 累計依賴數 |
|-------|---------|-----------|
| 0 | pyyaml, python-telegram-bot, fastapi, uvicorn, httpx, python-dotenv, apscheduler | 7 |
| 1 | — | 7 |
| 2 | — | 7 |
| 3 | — | 7 |
| 4 | build, setuptools | 9（含 dev） |
| 5 | jinja2（模板）, pydantic（API schema） | 11 |

---

## 遷移決策樹

```
團隊剛建立 → 留在 Stage 0
  ↓ Telegram 互動需求增加
需要智慧路由？ → Stage 1
  ↓ 成本或穩定性問題
Agent 花太多錢？常崩潰？ → Stage 2
  ↓ 知識不斷重複
Agent 重複解決同類問題？ → Stage 3
  ↓ 需要發布或多環境部署
要在另一台機器跑？ → Stage 4
  ↓ 需要視覺化監控
老闆要看 Dashboard？ → Stage 5
```

---

## 參考

- ark-team-agent 原始碼：`src/ark_team_agent/`（37 模組）
- 完整 MCP 工具規格：`references/mcp-tools-spec.md`
- 系統架構：`references/architecture.md`
