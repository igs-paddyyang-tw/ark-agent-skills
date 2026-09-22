# L5 weknora 接入 checklist（weknora-checklist，v1.0）

> 需要 L5 外部 RAG（WeKnora）的 team 的接入步驟。承接需求單
> `2026-09-22-shared-package-change-requests.md`（B5）。
> weknora **不是本地 wiki 櫃**、**不進 `knowledge_search_order`** —— 它是外部查詢決策樹，
> 由 `ark-weknora-cli` skill 獨立呼叫（見 `knowledge-sources-map.md` 的 A3 界線）。

---

## 何時需要 L5

- team 要查詢**研七既有的 WeKnora 知識庫**（別人已建好的 RAG），或
- team 要**自建 KB** 寫入 WeKnora 供跨團隊查。
- 純本地 wiki 就夠的 team（多數研發/工具團）**不需要** L5。

## 接入 checklist

### 1. 裝 skill
- [ ] `ark-weknora-cli` 已在 team 的 `.kiro/skills/`（base_skills 或 role_skills）。

### 2. `.env` 變數（複製 `ark-weknora-cli/assets/.env.example`）
- [ ] `WEKNORA_API_URL`（必填，缺值 BAD_INPUT）——WeKnora 服務位址
- [ ] `WEKNORA_API_KEY`（必填）——retrieve 權限即可
- [ ] `WEKNORA_AGENT_ID`（endpoint=agent 且未帶 `--agent-id` 時的預設）
- [ ] `WEKNORA_KB_ID`（endpoint=knowledge 且未帶 `--kb-id` 時的預設；可填別名或 UUID）
- [ ] `ARK_WEKNORA_TIMEOUT`（選填，預設 180）
- [ ] `.env` **不進版控**（機密）；服務環境由 systemd 注入，IDE 直接跑則讀專案根 `.env`

### 3. 查詢路徑（讀研七 KB）
兩條清楚路徑（見 `ark-weknora-cli/SKILL.md`）：
- [ ] **agent-chat**（`weknora_agent_chat.py`，走 `/agent-chat`，帶 `--agent-id`）——
      agent 自找 KB、多步推理；**不需帶 kb-id**（agent 內部已配置範圍）
- [ ] **knowledge-chat**（`weknora_knowledge_chat.py`，走 `/knowledge-chat`，帶 `--kb-id`）——
      純 RAG，指定知識庫
- [ ] 口徑路由用 `route_query.py`（三層 escalation），或 `weknora_sql_query.py --endpoint agent|knowledge`
- [ ] 🔴 payload 一定帶 `knowledge_base_ids`（缺 `--kb-id` 時帶 `[]`）——繞過服務端 wiki_search 的 regex bug（實測：不帶會掛）

### 4. 寫入路徑（自建/更新 KB）
- [ ] `weknora_ingest.py` 直打 WeKnora `knowledge-bases` / `knowledge` REST endpoint
- [ ] 需要 `WEKNORA_API_URL` + `WEKNORA_API_KEY`（寫入權限）

### 5. 環境變數覆蓋（進階）
- [ ] `ARK_WEKNORA_CMD` 覆蓋底層客戶端指令（覆蓋時 `--endpoint` 選擇失效；測試用 fake_client 也走這個）
- [ ] `ARK_WEKNORA_REGISTRY` / `ARK_WEKNORA_TIMEOUT` 傳遞給下層

## 🔴 界線提醒（對齊需求單 A3）

- weknora **不列入** `team.yaml` 的 `knowledge_search_order`（那只排本地 BM25 櫃）。
- 「何時查 weknora vs 查本地 wiki」是**外部查詢決策樹**，寫在 agent 的 data-query-routing 提詞
  （見 `assets/prompts/work/data-query-routing.md`），不由 `_search_domains` 管。
- weknora 是**外部服務依賴**——team 缺 `.env` 變數時，weknora 查詢失敗但本地 wiki 不受影響（tier 分級）。
