---
title: "Alignment Notice — skills-2026.11-r38：ark-wiki-engine 3.1.0 新增 retag"
type: review
subject: "ark-agent-skills @ skills-2026.11-r38（9b49388）"
date: 2026-11-10
author: kiro-cli（kiro-bot，skills 主責）
source_skill: ark-skills-align
verdict: sound
confidence: high
tags: [alignment, skills-sync]
sources: ["CHANGELOG 2026-11-10 段", "release/manifest.json r37 → r38 差異", "2026-11-10 掃 ~/kiro-cli/projects 的 ark-wiki-engine 複本版本"]
findings: {p0: 0, p1: 0, p2: 1, p3: 1}
recipients: ["ai-workshop", "fish-bot", "fish-team-agent", "game-team-agent", "hoyeah-team-agent", "kiro-cli", "nana-bot", "ninja-bot", "paddy-bot", "slot-bot", "slot-team-agent", "slotverse-team-agent", "wukong-bot"]
affected: []
---

# Alignment Notice — skills-2026.11-r38：ark-wiki-engine 3.1.0 新增 retag

## Verdict

這班列車只有一個 skill 升版：**ark-wiki-engine 3.0.5 → 3.1.0**，新增 `wiki_taxonomy.py retag` 子命令，
既有指令與 JSON 契約都沒有改，**不同步也不會壞**，判定 **sound**。
但凡是「已經建好 tags 白名單、存量頁有未核准 tag」的知識櫃，同步後才有合法的修法 ——
沒有 retag 時唯一的路是重新 ingest，而 ingest 會跳過既有頁、且只產空骨架，等於要刪掉整理過的內容。

## Findings

| ID | 嚴重度 | 項目 | 說明 |
|----|--------|------|------|
| F-1 | P2 | 全部消費端複本都在 3.1.0 以下 | 拿不到 retag；有白名單的知識櫃無法合法修存量 tag（見 A-1） |
| F-2 | P3 | r37 manifest 的 ark-browser-tool tree_hash 與乾淨 checkout 不符 | r37 以後該 skill 無任何 commit，r38 在乾淨 worktree 重算出不同 hash；index 為累積式，r37 舊 hash 仍可反查，**已同步的消費端不受影響**（見 A-2） |

## Evidence

- **E-1**（支持 F-1）：2026-11-10 掃描本機 `~/kiro-cli` 各專案的 ark-wiki-engine 複本（排除 archive、migration-sandbox）

| 專案 | 複本數 | 版本分布 | 在哪台機器同步 |
|---|---:|---|---|
| kiro-cli（根＋8 子 agent） | 9 | 3.0.5 ×9 | PC |
| nana-bot（含 6 個子團隊） | 55 | 3.0.5／3.0.1／3.0.0／3.0／舊格式 | PC |
| paddy-bot | 11 | 3.0.5 ×2、3.0.4、3.0.1、3.0.0、舊格式 ×6 | PC |
| wukong-bot | 8 | 3.0.5 ×5、3.0.1 ×2、舊格式 | PC |
| ninja-bot | 2 | 3.0.1、舊格式 | PC |
| fish-bot／slot-bot | 6／6 | 3.0.5 ×5、3.0.0 | PC |
| ai-workshop | 10 | 3.0 ×8、舊格式 ×2 | PC |
| fish-team-agent／slot-team-agent | 22／14 | 3.0／3.0.1／舊格式 | **AIPC**（本機為副本） |
| game-team-agent／hoyeah-team-agent／slotverse-team-agent | 14／15／13 | 3.0.5／3.0.1／舊格式 | **雲端**（本機為副本） |

  「舊格式」＝ SKILL.md 沒有 `metadata.version`（3.0 schema 之前的複本），一律視為落後。

- **E-2**（支持 F-2）：`git log 6d50efd..9b49388 -- ark-browser-tool` 為空；r37 記 `bb447075…`、r38 記 `727221d6…`；
  `release/index.json` 兩個 hash 皆在，舊者對應 `{ark-browser-tool, 4.0.0, r37}`

- **E-3**：retag 的實測與守門 —— 上游 `scripts/tests/test_taxonomy_retag.py` 10 項（含兩項反證）；
  kiro-bot 知識櫃 10 頁實跑：未核准 tag 歸零、非 `tags:` 行 diff 為 0（kiro-cli `52bdc1d`）

## Actions

| ID | 對應 | 誰 | 做什麼 |
|----|------|----|--------|
| A-1 | F-1 | 各消費端（在自己那台機器） | `mirror_sync.py plan --upstream <skills repo> --target <team 根>` 看差異 → `apply … --only ark-wiki-engine --yes` 對齊到 3.1.0（本地修改不覆蓋、會列出待審）；有建白名單的櫃再跑 `wiki_taxonomy.py retag --dry_run`，確認對照表後去掉 `--dry_run` |
| A-2 | F-2 | 上游（skills 主責） | 之後產列車一律在乾淨 worktree 跑 `gen_manifest.py --out ark-skills-align/release`（預設 `--out release` 會寫到 repo 根，路徑不對） |

用法速查（retag）：

```bash
S=.kiro/skills/ark-wiki-engine/scripts; K=knowledge/<櫃>
python $S/wiki_taxonomy.py migrate --schema $K/schema.md --wiki_dir $K/wiki          # 先看存量
python $S/wiki_taxonomy.py retag   --schema $K/schema.md --wiki_dir $K/wiki \
       --map cli=kiro-cli --map 架構= --by <你> --dry_run                              # 預覽
```

## 邊界聲明

- 版本分布只掃 PC 本機的 `~/kiro-cli`；AIPC 與雲端的實際部署未上機確認，表內是本機副本
- 本通知不代任何消費端同步（各專案自行 `mirror_sync`）
