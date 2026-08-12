---
title: "ark-code-spec-validator 與四段工作流鏈優化"
type: one-pager
status: draft
language: zh-TW
created: 2026-08-11
upgraded_to: null
---

# ark-code-spec-validator 與四段工作流鏈優化 — One Pager

## 問題與目標

四段工作流鏈（grill-me → superpowers → spec-executor → code-spec-validator）有 9 個問題（P1-P9），核心是：**drift score 不可信（P1-P2）、迴圈分流盲目（P3）、覆蓋比對不準（P4）**。導致「文件過時」被誤判為「需求不清」而觸發 30 題拷問，大專案易被誤殺、小專案易矇混。

**成功定義**：drift score 方向正確且大小專案差 < 5 分、文件過時不再觸發 grill-me、AC-ID 比對誤判率 = 0、閾值修改只改一個檔案。

## 方案

| 方案 | 優點 | 缺點 |
|------|------|------|
| A. 修文件與約定（本計畫） | 零 runtime 改動、git revert 即回滾 | 依賴 LLM 遵守規則 |
| B. 改 run_validator.py 程式碼 | 行為確定性高 | 改動範圍大、需測試 |
| C. 不改，人工補漏 | 零成本 | 每次迴圈浪費 token + 時間 |

**決策**：方案 A。所有變更為文件層（SKILL.md + dimensions.md + 新增約定檔），無 runtime 程式碼改動（僅 run_validator.py 一行 path 修正）。

## 執行計畫

| 階段 | 內容 | 時間 | 交付物 |
|------|------|------|--------|
| M1 正確性 | module path 統一 + schema 維度移出總分 + 定義評分公式 | 0.5d | SKILL.md + dimensions.md |
| M2 準確性 | 比例制評分 + AC-ID 約定 + ignore 配置 + plan 模板更新 | 1d | ac-id-convention.md + 4 模板 |
| M3 迴圈治理 | loop-rules.md 抽出 + 方向分流 + pipeline 狀態檔 | 1d | loop-rules.md + pipeline-state-schema.md |
| M4 可觀測性 | drift-report frontmatter + log.md 格式 + evals ×4 | 0.5d | 4 份 evals.json |

**依賴**：M1 → M2/M3 → M4（M2 和 M3 可並行）

**總計：3 天**

## 風險與驗收

**風險**：

| 風險 | 緩解 |
|------|------|
| AC-ID 回填遷移成本 | opt-in：有標註用精確匹配，無標註 fallback keyword（標示「低信度」）|
| 評分公式改動使歷史不可比 | log.md 加 `scoring_version`，日報分版呈現 |
| loop-rules.md 單獨安裝時缺依賴 | 每個 SKILL.md 保留一行摘要 + 引用 |
| pipeline.yaml 與 progress.json 重疊 | 明確分工：progress = 單次執行 / pipeline = 跨 skill 鏈級 |

**回滾**：全部文件層變更，`git revert` 即可。AC-ID 約定不強制，fallback 常駐。

**驗收條件**：
- [ ] M1：ark-team-agent repo 實跑 `--full`，報告總分與公式一致
- [ ] M2：8 端點小專案 vs 60 端點大專案，同 drift 比例分數差 < 5
- [ ] M3：注入三種方向 drift，分流建議正確（evals 驗證）
- [ ] M4：CollectorRunner 解析 log.md 產出 drift 趨勢條目

## 未決事項

1. Schema 維度 v2（request/response 比對）→ M1-M4 完成後再立案
2. pipeline.yaml 是否接 authority matrix（迴圈第 3 次走 L2 審批）
3. 閾值 90/70 是否依專案類型調整（庫 vs 服務 vs bot）
