# Onboarding Gate — 上架守則

> 所有待上架 skill 必須通過以下四關，缺一不可。

## Gate 1：Schema v1 Frontmatter

- [ ] name 等於目錄名
- [ ] description 含觸發描述
- [ ] metadata.author 存在
- [ ] metadata.schema_version: 1
- [ ] metadata.category 在受控詞彙（proc/scaffold/pipeline/present/doc/sop/ops）
- [ ] metadata.outputs 至少一項
- [ ] metadata.status: active

## Gate 2：Taxonomy 歸屬

- [ ] ark-skills-align/references/taxonomy.md 已加入
- [ ] backfill_metadata.py CATEGORY_MAP 已同步

## Gate 3：Audit 清零

- [ ] audit_skills.py 對該 skill 無 P0/P1 findings
- [ ] 觸發詞矩陣無衝突（含 negative trigger 聲明）

## Gate 4：觸發回歸

- [ ] 2 個正向 prompt（應觸發本 skill）
- [ ] 1 個負向 prompt（不應觸發本 skill，應觸發指定替代）
- [ ] 結果記錄於 commit message
