# Kiro Hook 配置說明

> 在 Kiro CLI 環境中自動觸發文件完整性檢查。

## 觸發條件

當 `docs/specs/`、`docs/designs/`、`docs/plans/`、`docs/one-pagers/` 下的 `.md` 檔案被編輯或建立時，自動執行 `check_doc_completeness.py` 驗證。

## 安裝方式

### 方式一：Git pre-commit hook

```bash
# 從 skill 資產複製到 repo
cp .kiro/skills/ark-superpowers/assets/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 方式二：Kiro Steering 配置

在 `.kiro/steering/` 下建立觸發規則（需 Kiro CLI 支援 hook 觸發）：

```yaml
# .kiro/hooks/doc-check.yaml
name: doc-completeness-check
trigger:
  fileMatch: "docs/**/*.md"
  events: [save, create]
action:
  script: .kiro/skills/ark-superpowers/scripts/check_doc_completeness.py
  args: ["${file}"]
```

## 檢查內容

1. **Frontmatter 完整性**：`title`、`status`、`created` 必填
2. **必要章節存在**：依文件類型（spec/design/adr/plan/one-pager）檢查
3. **空白章節偵測**：章節內容 ≥ 20 有效字元，排除 placeholder
4. **自動化驗證**：
   - Design/ADR：至少 2 個替代方案
   - Spec：NFR 含量化指標
5. **任務表契約**（Plan）：欄位數與角色值驗證

## 跳過方式

- Git hook：`git commit --no-verify`
- Kiro hook：不適用（建議修正而非跳過）

## 手動執行

```bash
# 檢查單一檔案
python3 .kiro/skills/ark-superpowers/scripts/check_doc_completeness.py docs/specs/my-spec.md

# 中英模板 parity check
python3 .kiro/skills/ark-superpowers/scripts/check_doc_completeness.py --parity

# 全套自我驗證
bash .kiro/skills/ark-superpowers/scripts/self_check.sh
```
