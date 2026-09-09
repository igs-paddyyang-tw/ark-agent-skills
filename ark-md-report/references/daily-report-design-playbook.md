---
title: "日報設計 Playbook — 三段式產出與口徑踩坑"
type: playbook
scope: shared
date: 2026-09-09
source: [docs/one-pagers/2026-09-09-daily-report-scheduler-revamp.md, scheduler.yaml]
tags: [daily-report, scheduler, bq, revenue, rtp, telegram, t9, pipeline, methodology]
aliases: [日報設計, 三份日報, T9 日報, 日報排程, daily report playbook]
related: [tg-ux-prompt-templates, market-team-framework]
created: 2026-09-09
updated: 2026-09-09
status: developing
---

# 日報設計 Playbook — 三段式產出與口徑踩坑

> 2026-09-09 升級三份日報排程（產品成效／市場分析／營運活動）過程沉澱的可重複經驗。
> 涵蓋：日報通用設計原則、三份日報的職責與分工、BQ 口徑踩坑、落地流程。

## 一、三份日報總覽

| 日報 | Topic | job 名稱 | cron | target | 資料線 |
|------|:-----:|---------|------|--------|--------|
| 產品成效日報 | 4 | `daily-product-report` | 30 7 * * * | data-engineer | 內部 BQ |
| 市場分析日報 | 3 | `daily-market-report` | 0 8 * * * | researcher | 外部情報 |
| 營運活動日報 | 538 | `daily-activity-preference` | 45 6 * * * | data-engineer | 內部 BQ × 設定 |

**分工原則（Paddy 定，不可調換）**：外部資訊 → researcher-agent；內部數據 → data-engineer-agent。

## 二、日報通用設計原則（T9 規格）

所有日報對齊 `tg-ux-prompt-templates`(v2) 的 T9 全版面規格：

1. **三段式產出**：md（raw 存檔）→ TG（`reply(style="report")` 寫 HTML）→ HTML（artifacts/reports）
2. **三段結論句必須一致**：md / TG / HTML 的第一句結論完全相同
3. **強制先跑必檢清單**：產報告前逐條確認（如 10 條 T9 必檢），不可先寫完再回頭補
4. **結論先行**：第一行定性（波動／結構性問題／設定面異常），細節在後
5. **硬規則**：
   - RTP 一律小數點第二位；散客 RTP 須 BQ 實查不可心算
   - 用「大客」不用「鯨魚」；「莊家淨贏」不用「水位」
   - 🔢 大數字用中文單位（京/兆/億），禁科學記號
   - 用 7 日滾動均值，不做日對日
   - 🚫 禁用 Markdown pipe table（TG 手機會擠成一團，用 • 條列）
   - 標明市場範圍與時區（預設 Asia/Taipei）

## 三、BQ 口徑踩坑（重要）

### 3.1 表名：參考提詞 vs 知識庫實查不符

設計日報時，使用者參考提詞給的表名與知識庫實查口徑有出入。**一律以知識庫實查為準**：

| 用途 | 提詞寫的 | 知識庫實際口徑 |
|------|---------|---------------|
| Slot 老虎機 | DetailBetWinCustom | `bklog.SessionBetWinLog` |
| Fish 捕魚機 | FishSessionBetWinLog | `bklog.SessionTigerSharkBetWinLog` |
| DAU | SessionActive | `bklog.SessionActive`（✅ 一致） |
| 營收 | DailyRevenueReport / TotalBuyNumber | 見 3.2 |

**教訓**：日報設計時不能照抄提詞表名，要先用 wiki_query / grep 知識庫確認實際表名與口徑，否則排程跑出來會錯或查無表。

### 3.2 營收口徑衝突：整體 vs 活動級

- 提詞的 `DailyRevenueReport（SUM(TotalBuyNumber)）` 對應到的是**活動級**營收表 `preprocessed_bklog.DailyMissionRevenueLog`（欄位 TotalBuyNumber = 累計營收）。
- 但**整體平台營收**現行用 `bklog.GameConsume` 的 `SUM(BuyNumber)`。
- 兩者口徑不同、數字不同。**處理方式**：不替使用者猜，prompt 標為「data-engineer 先 dry-run 比對兩套數字，確認口徑後才產報告，並把選定口徑寫進報告 sources」。

### 3.3 排除測試帳號：LEFT JOIN 不用 NOT IN

- 🔴 `WHERE UserID NOT IN (SELECT UserID FROM App_Dragon.GameAccount)` 會讓 `SessionActive` **全表掃描 44.5GB**，超過 1 GiB 上限被擋。
- ✅ 改用 `LEFT JOIN App_Dragon.GameAccount ... WHERE ga.UserID IS NULL`，掃描量降到 ~37MB。

### 3.4 通用護欄（data-leader SOUL）

- 一律加 `WHERE LogDate`／`BQDate` 日期條件，防全表掃描
- dry-run 先確認掃描量再正式跑

## 四、命名慣例

- `knowledge/shared/raw/bq/` 每日報告檔名：**檔名日期 = 資料日期 = 昨日**（非執行日期）。
  - 例：09-04 07:30 執行 → 產出 `xxx-daily-2026-09-03.md`
- 判斷排程是否缺檔時，用「資料日期=昨日」對檔名，避免誤判缺檔。

## 五、落地流程

1. 讀 data-leader / analyst 的 steering + 知識庫確認口徑
2. 改 `scheduler.yaml` 對應 job 的 prompt（原地升級，不新增重複 job）
3. `python -c "import yaml; yaml.safe_load(...)"` 驗證 YAML 合法
4. 建好新產出目錄（如 `knowledge/hoyeah/raw/market-team/daily/`）
5. 重啟 daemon（寫 restart.flag）讓新排程生效
6. 實跑一輪驗證三段式格式與 topic 推送

## 六、待驗證項（2026-09-09 落地時未決）

- researcher 在雲端能否自動抓外部資料（市場日報全自動 vs 需人工餵資料）
- 產品日報營收口徑 dry-run 比對後定案
- 三份日報實跑一輪確認格式正確
