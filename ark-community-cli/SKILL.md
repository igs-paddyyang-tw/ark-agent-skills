---
name: ark-community-cli
description: |
  社群訊息蒐集與分析的 CLI skill：以標準 SOP 從 Discord（自家伺服器，bot 唯讀）與 X／Twitter（日本市場，
  X API v2 pay-per-use）取得訊息，統一 schema、假名化、去重、規則分類（feedback_type）、日文/中文情感標記、
  聚類成痛點候選，產出 ark-md-report 契約的週摘與案件卡，並與知識庫閉環：案件 → 週摘 → wiki ingest（leader）
  → decisions 回寫 → 下週回饋比對。內含 discord_pull / x_pull / normalize / classify / digest / loop 六支腳本與
  費控、PII、ToS 守門。使用此 skill 當使用者提及「Discord 訊息蒐集」「X／Twitter 監測」「日本社群」「エゴサ」
  「玩家回饋收集」「社群輿情腳本」「意見建案」「community intake」「social listening」，或 hoyeah 的
  community-agent / researcher-agent 要拉社群資料時。分析結論的報告文體交 ark-md-report；wiki 儲存交 ark-wiki-engine；
  本 skill 只管「怎麼合規、省錢、可重跑地把訊息拿回來並接進閉環」。不適用於 Reddit／論壇／商店評論（researcher 的 market-intel 範圍）、
  X 發文／回覆／DM、玩家分群；產報告請用 ark-md-report、寫 wiki 請用 ark-wiki-engine。
metadata:
  author: paddyyang
  schema_version: 1
  version: 1.1.1
  category: pipeline
  updated: 2026-09-23
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: ai }
  render: none
  depends_on: [ark-md-report, ark-wiki-engine]
  status: active
---

# ark-community-cli

一句話：**拉得合規、花得有數、跑得可重、接得進 wiki。**

兩個來源、兩種信任度，永遠分開存、分開算：

| | Discord（自家伺服器） | X／Twitter（日本市場） |
|---|---|---|
| 是誰在講 | 已知玩家，可對到 `player_key` | 匿名大眾，只有 `author_key`（假名） |
| 取得方式 | Bot 唯讀 REST，`GET /channels/{id}/messages` 增量游標 | X API v2 recent search，pay-per-use 計費 |
| 成本 | 免費，只有 rate limit | **每讀一則 $0.005**，一次 100 則 = $0.50；月上限 200 萬則 |
| 主要風險 | PII（Discord ID、暱稱）、Message Content Intent 審核 | 花錢失控、query 太寬、ToS 禁爬 |
| trust | `owned` | `public-third-party` |

## 前置：一定先讀

- `references/compliance.md`：ToS、PII、費控三條紅線，違反任何一條就不要跑腳本
- 來源 SOP：`references/sop-discord.md`、`references/sop-x-japan.md`
- 2026 工具現況與選型理由：`references/landscape-2026.md`
- 分析方法（分群、痛點判定、交叉來源）：`references/analysis-playbook.md`
- 與知識庫閉環（handoff / ingest / decisions 回寫）：`references/wiki-loop.md`

## 工作流程（核心六步順序固定；probe/resolve 為運維輔助）

```bash
python scripts/community_cli.py init  --out community/                 # 產 config.yaml、state/、raw/、cases/
python scripts/community_cli.py probe   --config community/config.yaml [--channel feedback]  # 頻道健檢：可讀性 + 最近訊息
python scripts/community_cli.py resolve --config community/config.yaml [--write]              # 用 API 補 channels[].name
python scripts/community_cli.py pull  discord --config community/config.yaml [--since 7d] [--dry-run]
python scripts/community_cli.py pull  x       --config community/config.yaml --query game-ja [--max-posts 300] [--estimate]
python scripts/community_cli.py normalize     --config community/config.yaml   # raw/ → records/ 統一 schema、假名化、去重
python scripts/community_cli.py classify      --config community/config.yaml   # records/ → feedback_type、sentiment、cluster 候選
python scripts/community_cli.py digest        --config community/config.yaml --week 2026-W39   # → reports/ 週摘 MD + 案件卡
python scripts/community_cli.py loop  compare --config community/config.yaml --decision D-2026-09-22-01  # 決策前後回饋比對
python scripts/community_cli.py loop  handoff --config community/config.yaml --week 2026-W39   # 產 wiki ingest 清單給 leader
```

### 0. probe / resolve（運維輔助，開跑前用）
- **probe**：逐一探測 `config.discord.channels` 白名單，印可讀性 + 最近一則訊息摘要。開跑前先確認 token 看得到哪些頻道、有無 403/40333（缺 `discord.user_agent` 會被 Cloudflare 擋，非權限問題）。
- **resolve**：`GET /guilds/{guild}/channels`，用 API 真實名稱回填 config 的 `channels[].name`；預設只印差異，`--write` 才回寫 config。
- 兩者複用 pull 的同一套 client（UA/429/唯讀），只 GET、不寫 Discord、只碰白名單。

### 1. init
產 `config.yaml`（頻道白名單、X query 清單、假名鹽、保留期、費控上限）、`state/`（增量游標）、`raw/`、`records/`、`cases/`、`reports/`。鹽值 `pseudonym_salt` 產生後**不得更換**，換了 player_key 全部斷鏈。

### 2. pull
- **discord**：讀 `config.discord.channels` 白名單，每個頻道從 `state/discord/{channel}.cursor` 的 `after` 往後拉，100 則一頁，429 依 `retry_after` 等，原始 JSON 落 `raw/discord/{channel}/{date}.jsonl`。不讀白名單外頻道、不讀 DM、不用 user token。
- **x**：先 `--estimate` 打 counts endpoint 估這個 query 過去 7 天有幾則，**估完才決定 `--max-posts`**；query 由 `config.x.queries` 命名管理，一律帶 `lang:ja -is:retweet`；每次呼叫寫 `state/x/spend.jsonl`（讀取則數 × 單價），累計超過 `config.x.daily_budget_usd` 直接停。`--dry-run` 只印 request 不打。

### 3. normalize
兩來源 → 同一 schema（`assets/schema-record.json`）：`record_id / source / surface / ts / author_key / player_key? / text / lang / url / reply_to / metrics / raw_ref`。
- Discord `author.id` → HMAC(salt) → `author_key`；若 `config.identity_map`（data-engineer 的對照表）可讀，補 `player_key`；**原始 ID 只留在 raw/**
- X `author_id` → 同樣 HMAC；username 不落 records
- 去重：文字正規化後 sha1 完全去重 + 3-gram Jaccard ≥ 0.9 近似去重（標 `duplicate_of`，不刪）

### 4. classify
`assets/lexicon.yaml` 規則分類（ja／zh／en 三語關鍵詞）→ `feedback_type`（沿用 player-voice schema：bug／balance／economy／event／ux／social／payment／praise／uncategorized），情感三值（lexicon 版；裝了 `oseti` 自動改用），簡單聚類（同 feedback_type 內 token 重疊）產 `cluster_id` 與代表句。
規則分不出的留 `uncategorized` 並輸出 `classify/llm-queue.jsonl`——**這才是交給 agent 用 LLM 判的那批**，不要拿 LLM 跑全量，費用與可重現性都差。

### 5. digest
產兩樣東西，都符合 ark-md-report 契約（frontmatter：verdict／findings／severity／confidence／sources／trust）：
- `reports/weekly/{week}-community-digest.md`：來源別統計、feedback_type 分布、情感分布、Top clusters（頻次＋代表句 ≤3 則＋涉及 player_key 數）、與上週比較、uncategorized 比例
- `cases/{week}/*.md`：每個 cluster 一張案件卡（player-voice 的 case 格式），只含 `player_key`／`author_key`

### 6. loop（閉環）
- `handoff`：列出本週可 ingest 的 MD 與建議 tags／trust，寫 `reports/weekly/{week}-handoff.json`。**worker 沒有 wiki_ingest**，這份清單交 leader 執行；Discord 來源 `trust: llm-distilled → seedling`，X 來源另加 `provenance: public-third-party`
- `compare`：讀 `knowledge/.../decisions/{id}.md` 的決策日期，比對決策前後各 7 天同 cluster 的頻次與情感，產 `reports/decisions/{id}-followup.md`。這一步讓「決策有沒有用」由下週資料說，不由報告自己說

交付訊息格式：`pull: discord {n} 則 / x {n} 則 (${cost})｜records {n}（dup {n}）｜uncategorized {pct}｜digest: reports/weekly/{week}-community-digest.md｜handoff: {n} 檔待 leader ingest`

## 硬規則

- 不用 user token、不跑 self-bot、不爬 X 網頁；只走官方 API
- Discord 原始 ID／暱稱、X username 不離開 `raw/`；`records/` 以後只有假名
- X 每次 pull 前必 `--estimate`；日預算寫在 config，腳本到頂就停，不由 agent 決定「再拉一點」
- 不回覆、不點讚、不追蹤任何帳號；本 skill 只有 GET
- 分類、情感、聚類是「候選」，不是結論；結論在 analyst 交叉分群後才成立
- raw/ 依 `config.retention_days` 清理（預設 90 天），records/ 保留

## 檔案

```
community/
├── config.yaml                 # 白名單、query、鹽、預算、保留期
├── state/                      # discord 游標、x spend 帳
├── raw/{discord,x}/            # 原始 JSONL（含 PII，加密磁碟，定期清）
├── records/{date}.jsonl        # 統一 schema，假名化
├── classify/{date}.jsonl + llm-queue.jsonl
├── cases/{week}/*.md
└── reports/weekly/ reports/decisions/
```

## 邊界

- 不做 Reddit／論壇／商店評論（researcher 的 market-intel 範圍，另開 skill）
- 不做 X 發文、回覆、DM；不做 Discord 發言
- 不做玩家分群（data-engineer 的 `ark-player-segment`）；本 skill 只吐 `player_key` 供 join
- 不決定 wiki 進不進：`handoff` 只是清單，ingest 與審核在 leader 與 ark-wiki-engine
