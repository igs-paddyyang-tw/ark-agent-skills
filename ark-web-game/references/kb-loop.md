# skill＋知識庫回寫規則

> 這個 skill 是邊做邊長的：每做完一段工作，就把新的「做法」寫回 skill、把新的「事實」寫回知識庫。

## 1. 分工

| 內容 | 去處 | 例 |
|---|---|---|
| 怎麼做（步驟、指令、守門、格式） | `references/*.md` | 抽離七步、wire 指令表 |
| 可重複的動作 | `scripts/`＋`scripts/tests/` | trace 檢查、release pack |
| 發生過的事實、量測、踩坑、程式行為 | `knowledge/webgame/raw/<date>-<主題>.md`（只增不改） | 「Open House 最長劇本 12,3xx 字元」 |
| 為什麼、原則、跨案例的結論 | `knowledge/webgame/wiki/`（由 raw 蒸餾） | 「為什麼數學只能有一份來源」 |

同一段文字不在兩處複製；references 用「知識頁：W-xxx」連過去，wiki 頁用「做法見 ark-web-game references/xxx.md」連回來。

## 2. raw 筆記格式

```markdown
---
title: "<主題>"
type: source
captured: YYYY-MM-DD
captured_by: "<agent 或人>"
evidence: ["<路徑或指令>", "..."]
---
# <主題>
- 事實一（附出處：檔案:行、指令輸出）
```

raw 只寫看得到證據的事；推論寫到 wiki，並標「推論」。

## 3. wiki 頁

- 路徑 `knowledge/webgame/wiki/<分類>/W-0xx-<slug>.md`；frontmatter：title、type、tags（只用 schema 白名單）、created、updated、status、trust: llm-distilled、approved: false。
- 未經人工核可不得標 mature。
- 改完更新 `knowledge/webgame/index.md`，`log.md` 追加一段（只增不改）。

## 4. 守門指令（每次回寫都跑）

```bash
K=.kiro/skills/ark-wiki-engine/scripts; KB=knowledge/webgame
python $K/wiki_guard.py scan $KB/raw/<新檔>.md $KB/wiki/<改的頁>.md
python $K/wiki_taxonomy.py check --schema $KB/schema.md $KB/wiki/<改的頁>.md
python $K/wiki_lint.py --wiki_dir $KB/wiki --errors-only
python $K/wiki_index.py build --wiki_dir $KB/wiki && python $K/wiki_index.py freshness --wiki_dir $KB/wiki
python -m pytest .kiro/skills/ark-web-game/scripts/tests
python .kiro/skills/ark-prompt-spec-validator/scripts/prompt_lint.py .kiro/skills/ark-web-game/SKILL.md
```

沒有刪除權限時，重建索引前先把舊的 `.index` 搬到 `output/_trash/`。

## 5. 升版

- 只改 references 文字：patch。
- 新增腳本、指令或改流程：minor。
- 改 SpinResult、wire、Release Manifest 的格式：minor，且版本表註明「契約變更」，兩軌同步。
- 版本表每版一行：日期、改了什麼、依據（計畫任務編號或報告）。
