# test-checklist 契約 v1

雙軌：`checklist.json`（runner 唯一讀的來源）+ `test-checklist.md`（`aiqa_testgen.py render` 產出，人讀，含公司欄位對照與執行提詞）。

## 頂層
`{contract:"1", game, machine, pack_sha256, updated, count, items[]}`

## item
| 欄位 | 說明 |
|---|---|
| id | `<GAME>[-<MACHINE>]-<FOLDERCODE>-<nnn>`；模板項 `<GAME>-<TEMPLATE>-<nnn>` |
| title / category / folder | 對應公司欄位 測試目的 / 類別 / 項目；folder 必在 gamepack.taxonomy |
| tier / tier_reason | T1 可觀察 · T2 需 harness / 帳號狀態 · T3 網路 · T4 多實例 · T5 掛測 · NA 不執行（iOS / 真機 / 音效 / CN / ipv6） |
| repeat / priority | 重複次數（結果不一致 → FLAKY）/ P0–P2 |
| spec_refs / origin | 追溯：`規格書!sheet!cell`、`dev-spec:<claim key>`、`tester:<xlsx>!<sheet>#<row>`、`template:<name>` |
| preconditions | `[{type: screen|bet|credit_min|note, value}]` |
| manual_steps | 測試員原文步驟（import 時保留） |
| actions | 見下；含 `manual_step` 的項目執行時 BLOCK:NEEDS_BINDING |
| unbound_steps | 未被 bindings.yaml 綁到的步驟原文 |
| assertions | 見下 |
| block_if / na_if | 執行前 gate 條件（字串） |
| baseline | import 自公司表的人工結果 `{android, ios, tester, date, mantis}`，報告用來算一致率與誤 PASS |

## actions
| do | 參數 | 說明 |
|---|---|---|
| navigate | to | 依 pack.navigation 從目前畫面（模板比對）走到目標畫面 |
| tap | target(`btn:x`), wait?, timeout_s? | 模板命中座標優先，退回 pack xy |
| key | name | KEYCODE_<name> |
| wait | screen / state / seconds / until_popup(+record, since) , timeout_s | state 走 wait_stable |
| read | name, roi, oracle(ocr_number\|text) | 裁切放大 → reader（fake / tesseract / llm / dual）→ observations[name].append |
| capture | name, roi?, zoom? | 存證 |
| ask | name, question | 視覺是非題 → observations[name] = {answer, confidence} |
| repeat | times, actions | 巢狀 |
| macro | name, vars? | 執行 pack `macros/<name>.yaml`（按鍵精靈式確定性腳本，見 macro-sop.md）；ocr 值併入 observations；檢查點失敗 → BLOCK |
| restart_app / net(state) / harness(name) / crash_check / loop_spin(minutes, interval_s) / swipe | | harness 無 adapter → BLOCK |

## assertions
`{id, oracle, expr?, question?, obs?, when?, expect, expect_answer?, min_confidence?, spec_ref|origin, needs_binding?}`
- `expr` 用 safe_eval：可讀 observations 名稱（單值）與 `<name>_list`（累積）；函數 sum/len/all/any/abs/min/max/round/pairs/seq_multiplier/approx/nonempty；可用 `is None` / 生成式。
- `visual`：`question` 或 `obs`（指向 ask 的 name）；信心 < min_confidence（0.8）→ NEEDS_HUMAN；**不能單獨撐 PASS 的高風險判定**（報告會列）。
- `needs_binding: true`：import 時只猜到 oracle 沒有 expr；執行時 BLOCK，需人把預期結果寫成 expr 並指定 roi。

## verdict
PASS（全部斷言 PASS）/ FAIL（任一 FAIL）/ FLAKY（重複不一致）/ NEEDS_HUMAN（視覺信心不足、讀數 null、執行錯誤）/ BLOCK（gate 不過）/ NA。
