---
name: ark-skills-align
description: |
  [DEPRECATED — 已併入 ark-skills-sync（skills 生命週期：專案安裝／更新／健檢、回貢上游、稽核、整併、發列車）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：ark-agent-skills repo 的對齊、同步與稽核專用 skill。
  使用此 skill 當使用者要求「對齊 ark-agent-skills」「同步 skill 庫」「稽核 skill 庫」「整併 skills」
  「合併重複 skill」「回填 skill metadata」「檢查觸發詞衝突」「執行 skills 整併計畫 / alignment directive」，
  或消費端「對齊 team 的 skill 版本」「升版 skill」「這個 agent 的 skill 是哪一版」。
metadata:
  version: "3.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-11-13
  category: ops
  form: instruction
  domain: general
  author: paddyyang
---

# ark-skills-align（已併入 ark-skills-sync）

2026-11-13 起，整套內容（腳本、references、列車 release/）搬到 **`ark-skills-sync`**，並新增專案端入口
`skills_sync.py`（status／plan／update／install／remove／doctor／residue）。規範與情境路由見 `ark-skills-sync/SKILL.md`。

```bash
python3 <ark-agent-skills>/ark-skills-sync/scripts/skills_sync.py status
```

消費端若還沒有 `ark-skills-sync`（mirror_sync 不會自動安裝新 skill）：

```bash
git -C ~/kiro-cli/github/shared/ark-agent-skills archive HEAD ark-skills-sync | tar -x -C .kiro/skills/
```

## 過渡期相容

`scripts/` 底下保留同名轉呼檔（argv 原封轉給 `../../ark-skills-sync/scripts/` 的同名腳本），讓寫死舊路徑的
套件 `skills_verify`、各專案 wrapper 與文件繼續可用。列車 manifest 改在 `ark-skills-sync/release/`（r40 以前的在本目錄歷史裡）。

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 3.0.0 | 2026-11-13 | **Breaking**：併入 `ark-skills-sync`，本目錄只留轉址與轉呼腳本 |
