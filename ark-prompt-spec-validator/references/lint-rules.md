<!-- prompt-lint: ignore PL-004,PL-011,PL-013,PL-021 -->
# L1 Lint 規則清單（prompt_lint.py）

本檔列出所有偵測樣式，故以檔內指令關閉會被自身內容誤觸的規則（可稽核：報告標 ⏭️ ignored）。

規則 ID 穩定不重編；停用的規則保留 ID 並標 `retired`。
適用欄：`S` = skill、`P` = prompt、`C` = content、`*` = 全部。

## P0 — 直接 broken，不跑 L2

| ID | 適用 | 規則 | 為什麼是 P0 |
|----|------|------|------------|
| PL-001 | * | frontmatter 存在且 YAML 可解析 | 下游 agent 只讀 frontmatter 路由，壞了整份文件就不可見 |
| PL-002 | S | `name` == 目錄名 | 與 audit_skills.py 同級；載入器以目錄名索引 |
| PL-003 | * | 無隱形/雙向控制字元（U+200B/C/D、U+2060、U+FEFF、U+202A–E、U+2066–69） | 注入向量，與 wiki_guard 同標準 |
| PL-004 | * | 無提詞注入樣式（`ignore (all )?previous instructions`、`忽略(以上\|之前)(所有)?指令`、`you are now`、`system:` 行首偽裝） | 內文若含注入句，放給 agent 讀即中毒 |

## P1 — 規格不符，必修

| ID | 適用 | 規則 |
|----|------|------|
| PL-010 | S | `metadata.schema_version`、`category`（受控詞彙）、`outputs[].format/audience`（受控詞彙）齊全 |
| PL-011 | * | 無殘留 placeholder：`{{...}}`、`{TODO}`、`{TBD}`、`<填入...>`、`[TODO]`、`XXX`、`lorem` |
| PL-012 | * | 文中引用的相對路徑（`scripts/…`、`references/…`、`assets/…`、`evals/…`）實際存在 |
| PL-013 | * | 指令矛盾：同一名詞短語在 ±2 行內同時被「必須/一律/永遠」與「不得/禁止/絕不」修飾（heuristic，報 medium confidence） |
| PL-014 | P | 必要章節存在（預設：角色/職責、邊界/不做什麼、輸出格式；可用 config 覆寫 `required_sections`） |
| PL-015 | S | description 內「」引號觸發詞與 exclusive matrix 衝突（非 owner 卻宣告獨占詞）；`--repo` 時另比對其他 skill description 相同觸發詞 |
| PL-016 | S | description 內含「不適用於」或「請用 <other-skill>」排除段（觸發詞治理要求） |
| PL-017 | * | 引用的 skill 名稱（`ark-*`）在 `--repo` 內存在且非 deprecated stub |

## P2 — 品質，建議修

| ID | 適用 | 規則 |
|----|------|------|
| PL-020 | S | SKILL.md 本體 ≤ 500 行；description ≤ 1024 字元 |
| PL-021 | C,P | chunk 自足禁詞：「如上所述」「前者」「後者」「上面提到」「見上」 |
| PL-022 | C | Finding ID（F-n / D-n / A-n）連續無跳號、無重複 |
| PL-023 | S,P | 宣告會「產出/輸出」卻無「輸出格式」章節或程式碼區塊範例 |
| PL-024 | * | Markdown 標題層級跳級（`#` 直接到 `###`） |
| PL-025 | S | description 缺少「使用此 skill 當…」觸發句（觸發不足風險） |

## P3 — 風格

| ID | 適用 | 規則 |
|----|------|------|
| PL-030 | S,P | 模糊修飾詞計數 > 5：「適當地」「盡量」「可能的話」「視情況」「等等」 |
| PL-031 | S,P | 被動語氣/非命令式段落比例 > 30%（heuristic） |
| PL-032 | * | 表格欄數不一致 |

## 評分

`L1 = max(0, 100 − P1×15 − P2×5 − P3×1)`；任一 P0 → L1 = 0 且 verdict `broken`。

## 檔內指令

- `<!-- prompt-lint: ignore-file -->`：整檔跳過（fixture、規則目錄）
- `<!-- prompt-lint: ignore PL-011,PL-013 -->`：本檔停用指定規則；仍出現在報告 ignored 區，不會靜默消失

## config（.ark-prompt-validator.yaml）

```yaml
type_overrides:                    # 路徑 glob → type
  "steering/**/*.md": prompt
  "knowledge/**/wiki/**/*.md": content
required_sections:                 # 覆寫 PL-014，依 type
  prompt: ["角色", "邊界", "輸出格式"]
exclusive_triggers:                # 擴充 PL-015 矩陣（與 audit_skills.py 同格式）
  "提詞驗證": ark-prompt-spec-validator
ignore_rules: ["PL-031"]           # 停用規則（報告標 ⏭️ ignored，可稽核）
ignore_paths: ["**/node_modules/**"]
```
