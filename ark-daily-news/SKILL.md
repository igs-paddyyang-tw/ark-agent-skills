---
name: ark-daily-news
description: |
  產出科技日報：MD-first 雙軌流程。先產出結構化 Markdown（Content 軌，給 AI/知識庫），
  再渲染 HTML 卡片（View 軌，給人看/發 TG）。
  支援手動輸入或串接資料來源結果，含 news_md_writer 步驟自動寫入 knowledge/raw/。
  使用此 Skill 當使用者提及科技日報、tech daily、產出日報、新聞日報、
  或任何需要將新聞轉化為 MD + HTML 雙軌產出的場景。
metadata:
  author: paddyyang
  schema_version: 1
  category: document
  version: "2.1"
  updated: 2026-08-13
  outputs:
    - { format: md, audience: ai }
    - { format: html, audience: human }
  render: html
  status: active
  depends_on: [ark-md-report, ark-html-report]
---

# ark-daily-news

科技日報 — MD-first 雙軌產出。

## 核心流程

```
爬蟲 → 解析 → 結構化 → 【save_md】→ 【render_html】→ 發 TG
                            ↓                ↓
                  knowledge/raw/         output/*.html
                  (AI 看/wiki ingest)    (人看/瀏覽器)
```

**原則：MD 是 source of truth，HTML 只是渲染視圖。**

## 觸發條件

- 「科技日報」「tech daily」「產出日報」
- 「新聞日報」「每日新聞」「news daily」
- 「日報模板」「產出日報 HTML」
- 「今日科技新聞」

---

## 步驟一：結構化新聞

將原始新聞轉為結構化 JSON：

```json
[{
  "topic": "AI 焦點",
  "title": "10 字內標題",
  "source": "來源",
  "news_date": "YYYY-MM-DD",
  "what": "100 字內摘要，關鍵詞用 <span class=\"hl\">包裹</span>",
  "why": "80 字內影響分析",
  "summary": "15 字內一句話總結",
  "urgency": "一般|關注|立即",
  "action": "具體行動建議（null 則不顯示）",
  "tags": [{"icon": "emoji", "text": "8 字內"}]
}]
```

## 步驟二：save_md（Content 軌）

```bash
python scripts/news_md_writer.py --json items.json --issue tech
```

落點 **`knowledge/raw/digest/<issue>/<date>.md`** —— 與排程管線
（ninja `digest/raw_writer.py`）同一個目錄樹與 frontmatter 契約。
舊版寫成 `raw/news-daily-{date}.md`，會讓同一種東西有兩個名字，
wiki ingest 端遲早漏掉其中一種。

腳本做三件手寫容易漏的事：

| 事情 | 為什麼 |
|------|--------|
| **拒絕覆蓋既有檔**（要 `--force`） | 同一天排程管線可能已寫過。靜默覆蓋會讓當天的收集素材無聲消失，而 raw 是唯一保留「被 `max_items` 砍掉的條目」的地方 |
| **寫入前跑 `wiki_guard scan`** | 素材來自外部網頁，正是提示注入／隱形字元要防的來源。檢查暫存檔而非目標檔 —— 寫進去才檢查等於已經污染目標目錄 |
| **guard 不可用時標記 `guard: unavailable`** | 「沒檢查」與「檢查過了」在下游是兩件事，不能靜默當成通過 |

必要欄位缺漏會擋下（`title` / `what` / `why`）。**缺 `why` 的新聞就只是轉述** ——
日報的價值在影響分析，不在轉貼標題。

### MD 格式規範

```markdown
---
title: tech 日報原始素材 · 2026-08-13
type: digest-raw
issue_type: tech
date: 2026-08-13
collected: 5
sources: [Anthropic Blog, GitHub]
generated_at: 2026-08-13T11:22:52+08:00
generated_by: ark-daily-news
guard: pass
tags: [digest, raw, tech]
---

# tech 日報原始素材 · 2026-08-13

## 1. 標題

**分類**：AI 焦點
**來源**：Google Blog
**緊急度**：立即

### 📋 發生了什麼
事件摘要...

### ⭐ 為什麼重要
影響分析...

### 💡 一句話總結
...

### 🎯 行動建議
...

**標籤**：`🤖 AI 模型` `💡 突破`

---
```

此 MD 可被：
- `ark-wiki-engine` ingest 為知識頁面 source（ingest 順序：guard → 萃取 → taxonomy → 落盤 → 索引重建）
- 其他 agent 直接讀取分析
- 排程管線的下游一併消費（形狀相同，靠 `generated_by` 區分來路）

## 步驟三：render_html（View 軌）

```bash
python scripts/render_news_html.py --md knowledge/raw/digest/tech/2026-08-13.md
```

**MD 是 source of truth，HTML 從 MD 渲染**：MD 改了重新渲染就會反映。
若兩軌各自從 JSON 生成，最後沒人知道哪個是對的。

腳本套 `assets/news-daily.html` 樣板，不自己寫 CSS —— 兩份 CSS 必然漂移。
它會剝掉樣板裡給維護者看的說明註解（約 3 KB），並在輸出前**檢查零外部請求**，
違規直接報錯：破圖的附件比沒有附件更糟，讀者會以為是自己網路的問題。

版式是「報頭 + 欄目 + 卡片牆」：日報常態 8~24 則，長列表要一路捲到底才知道
今天有什麼，而讀者多半先掃一遍再挑著讀。

| 項目 | 規格 |
|------|------|
| 佈局 | `grid auto-fill minmax(320px, 1fr)` —— 桌面多欄、手機自動單欄 |
| 主題 | 三態（系統偏好 + `data-theme` 蓋章），深色 token 只定義一份 |
| 字體 | 系統 stack，**不載入網路字體** |
| 外部資源 | **零** |

> ⚠️ **零外部請求是硬性條件**：這份 HTML 走 TG 檔案附件，讀者常在手機上離線開啟。
> 不得加入 CDN、`@import` 網路字體、遠端圖片或任何 `<script src>`。
> 完整規範與交付前檢查指令見 `../ark-html-report/references/offline-mode.md`。

所有由 LLM 或外部來源產生的文字，插入前必須逸出 `&` `<` `>` —— 一個沒逸出的 `<`
會吃掉後面整段內容。

## 步驟四：發送 Telegram

**兩段式**：先文字摘要，再 HTML 附件。

```bash
python ../ark-telegram-sender/scripts/tg_send.py text --topic daily_report \
    --file-text summary.txt --escape never
python ../ark-telegram-sender/scripts/tg_send.py file --topic daily_report \
    --path data/output/2026-08-13/tech-2026-08-13.html --caption "📅 科技日報 2026-08-13"
```

不要把長內容硬切成多則文字訊息 —— 會洗版，讀者也拼不回來。
摘要截斷 + 附件補完，並標明「其餘 N 則見附件」。

文字摘要格式：
```
📡 科技日報 {date}

⚡ 立即處理
• {urgent_title} → {action}

今日精選 N 則，完整分析見附件 👇
```

失敗語意、逸出策略、常見 400 對照見 `../ark-telegram-sender/references/delivery-sop.md`。
**摘要送不出去才算出刊失敗；附件失敗不算**（讀者已收到通知）。

---

## 完整鏈路

```bash
# ① 取材（新來源探勘用；常態來源請落成 collector，不要每天現爬）
#    ark-web-scraper

# ② 結構化 → raw MD（含 guard 前置）
python scripts/news_md_writer.py --json items.json --issue tech

# ③ 入庫
#    ark-wiki-engine：ingest raw/digest/tech/<date>.md

# ④ 渲染
python scripts/render_news_html.py --md knowledge/raw/digest/tech/<date>.md

# ⑤ 發送（兩段式）
python ../ark-telegram-sender/scripts/tg_send.py text --topic daily_report --file-text summary.txt
python ../ark-telegram-sender/scripts/tg_send.py file --topic daily_report --path <html>
```

> **這條鏈是「臨機路徑」**：適合一次性、新主題、還在探索來源的日報。
> 已經穩定每天出刊的刊別應該走程式管線（collector + 排程），
> skill 在那裡的角色是提供樣板與契約，不是每天執行。
> 兩條路徑的分工見 ninja `docs/plans/news-daily-skill-chain-plan.md`。

---

## 與其他 Skill 的關係

| Skill | 角色 | 何時用 |
|-------|------|--------|
| ark-web-scraper | 取材 | **只用於新來源探勘與一次性抓取**。常態來源請落成 collector —— 每天現爬會變成第二套來源定義，與程式管線漂移 |
| ark-wiki-engine | 消費 MD 產出，ingest 為知識 | 每次 save_md 之後 |
| ark-html-report | 定義 offline 交付規範（本 skill 的樣板即其實例） | 需要改樣板或做非日報型報告時 |
| ark-telegram-sender | 兩段式送達（摘要 + 附件） | 步驟四 |
| ark-md-report | 深度分析報告的文體與 frontmatter 契約 | **不在日報主鏈上** —— 它的五種 type（review／competitive／incident／decision／data）沒有 news 類，硬套會產生兩份互相矛盾的 frontmatter |

## 腳本

| 檔案 | 用途 |
|------|------|
| `scripts/news_md_writer.py` | 結構化 JSON → raw MD（guard 前置、拒絕覆蓋、必要欄位檢查） |
| `scripts/render_news_html.py` | raw MD → HTML 卡片牆（套樣板、剝說明註解、零外部請求檢查） |
| `assets/news-daily.html` | 版式樣板（報頭 + 欄目 + 卡片牆，含三種卡片變體的結構範例） |
