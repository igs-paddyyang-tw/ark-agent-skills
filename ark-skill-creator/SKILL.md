---
name: ark-skill-creator
description: |
  建立新 Skill、修改和改善既有 Skill、測量 Skill 效能。
  使用此 Skill 當使用者想要從零建立 Skill、編輯或優化既有 Skill、
  執行評估測試 Skill、基準測試 Skill 效能（有/無 skill 對照）、
  或優化 Skill 的 description 以提升觸發準確度。
  不適用於：整庫批次稽核/合併/回填請用 ark-skills-align；
  提詞與 AI 內文的規格驗證請用 ark-prompt-spec-validator；
  code vs spec 一致性請用 ark-code-spec-validator。
metadata:
  schema_version: 1
  status: active
  updated: 2026-09-14
  version: "2.0"
  category: process
  outputs:
    - format: md
      audience: both
  author: paddyyang
---

# Skill 建立器

建立和迭代改善 Skill 的工作流。三條管線：**A 功能評估**（skill 值不值得存在）、
**B 觸發優化**（description 會不會在對的時機觸發）、**C 驗證交付**（打包前守門）。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `claude` CLI（Claude Code） | run_eval / run_loop / improve_description | 評估管線不可用；建立/改寫 skill 不受影響 |
| `pyyaml` | quick_validate / package_skill | 驗證與打包不可用 |
| 其餘 | — | 全部 stdlib |

## 資產地圖（先讀這張表再動工）

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/run_eval.py` | 觸發評估：對查詢集測 description 是否觸發 | 管線 B |
| `scripts/improve_description.py` | 依評估結果改寫 description（呼叫 `claude -p`） | 管線 B |
| `scripts/run_loop.py` | B 管線主迴圈：eval→improve 迭代，含 train/test 切分防過擬合 | 管線 B |
| `scripts/generate_report.py` | run_loop 結果 → HTML 報告（每次嘗試 ✓/✗） | 管線 B |
| `scripts/aggregate_benchmark.py` | 彙總各 run 的 grading.json → 均值/標準差/with-without delta | 管線 A |
| `eval-viewer/generate_review.py` | 讀 workspace、嵌入輸出、起本機 server 供人審查；回饋自動存 feedback.json | 管線 A |
| `eval-viewer/viewer.html` | generate_review 的頁面模板（勿直接開啟） | 由腳本載入 |
| `scripts/quick_validate.py` | 交付前守門：frontmatter 完整性 + ark schema v1 欄位 | 管線 C |
| `scripts/package_skill.py` | 打包 .skill（zip）；打包前自動跑 quick_validate | 管線 C |
| `agents/grader.md` | 子代理提詞：對照 expectations 評分 transcript/outputs，並反批 eval 品質 | 管線 A 步驟 4 |
| `agents/comparator.md` | 子代理提詞：盲測比較兩份輸出（不知何者有 skill） | 管線 A 步驟 4（主觀輸出用） |
| `agents/analyzer.md` | 子代理提詞：盲測揭盲後歸因勝負、產改善建議 | 管線 A 步驟 5 |
| `references/schemas.md` | skill.json / evals.json / grading.json 的 JSON Schema | 寫 eval 或解析結果時 |
| `scripts/tests/test_cli_contract.py` | CLI 契約守門：8 支腳本 `--help` 零依賴可跑、守衛先於第三方 import | 改任何腳本後 |
| `assets/eval_review.html` | ⚠️ deprecated：無程式引用的孤兒模板（真正的檢視器是 eval-viewer/），留待下次 alignment 移除 | 不載入 |

## 核心流程

1. 決定 Skill 要做什麼以及大致如何做 → 訪談（邊界案例、I/O 格式、成功標準、依賴）
2. 撰寫 Skill 草稿（見「撰寫指南」）
3. 建立測試提示詞（`evals/evals.json`，schema 見 `references/schemas.md`）
4. 管線 A：功能評估
5. 依回饋改寫，重複 4–5 直到滿意
6. 管線 B：觸發優化
7. 管線 C：驗證與打包

## 管線 A — 功能評估（有 skill vs 無 skill）

1. **雙盲執行**：對每個 eval，同時啟動兩個子代理（一個載入 skill、一個不載）執行相同 prompt，
   各自產出 `eval-N/{with_skill,without_skill}/run-M/`（transcript.md + outputs/）
2. **等待期草擬斷言**：好的斷言客觀可驗證；主觀輸出（寫作風格、設計）不硬套量化斷言
3. **記錄計量**：`total_tokens`、`duration_ms` 寫入 timing.json
4. **評分**：以 `agents/grader.md` 為提詞啟動評分子代理，逐 run 產 grading.json；
   主觀輸出改走 `agents/comparator.md` 盲測比較
5. **彙總與歸因**：
   ```bash
   python scripts/aggregate_benchmark.py <benchmark_dir>   # 均值/stddev/delta
   ```
   盲測結果以 `agents/analyzer.md` 揭盲歸因，產改善建議
6. **人工審查**：
   ```bash
   python eval-viewer/generate_review.py <workspace> [--previous-feedback <old/feedback.json>]
   ```
   讀 `feedback.json`：空回饋 = 使用者認可；聚焦有具體抱怨的案例

## 管線 B — Description 觸發優化

1. 產 20 個評估查詢（應觸發/不應觸發混合，真實、具體、有細節），存成 eval set
2. 與使用者審查查詢集
3. 執行優化迴圈：
   ```bash
   python -m scripts.run_loop --eval-set <path> --skill-path <path> --max-iterations 5
   ```
   （內部串 run_eval → improve_description，自動 train/test 切分；報告由 generate_report 產出）
4. 取 `best_description` 更新 SKILL.md frontmatter

## 管線 C — 驗證與交付

```bash
python scripts/quick_validate.py <skill_dir>    # frontmatter + ark schema v1（不足補齊再交）
python scripts/package_skill.py <skill_dir> [dist/]
python scripts/tests/test_cli_contract.py       # 若本次有改 scripts/
```
quick_validate 是本地快篩；入庫前的權威守門是 `ark-skills-align` 的 audit_skills.py。

## 撰寫指南

**結構**：`SKILL.md`（必要：frontmatter name/description + 指令本體）＋選用 `scripts/`（可執行）、
`references/`（按需載入文件）、`assets/`（輸出用範本）、`agents/`（子代理提詞）。

**漸進式揭露**（三層載入）：metadata（永遠在 context，~100 字）→ SKILL.md 本體
（觸發時載入，<500 行）→ 附帶資源（按需，無限制）。接近上限就往 references/ 分層；
大型參考檔（>300 行）附目錄。**SKILL.md 必須指向每一份會用到的資產**——
本檔的「資產地圖」就是範例：沒被指到的檔案等於不存在。

**風格**：命令式語氣；解釋「為什麼」而非堆疊 MUST；用範例展示 I/O；通用化不過擬合。
**description**：主要觸發機制，寫功能＋使用情境，稍微積極避免觸發不足；
必附 negative trigger 指向相鄰 skill（本檔 frontmatter 即範例）。

## 注意事項

- Skill 不得包含惡意程式碼或安全風險
- 測試查詢要夠實質——簡單一步驟查詢不會觸發 skill（AI 直接處理）
- 改任何 `scripts/*.py` 後必跑 test_cli_contract.py：`--help` 攔截必須在第一個第三方 import 之前
