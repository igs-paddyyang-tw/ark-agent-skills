# Alignment 操作手順

每類結構性操作的標準步驟。所有操作前先確認對應 Directive D-x 編號。

## §merge — 合併兩個 skill（如 D-1 ai-bot-builder → agent-builder）

1. **觸發詞移交**：source 的 description 中，target 沒有的觸發詞（含別名，如「ai-bot-builder」本身）併入 target description
2. **資產遷移**：source 的 scripts/、references/、assets/ 中 target 缺少的內容遷入；同名檔案 diff 後人工決定
3. **stub 化 source**：
   - 刪除 source 的 SKILL.md 與已遷移資產
   - 建 `README.md`：

```markdown
# <source-name>（DEPRECATED）

本 skill 已於 <YYYY-MM-DD> 併入 [<target-name>](../<target-name>/)。
觸發詞與功能已完整移交，請改用 <target-name>。

- 遷移對應：Directive <D-x>
- stub 保留至：<YYYY-MM-DD + 6 個月>
```

4. **全庫引用掃描**：`grep -rn "<source-name>" --include="*.md"` 找出其他 skill 對 source 的引用，改指 target

## §demote — 移除 skill、內容降級為文件（如 D-3 theme-factory、D-4 markdown-formatter）

1. 判定去向：操作型內容 → 目標 skill 的 `references/`；規範型內容 → repo 頂層 `docs/`
2. 內容遷移時改寫為「被引用文件」口吻（去掉觸發描述、加上「本文件被 X、Y skill 引用」）
3. stub 化（同 §merge 步驟 3，遷移目標寫文件路徑）
4. 至少讓 Directive AC 要求數量的 skill 在 SKILL.md 中引用新文件路徑

## §preset — 領域特化收編為基底 preset（如 D-5 data-dashboard、D-8 cost-tracker）

1. 萃取領域內容：資料模型、領域元件、領域指標定義 → 基底 skill 的 `references/<domain>-preset.md`
2. 基底 SKILL.md 增加一節「領域 preset」：說明何時讀該 preset（觸發詞：博奕/老虎機…）
3. 領域觸發詞併入基底 description
4. stub 化特化 skill
5. **回歸驗證**：用特化 skill 原本的典型 prompt 測基底 skill，確認能觸發且讀到 preset

## §backfill — schema v1 全庫回填

1. 跑 `python scripts/backfill_metadata.py --repo <repo> --dry-run` 看 diff
   （⚠️ 腳本**沒有** `--taxonomy` 參數，只吃 `--repo` 與 `--dry-run`）
2. 腳本只**新增** metadata 欄位（category/outputs/render/status/schema_version），不動 name/description/既有欄位
3. category **以 skill 現有 frontmatter 為準**；完全缺失時才用腳本內建推薦表起始值。
   outputs 依 taxonomy.md 各類預設值填，例外清單人工複核
   （例：chart-generator 在 pipeline 類但 outputs 是 png）
4. 去掉 --dry-run 實際寫入 → 跑 audit 確認 missing-category / missing-outputs 清零

## §triggers — 觸發詞治理

1. 依 Directive 第 3 節矩陣逐條處理：從非 owner 的 description 移除獨占詞，改用不衝突的表述
2. 每改一個 skill 的 description，在 commit message 附 3 個觸發測試 prompt：
   2 個應觸發（用 owner 場景）、1 個不應觸發（用被移除詞的場景）
3. 改完跑 audit 的 trigger-conflict 檢查清零
4. 新發現的衝突（audit 抓到但矩陣沒有的）：先回報使用者定 owner，再寫入 audit_config.yml

## §readme — README 分類表重寫

1. README 分類表**由 frontmatter 生成**，不手寫：讀全庫 category 欄位分組，每 skill 取 description 第一句作定位
2. 格式：兩層（category × skill），另附 deprecated stub 清單（含日期）
3. 生成後跑 audit 的 readme 一致性檢查

## Commit 規範

- 每個 D-x 一個 commit（Phase A 的觸發詞治理可以合一個）
- message 格式：`align(phase-X): D-n <動作摘要> [refs: alignment-directive]`
- Phase 收尾 commit 附 drift report 路徑
