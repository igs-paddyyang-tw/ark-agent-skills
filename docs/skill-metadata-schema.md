---
title: "Skill Metadata Schema"
type: reference
created: 2026-08-11
---

# Skill Metadata Schema

> 所有 SKILL.md frontmatter 必須遵循此規格。

## 欄位定義

```yaml
---
name: string                    # 必填。skill 唯一識別名（ark-xxx）
description: string             # 必填。觸發描述 + negative trigger
metadata:
  author: string                # 必填
  category: enum                # 必填。八大分類之一
  outputs:                      # 必填。至少一項
    - format: enum              # md | html | code | data | png | pdf | office
      audience: enum            # ai | human | both
  render: enum                  # 選填。html | none（預設 none）
  depends_on: string[]          # 選填。依賴的其他 skill 名稱
---
```

## category 合法值

| 代號 | 名稱 | 說明 |
|------|------|------|
| `process` | 流程鏈 | 拷問 / 規格 / 執行 / 驗證 |
| `scaffolder` | 平台生成器 | 產出專案骨架 |
| `pipeline` | 管線元件 | Python 模組 / 結構化資料 |
| `view` | 呈現層 | HTML / 視覺輸出 |
| `document` | 文件輸出 | MD / Office |
| `domain` | 領域 SOP | 策略 / 分析 |
| `ops` | 維運 | 診斷 / 驗證 |
| `executor` | 執行器 | 捆綁可執行 `scripts/`，agent 直接以 bash 呼叫 |

## outputs.format 合法值

`md` | `html` | `code` | `data` | `png` | `pdf` | `office`

> ⚠️ 2026-09-04 訂正：原本列 `xlsx` / `pptx` / `docx` 且缺 `data`，
> 與守門 `audit_skills.py` 的 `OUTPUT_FORMATS` 分岔 —— 全庫實際只用到
> `md` / `code` / `html` / `data` 四種，Office 檔一律歸 `office`。
> **本節以 `OUTPUT_FORMATS` 為準**（讀規格的人會照著設，寫錯會被 P2 擋下）。

## outputs.audience 合法值

`ai` | `human` | `both`

## 範例

```yaml
---
name: ark-code-spec-validator
description: |
  驗證 code 與 spec/design 文件的一致性，產出 Drift Report。
  不適用於：line coverage 分析（改用 ark-test-runner）。
metadata:
  author: paddyyang
  category: process
  outputs:
    - format: md
      audience: both
  render: none
  depends_on: [ark-superpowers]
---
```

## Lint 規則

- `name`：必須以 `ark-` 開頭
- `category`：必須為上述 8 個 enum 之一
- `outputs`：至少一項，format 和 audience 皆為合法 enum
- `description`：建議包含「不適用於→改用 X」negative trigger
