---
type: test-report
contract: "1"
run_id: 20260918-ghy-aztec2-01
game: GHY 金猴爺 v4.6.8
machine: 阿茲特克2 Slot
platform: Android（BlueStacks 5，1600x900，serial 127.0.0.1:5555）
checklist: test-checklist.json @ sha256:…（124 項）
pack: games/ghy/machines/aztec2 @0.1
protocol: aiqa-protocol/1
model: <provider/model 釘版>
executed_by: aiqa
started: 2026-09-18T09:00:00+08:00
finished: 2026-09-18T12:42:00+08:00
---

# 測試報告 — 阿茲特克2 Slot — run 20260918-ghy-aztec2-01

> 示範用：數字為說明格式的假值。所有 PASS 皆附證據路徑；NEEDS_HUMAN 未計入 PASS。

| 摘要 | 值 |
|---|---|
| 測試項總數 / 本 run 執行 | 124 / 78 |
| PASS / FAIL / FLAKY / NEEDS_HUMAN / BLOCK / N/A | 61 / 3 / 2 / 9 / 3 / 46 |
| 自動化率（可自動得出判定 / 全部） | 63% |
| 與人工結果一致率（51 項有人工結果、aiqa 非 NEEDS_HUMAN 者） | 94%（3 項不一致，見 §4） |
| 誤 PASS（人 fail、aiqa PASS） | **0** |
| 執行時間 / LLM 呼叫 / 截圖 | 3 h 42 m / 412 / 1,806 張（保留 214 張） |

## 1. 依公司分類樹（可貼回 xlsx「總進度」）

| 類別 | 項目 | 測項 | PASS | FAIL | FLAKY | NEEDS_HUMAN | BLOCK | N/A | 進度 |
|---|---|---|---|---|---|---|---|---|---|
| 1.遊戲流程 | 1-1 Main Game | 18 | 14 | 1 | 0 | 2 | 1 | 0 | 100% |
| 1.遊戲流程 | 1-2 Free Game | 7 | 4 | 0 | 1 | 1 | 1 | 0 | 100% |
| 1.遊戲流程 | 1-4 buy bonus | 4 | 3 | 0 | 0 | 1 | 0 | 0 | 100% |
| 2.道具卡 | 2-1/2-2/2-3 | 11 | 8 | 0 | 0 | 2 | 1 | 0 | 100% |
| 3.特殊操作 | 3-1 Recover | 9 | 8 | 1 | 0 | 0 | 0 | 0 | 100% |
| 3.特殊操作 | 3-3 網路環境 | 26 | 5 | 0 | 1 | 0 | 0 | 20 | 100% |
| 3.特殊操作 | 3-4 裝置適配性 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | — |
| 3.特殊操作 | 3-5 掛測 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 100% |
| 4.UI功能 | 4-1 共用按鈕 | 8 | 7 | 1 | 0 | 0 | 0 | 0 | 100% |
| 5.遊戲畫面 | 5-1～5-4 | 29 | 10 | 0 | 0 | 3 | 0 | 16 | 100% |
| 7.音樂音效 | 7-1 | 14 | 0 | 0 | 0 | 0 | 0 | 14 | — |

## 2. FAIL（3）

### GHY-AZ2-MG-003 bet 推薦頁 — FAIL
- **斷言** A2 `visual` 宣傳圖不應破圖或模糊 — 期望「無」；實際「右下角宣傳圖缺角」（confidence 0.91）
- **證據** `items/GHY-AZ2-MG-003/rep-1/step-03-bet_recommend.png` · `roi-promo-zoom.png`
- **重現** `repro.md`：大廳 → tap 機台阿茲特克2（1188,512）→ 等 2.5s → 觀察推薦頁右下
- **規格** 規格書!大廳!Bet推薦頁 · **人工結果對照** fail（一致，Mantis 既有單）
- **Mantis 草稿** `mantis-drafts.md#GHY-AZ2-MG-003`

### GHY-AZ2-RC-006 Recover：FG 最後一手重啟 — FAIL
- A2 `ocr_number` 資產更新：期望「重啟後資產 = 離開前 + FG 總贏分」；實際差 −240（雙讀一致）
- 證據 `rep-1/step-05-credit-before-zoom.png` · `step-09-credit-after-zoom.png`；人工結果：pass（**不一致，見 §4**）

### GHY-AZ2-UI-004 右側共用 / 廣告 — FAIL
- A3 `state` 廣告看完應彈出領錢面板：實際 30 s 內未偵測到 state:ad_reward_panel，停在黑畫面
- 證據 `rep-1/step-06.png…step-12.png`（每 2 s）· logcat 無 FATAL；人工結果：無（常規測試未執行）

## 3. NEEDS_HUMAN（9）— 附裁切圖，建議一人 15 分鐘覆核
| id | 斷言 | AI 回答 | confidence | 圖 |
|---|---|---|---|---|
| GHY-AZ2-MG-001 | A2 連線亮框動態 | 「亮框有，動態是否完整不確定」 | 0.62 | rep-2/spin-07-board.png |
| GHY-AZ2-MG-011 | A4 彩虹樣式 | 「顏色漸層，疑似彩虹」 | 0.71 | rep-1/spin-19-mult-zoom.png |
| … | | | | |

## 4. 與人工結果不一致（3）— 最高優先看
| id | 人工 | aiqa | 判讀 |
|---|---|---|---|
| GHY-AZ2-RC-006 | pass（09-15） | FAIL（資產差 −240） | 可能為 FG 總贏分含 retrigger 未計入或本次真的有 bug；證據齊，請複驗 |
| GHY-AZ2-FG-002 | pass | FLAKY（3 次中 1 次剩餘次數讀值不符） | OCR 在轉場幀讀到舊值？已附三次裁切圖 |
| GHY-AZ2-MG-013 | pass | NEEDS_HUMAN | 兌線消除掉落方向視覺判定信心 0.66 |

## 5. BLOCK（3）— 需要人先做
| id | 缺什麼 | 建議 |
|---|---|---|
| GHY-AZ2-MG-007 聽牌表演 | harness:trigger1 未定義 | 測試員提供 trigger 下法 → 寫進 games/ghy/harness.yaml |
| GHY-AZ2-FG-005 buy bonus 升級流程 | 帳號等級 ≥ 100 | GM 調等級或提供高等測試帳號 |
| GHY-AZ2-IT-003 掃蕩卡 | 需持有掃蕩卡 | GM 發卡 |

## 6. FLAKY（2）
- GHY-AZ2-FG-002（見 §4）· GHY-AZ2-NET-002：2 次中 1 次「網路不穩符號」未偵測到（斷線時機落在停輪後）— 建議動作改為 spin 後 0.3 s 斷線

## 7. N/A（46）
- 3-3 網路：延遲 1000/3000 × 掉包 15/50 共 16 項（主機側工具未接）、CN 線路 3、ipv6 1
- 3-4 裝置適配 5（真機 / iOS）· 5-x iOS 畫面適配 16 · 7-1 音樂音效 14

## 8. 覆蓋：規格條目 → 測試項
- 規格書 62 條可測條目中 57 條有 ≥ 1 測試項；**缺 5 條**：Taco 包 A/C 條件、Buy Bonus 價格表、FG 上限手數、大獎分級門檻、winner list 顯示規則 → 建議 testgen 下一輪補
- baseline（人工表 124 項）對齊：aiqa 生成覆蓋 103 項（83%）；未覆蓋 21 項多為裝置 / 音效（N/A 類）

## 9. 附錄
- 環境：BlueStacks 5.21 · Android 9 · wm size 1600x900 · app com.igs.ghy v4.6.8 (build 2026091401) · serial 127.0.0.1:5555 · adb 35.0.1
- 預算：max_llm_calls 600（用 412）· 每項 timeout 300 s（超時 0）· 截圖保留策略 PASS 首末+斷言 / FAIL 全留
- 產出：`test-results.xlsx`（公司欄位回填）· `mantis-drafts.md` · `benchmark.json` · `items/<id>/…`
- 判定原則：視覺斷言不單獨撐 PASS；OCR 雙讀不一致 → NEEDS_HUMAN；重複不一致 → FLAKY；誤 PASS 為零容忍
