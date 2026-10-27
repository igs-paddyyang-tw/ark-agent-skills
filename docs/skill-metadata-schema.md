---
title: "Skill Metadata Schema（指路頁）"
type: reference
created: 2026-08-11
updated: 2026-10-20
---

# Skill Metadata Schema → 已移至 ark-skills-align

本檔曾是第三份 metadata 規格，與 `ark-skills-align/references/` 的兩份互相矛盾
（category 清單缺 `executor`、沒定義 schema 1.1、沒有 `status: experimental`）。2026-10-20 收斂為單一權威：

| 要查 | 去哪 |
|---|---|
| SKILL.md 欄位、schema_version、版號規則 | `ark-skills-align/references/metadata-schema.md` |
| category／form／domain 詞彙與判準、outputs 預設 | `ark-skills-align/references/taxonomy.md` |
| 詞彙的程式權威（守門） | `ark-skills-align/scripts/audit_skills.py` |
| 為什麼分類拆三軸 | `docs/specs/2026-10-20-skill-taxonomy-three-axis-spec.md` |
