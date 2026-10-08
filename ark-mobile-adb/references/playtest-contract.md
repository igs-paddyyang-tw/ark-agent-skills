# playtest 契約（playtest/1）：清單 md · run 目錄 · 事件 · 報告

## 1. 測試清單 md（輸入）

寬鬆格式，三種項目寫法可混用；`python scripts/aiqa_playtest.py parse 清單.md` 先看解析結果。

```markdown
---                                  # frontmatter 全部選填
title: 金猴爺 新手體驗測試
game: 金猴爺
package: com.igs.fafafa              # 用來讀版本、判斷 App 是否在前景
platform: BlueStacks 5（Mac）
account: 全新訪客帳號
budget_minutes: 210                  # 實際操作預算
explore: true                        # 是否做自我探索（預設 true；false 時報告不要求探索）
explore_budget: 40%
balance_floor: 100000
forbid: [不使用背包道具]              # 只能追加，預設禁止清單永遠生效
explore_focus: [預設押注]             # 也可寫在「探索重點」段
---

## 基本測試                           ← 標題含「基本 / 固定 / 必測 / 測試項」→ 基本測試段（沒有任何段落標題時全文都算）
### 登入與大廳                        ← 一般標題 = 分組（報告依分組出表）
- [ ] 開 App 進大廳，無閃退 ｜ 預期：看到大廳與餘額      ← 寫法 A：勾選 / 條列，「｜預期：」或「|」分隔
  - 子條列 = 步驟

#### B-010 規則對照                    ← 寫法 B：標題（可帶 ID）+ 步驟 / 預期 / 重複 / 證據 / 前置 / 備註
步驟：
- 開 i 讀規則
預期：觸發條件與次數一致
重複：3

| 編號 | 項目 | 步驟 | 預期 |          ← 寫法 C：表格（欄名含 編號/ID、項目/測試目的、步驟、預期）
|---|---|---|---|
| | 魚機能離開 | 開選單→按離開 | 回大廳 |

## 探索重點                           ← 含「探索 / 自我 / 自由」→ 條列成 explore_focus（給 AI 的提示）
## 禁止                               ← 含「禁止 / 不要做 / 安全」→ 追加 forbid
## 備註                               ← 含「備註 / 背景 / 環境」→ notes
```

- ID：寫了就用（`[A-Z][A-Z0-9-]*-\d{2,}`，例 `GHY-LB-002`、`B-010`），沒寫自動補 `B-001…`（跳過已用的號碼）；重複 ID → BAD_INPUT。
- 一項都解析不到 → `init` 回 GATE_BLOCKED（只做探索請加 `--allow-empty`）。

## 2. run 目錄

```
artifacts/playtest/<yyyymmdd>-<game>-NN/
  session.json        # 環境：game/package/app_version/platform/device/resolution/backend/started/finished/forbid/checklist_sha256
  checklist.md        # 原清單（複本）     checklist.json  # 解析結果（items / explore_focus / forbid / notes）
  events.jsonl        # 唯一事實來源（append-only）
  decision-log.md     # 人讀的決策紀錄（時間 | 看到的畫面 | 動作 | 原因）
  narrative.md        # Agent 寫的敘事段（init 放骨架）
  shots/S-0001-<label>.png  shots/_thumb/…   # 截圖與給 Agent 看的縮圖
  logs/logcat-*.txt
  report.html  summary.json  checklist.next.md   # report / promote 產出
```

## 3. 事件（events.jsonl，每行一筆）

共同欄位：`seq, ts, kind`。有 `id` 的事件可多次寫入，後寫覆蓋（`merged()`）。

| kind | id | 主要欄位 | 來源指令 |
|---|---|---|---|
| shot | S-0001 | file, label, caption, item, finding, explore, section, feature, fg | shot / spin |
| tap | T-0001 | x, y, (x2,y2 / key / gesture), why, target, outcome(ok/miss/early/noresp) | tap / swipe / key / mark |
| spin | — | machine, bet, n, ts_start, stopped | spin |
| item | 清單 id | verdict(PASS/FAIL/FLAKY/NEEDS_HUMAN/BLOCK/NA), actual, note, shots[], finding, block_reason | item |
| finding | F-001 | severity(高/中/低), category, title, detail, shots[], suggest, confirm, repro, where, item, explore | finding |
| explore | X-001 | heuristic(E1–E16), area, hypothesis, method, result, status(planned/issue/ok/inconclusive/skipped), finding, shots[] | explore |
| ledger | L-001 | label, before, after, bet, spins, win, expect_delta, delta, diff, match | ledger |
| popup | — | name, ptype(free/paid/info/external), action, price, shots[] | popup |
| game | — | name, gtype, rules_read, feature, win | game |
| segment | — | action(start/end), name, note | segment |
| logcat / crash_suspect | — | file, crash, fatal[] / where, logcat | logcat / spin |
| decide / init / finish | — | see, do, why | decide / init / finish |

實際操作時間 = 相鄰事件間隔加總（單一間隔上限 180 秒；`spin` 期間整段計入）。有效點擊率 = (ok + noresp) / 全部點擊。

## 4. 報告（report.html）

單檔 HTML，亮 / 暗色自動，手機寬度可讀；截圖縮成 JPEG 內嵌（`--img-width 720`、`--max-images 80`）。

| 區塊 | 來源 | 內容 |
|---|---|---|
| 標題列 | session | 起訖時間 · 平台 / 裝置 · 遊戲 package 版本 · 帳號 · 「事前沒有任何訓練」 |
| 摘要 | narrative「摘要」+ 自動 KPI | 基本測試通過數、問題數（高中低）、探索數、操作時間、點擊與有效率、遊戲數與特色次數、對帳、付費窗次數、截圖數 |
| 基本測試結果 | item | 依分組：編號 / 項目 / 預期 / 結果 / 實際 / 證據；FAIL 等附圖 |
| 發現的問題（依嚴重度） | finding | 「高」另列紅框；表格 + 證據圖牆 |
| 自我探索測試 | explore | 編號 / 方向（準則）/ 想驗證什麼 / 做法 / 結果 / 狀態 → finding |
| 敘事段 | narrative 其他 `##` | 流程卡、規則表、功能巡覽、圖牆、警示框 |
| 數據總覽 | segment / tap / ledger / popup / game / crash | 時間、點擊、對帳、彈窗整理（免費 vs 付費）、玩過的遊戲、閃退 |
| 優化建議 | finding.suggest | 依分類（穩定性 / 新手體驗 / 規則 / 介面 / 付費…）：優先度 / 現況 / 建議 |
| 做法與限制 | 自動 + narrative | 做法、兩段式、能 / 不能驗證、安全邊界 + 本輪特有 |
| 待辦 | 自動 + narrative | 未執行 / BLOCK / NEEDS_HUMAN / 需確認 / 探索無定論 + 人寫的 |
| 頁尾 | session | 原始資料路徑、清單 sha256；完整度檢查（摺疊） |

### 完整度檢查（`report --strict` 有錯誤 → exit 3）

錯誤：清單項未執行；PASS / FAIL 沒證據；BLOCK 沒寫原因；finding 沒證據；探索 0 項（`explore: true` 時）；探索仍 planned；探索 issue 沒連 finding；narrative 引用不存在的圖。
提醒：FAIL 沒對應 finding；finding 沒 suggest / category；對帳不符沒說明；有閃退紀錄但沒有穩定性 finding；沒寫摘要；圖片超過上限。

`summary.json`：verdicts、findings、explores、taps、有效率、spins、ledger、active_min、shots、lint——給日報 / wiki / 下游 agent。
