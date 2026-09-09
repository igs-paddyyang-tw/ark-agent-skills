---
title: "Telegram UX — 提詞模板準則（方案 A · v2）"
type: playbook
scope: shared
version: 2
date: 2026-09-09
source: [docs/reports/2026-08-06-telegram-ux-message-analysis.md, docs/reports/2026-08-07-telegram-ux-optimization-proposal.md]
tags: [telegram, ux, prompt-template, agent-output, formatting]
aliases: [tg-ux-prompt-templates, TG 模板, Telegram 輸出準則, 提詞模板準則, Telegram 訊息模板規範]
created: 2026-08-07
updated: 2026-09-09
status: stable
changelog:
  - "v2 (2026-09-09): 對齊套件實際行為 — 新增抬頭產生權責分工(套件畫T1-T5抬頭)、雙軌格式規則(template=Markdown / style=report=HTML 互斥)、reply() 參數對應表、T9 魚機成效日報+10條必檢清單、模板指派表。T6/T7 改標為套件自動產生僅供參考。"
  - "v1 (2026-08-07): 初版方案 A 準則，T1-T8 模板 + 紅線 + 長度上限。"
---

# Telegram UX — 提詞模板準則（v2）

> **適用場景**：Agent 輸出到 Telegram 時套用本準則，確保格式一致、手機易讀。
> 方案 A：在 SOUL.md / scheduler prompt 中直接引用對應模板，零程式碼改動。
> **v2 對齊套件實際行為**：T1–T5 抬頭由套件產生，agent 只寫內文；T8/T9 全版面自寫；T6/T7 由套件自動產生。

---

## 一、通用規則

### 1.1 格式（雙軌，互斥）

- **T1–T5**（`template=`）→ 寫 **Markdown**，套件負責轉 HTML
- **T8／T9**（`style="report"`）→ 寫 **Telegram HTML**（`<b>` `<i>` `<code>`），自控且不轉義
- 🚫 兩者**不可混用** —— 走 `template=` 卻寫 `<b>` 會被跳脫成可見文字
- 單則訊息上限 **4000 字元**，超過須截斷並補 `↪️ 續` 前綴
- 結論先行：第一行說結果，細節在後
- 每區塊用 emoji ＋ 粗體標題開頭（`**標題**` 或 `<b>標題</b>`，依上面選定的模式）
- 多項用條列（`- ` 或 `•`）；🚫 **禁用 Markdown pipe table**，手機 TG 會擠成一團
- 禁止輸出 raw stack trace、shell stdout、檔案列表

### 1.2 長度上限（依訊息類型）

| 類型 | 上限 |
|------|------|
| 狀態回報 | 150 字 |
| 任務更新 | 100 字 |
| 日報摘要 | 400 字 |
| 錯誤通報 | 80 字 |
| 閒聊回覆 | 100 字 |

### 1.3 `reply()` 參數對應

| 情境 | 參數 |
|------|------|
| 一般回覆、路由確認 | `style=chat`（預設） |
| **T1–T5 五種標準報告** | **`template="<名稱>"`**（抬頭由套件畫，只寫內文 markdown） |
| T8／T9 自建版面 | **`style=report`**（自控排版，不加抬頭、不轉義，自己寫 HTML） |
| 補充說明 | `kind=followup`（加 ↪️ 前綴） |

> 🔴 **`template` 與 `style="report"` 互斥** —— 同時給的話 `template` 會被忽略。用 `template=` 時**不要**帶 `style`。

---

## 二、模板 T1–T9

| 模板 | 產生者 | 呼叫方式 |
|------|--------|---------|
| **T1–T5** | 🔧 **套件畫抬頭**，agent 只寫內文 | `reply(template="…")` |
| T8 成本警告 · T9 魚機成效日報 | **Agent**（套件無對應，自建全版面） | `reply(style="report")` |
| T6 決策請求 · T7 掛起通報 | 🔧 **套件全自動產生**（僅供參考，勿照抄） | — |

### T1–T5 的共同規則（重要）

抬頭由套件產生為 `{emoji} <b>{你的代號}｜{標籤}</b>` ＋ 分隔線，**你不要自己再寫一次**。

內文一律用 **Markdown**，套件會轉成合法 TG HTML：

| 你寫 | 轉出 |
|------|------|
| `**粗體**` | `<b>粗體</b>` |
| `- 項目` | `• 項目` |
| `` `code` `` | `<code>code</code>` |
| `~~刪除~~` / `*斜體*` | `<s>` / `<i>` |

- ✅ **不用擔心格式壞掉** —— 套件跳脫優先，寫壞也不會被 TG 退件
- 🚫 **不要在內文寫 raw HTML**（`<b>` 會被跳脫成文字）
- 抬頭沒有日期欄位 → **日期寫在內文第一行**

### T1 科技日報 ｜ `reply(template="news-daily")`

套件抬頭：`📰 <b>{代號}｜科技日報</b>`

**你只寫內文（markdown）：**
```
YYYY-MM-DD

**🤖 AI**
- {標題} — {一句話摘要}

**💻 開發工具**
- {標題} — {一句話摘要}

**🔒 資安**
- {標題} — {一句話摘要}

**🌐 綜合**
- {標題} — {一句話摘要}
```
每類別 1–3 則｜摘要 ≤ 30 字｜無新聞的類別直接省略

### T2 每日狀態回報 ｜ `reply(template="status-report")`

套件抬頭：`📊 <b>{代號}｜狀態回報</b>`

**你只寫內文（markdown）：**
```
MM/DD

**✅ 完成**
- {任務描述}

**🟡 進行中**
- {任務描述}（預計 {時間}）

**📌 明日計劃**
- {計劃描述}
```
每項 ≤ 20 字｜無進行中任務時省略該區塊

### T3 維運日報 ｜ `reply(template="ops-report")`

套件抬頭：`🛠️ <b>{代號}｜維運日報</b>`

**你只寫內文（markdown）：**
```
MM/DD

- **🟢 服務** {N}/{Total} running
- **🔄 重啟** {N} 次（{原因}）
- **⚠️ 異常** {描述 or 無}
- **💰 成本** ${spent} / ${limit}
```
無異常直接寫「無」｜成本保留兩位小數

### T4 任務派工通知 ｜ `reply(template="task-dispatch")`

套件抬頭：`📋 <b>{代號}｜任務派工</b>`

**你只寫內文（markdown）：**
```
- **🎯 任務** {標題}
- **👤 指派** {agent-name}
- **📄 規格** {docs 路徑}
- **✅ 驗收條件** {一句話}

⏰ 截止：{日期}
```

### T5 錯誤通報 ｜ `reply(template="error-alert")`

套件抬頭：`⚠️ <b>{代號}｜錯誤通報</b>`

**你只寫內文（markdown）：**
```
- **⚡ 服務** {instance-name}
- **❌ 錯誤** {簡短描述，不貼 exception}
- **🕐 時間** {HH:MM:SS}
- **🔄 處理** {自動重試 or 待人工}
```
錯誤描述 ≤ 30 字｜**禁貼完整 exception**｜需詳細 log 用 `log_to_leader()` 私下回報

### T6 決策請求 ｜ 🔧 套件自動產生（agent 無需照抄）

> 由 `ark_team_agent` 產生，**agent 不需要也不應該自己組這個格式**。本節僅作「套件會發什麼」的參考。

**L3 升級卡**（`telegram.py:send_l3_escalation_card`，發給 Paddy 私訊）
```
⚠️ <b>需要你拍板｜L3 請求 {req_id}</b>
來自：{requester}
問題：{question}
備註：{context_note}
```
Inline Button：`[✅ 批准] [❌ 否決] [🔄 改為 L2 授權 {decider}]`

**L2 拍板請求卡**（`decision_manager.py:_render_request_card`，發給決策者 topic）
```
🔔 拍板請求 {req_id} | 來自 {requester}
問題：{question}
選項：
  A. {選項A}
  B. {選項B}
⛔ 受阻任務：{tasks}
```

> **Agent 該做的是「回覆」而非「產生卡片」** —— 收到卡片後回一個 ` ```decision ` 塊
> （欄位：`decision_id` / `req_id` / `verdict` / `rationale` / `confidence`）。

### T7 掛起通報 ｜ 🔧 套件自動產生（agent 無需照抄）

> 由 hang detector（`telegram.py:notify_hang`）偵測閒置後**自動發送**，依 role 分流：
> admin／manager → 送提詞 ＋ 通知 Paddy（帶按鈕）｜leader／worker → 送提詞（靜默）。
> **agent 不需要也不應該自己組這個格式**。本節僅作參考。

```
ℹ️ <b>{代號}</b> 閒置超過 {N 分鐘 or N 小時}
上次活動：{HH:MM}　現在：{HH:MM}

已自動喚醒，等待回覆中。
```
Inline Button：`[🔔 喚醒] [🔁 重啟] [⏸ 暫停{代號}今日] [✅ 已知悉]`

二次無回應會升級（`notify_hang_escalation`），內容含閒置時長、可能原因與建議。

### T8 成本警告 ｜ `reply(style="report")` — 自建全版面

> 套件無對應模板。**整則版面由你寫 HTML**，含抬頭。

```
💰 <b>成本警告</b> — {代號}

今日消費：<b>${spent}</b> / ${limit}（{pct}%）
<code>{進度條}</code>

剩餘額度：<b>${remaining}</b>

<i>達上限後自動暫停，明日 00:00 恢復</i>
```
進度條 `████████░░`（10 格），filled = `pct // 10`

### T9 魚機成效日報 ｜ `reply(style="report")` — 自建全版面（必跑檢查表）

> 週期性核心產出。套件無對應模板，**整則版面由你寫 HTML**，含抬頭。
> **產出前必須逐條對照 `hoyeah/wiki/methodology/` 的檢查表**。

```
📊 <b>{M/D} 魚機成效日報</b> · {市場} · Asia/Taipei

<b>結論</b>：{一句話定性 —— 大客波動／結構性問題／設定面異常}

📈 <b>整體</b>（vs 7 日均）
• DAU {n}（{±x.x%}）
• 押注 {n} 萬億（{±x.x%}）
• 莊家淨贏 {n} 萬億（{±x.x%}）
• RTP {xx.xx%}（{±x.xx} 百分點）

🐋 <b>大客影響（Top 5）</b>
• Top5 RTP {xx.xx%} ｜ 散客 {xx.xx%}
• Top5 押注佔比 {xx%}（前期 {xx%}）
• ARPPU 中位數 ${x.xx}（{未移動／移動}）

🏛 <b>廳館</b>
• TableTypeIDKey={n} RTP {xx.xx%}，淨贏 {n} 萬億（{說明}）
• TableTypeIDKey={n} RTP {xx.xx%}，30 天破百 {n} 次

🎯 <b>建議</b>
• 短解：{建議砍 x% RTP／無需調整}
• 長解：{續查方向／無}
```

**產出前必檢（每條都有知識庫依據）**

| # | 檢查項 | 依據 |
|---|--------|------|
| 1 | RTP 一律 **小數點第二位** | `analysis-standards` §二 |
| 2 | 魚機用 **Top 5**（不是 Top 10） | `anomaly-diagnosis` 陷阱 #10 |
| 3 | 集中度需 **Top5 佔比 ＋ ARPPU 中位數**（組合拳缺一不可） | `whale-analysis` §三 |
| 4 | 廳館以 **TableTypeIDKey** 引用（名稱曾互換） | `fish-machine-mechanics` §一 |
| 5 | RTP 偏高的廳要查 **30 天破百次數**（>3 次＝慣性漏水，找企劃） | `fish-machine-mechanics` §一 |
| 6 | 用 **7 日滾動均值**，不做日對日 | `fish-machine-mechanics` §一 |
| 7 | 結論即使是「運氣波動」也要給 **短解＋長解** | `analysis-standards` §一 |
| 8 | 標明 **市場範圍與時區**（預設 Asia/Taipei） | `analysis-standards` §二 |
| 9 | 散客 RTP 須 **BQ 實查**，不可心算 | `anomaly-diagnosis` 陷阱 #2 |
| 10 | 用「**大客**」不用「鯨魚」；「**莊家淨贏**」不用「水位」 | `analysis-standards` §二 |

⚠️ **禁用 Markdown pipe table** —— 手機 TG 會擠成一團，一律用 `•` 條列。

---

## 三、禁止事項（紅線）

| ❌ 禁止 | ✅ 替代 |
|--------|---------|
| 貼 stack trace／exception 全文 | 錯誤描述 ≤ 30 字 ＋ `log_to_leader` |
| 貼 git log／commit list | 僅摘要（改了什麼，一句話） |
| 貼檔案列表 | 只列數量或路徑 |
| 超過 4000 字元不截斷 | 截斷 ＋ `↪️ 續` |
| 走 `template=` 卻寫 raw HTML | 寫 Markdown，套件負責轉換 |
| 走 `style="report"` 卻寫 Markdown | 寫 HTML，report 模式不轉換 |
| `template=` 與 `style="report"` 同時給 | 擇一（同時給 template 會被忽略） |
| 自己重畫 T1–T5 的抬頭 | 抬頭由套件產生，只寫內文 |
| 凌晨傳成本恢復通知 | 靜默，次日互動時再附帶提示 |
| Rate Limit 廣播給所有私聊 | 只發給 admin／manager |

---

## 四、模板指派

> ⚠️ **T6／T7 不列入指派** —— 由套件自動產生，agent 無需（也不應）照抄。

| Agent | 主用模板 | `reply()` 呼叫 |
|-------|---------|---------------|
| `admin-agent` | T3 維運日報 | `template="ops-report"` |
| `admin-agent` | T5 錯誤通報 | `template="error-alert"` |
| `admin-agent` | T8 成本警告 | `style="report"` |
| `analyst-agent` | T2 每日狀態回報 | `template="status-report"` |
| `analyst-agent`（魚機日報） | **T9 魚機成效日報** | `style="report"` |
| `bi-engineer-agent` | T2 每日狀態回報 | `template="status-report"` |
| `tech-leader` | T5 錯誤通報 | `template="error-alert"` |
| `developer-agent` | T5 錯誤通報 | `template="error-alert"` |
| `ai-engineer-agent` | T1 科技日報（排程 `daily-news`） | `template="news-daily"` |
| `design-leader` | T4 任務派工通知 | `template="task-dispatch"` |

---

## 五、如何在提詞中使用

在 SOUL.md 或 scheduler prompt 末尾加入：

```
## 回覆格式規範

回覆到 Telegram 時，依內容類型套用以下模板（參考 tg-ux-prompt-templates）：
- 日報 → T1 科技日報 or T2 每日狀態回報
- 維運 → T3 維運日報
- 派工 → T4 任務派工通知
- 錯誤 → T5 錯誤通報

通用規則：
1. T1–T5 用 template=，寫 Markdown（套件轉 HTML、畫抬頭），你只寫內文
2. T8/T9 用 style="report"，寫 Telegram HTML，自控全版面
3. template 與 style="report" 互斥，不可同時給
4. 結論先行；單則上限 4000 字元，超過截斷
5. 禁止貼 stack trace / shell stdout / 檔案列表；禁用 Markdown pipe table
```

---

## 六、已確認不需改動的項目

| 項目 | 理由 |
|------|------|
| N3 掛起觸發邏輯（30 分鐘）| 每日 3 次上限已保護 |
| N6 成本警告 ASCII 進度條 | 視覺直覺，保留 |
| N9 崩潰恢復通知 | 非預期事件，通知有必要性 |
| /status 分組顯示結構 | 已優化過，結構清楚 |
