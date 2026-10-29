---
title: "Alignment Notice — 2026-10-29 skills 整併（r12～r16）與 ark-agent-cli 2.4 行為變更"
type: review
subject: "ark-agent-skills @ skills-2026.10-r16（015acde）"
date: 2026-10-29
author: claude-code（nana-bot，skills 主責）
source_skill: ark-skills-align
verdict: needs-work
confidence: high
tags: [alignment, breaking-change, skills-sync, deprecation]
sources: ["check_consumers.py（2026-10-29 21:30 掃 ~/kiro-cli/projects）", "CHANGELOG r12～r16", "ark-agent-cli 2.4.0 版本段"]
findings: {p0: 0, p1: 3, p2: 1, p3: 0}
recipients: ["ai-workshop", "fish-team-agent", "fish-bot", "game-team-agent", "nana-team-agent", "ninja-bot", "ninja-team-agent", "paddy-bot", "slot-team-agent", "slot-bot", "slotverse-team-agent"]
affected: ["ai-workshop", "fish-team-agent", "fish-bot", "game-team-agent", "nana-team-agent", "ninja-bot", "ninja-team-agent", "paddy-bot", "slot-team-agent", "slot-bot", "slotverse-team-agent"]
---

# Alignment Notice — 2026-10-29 skills 整併（r12～r16）與 ark-agent-cli 2.4 行為變更

## Verdict

上游一天內把 **16 個 skill 併入 5 個接手者**（active 62 → 48），並發布 ark-agent-cli 2.4.0。
舊名都留著轉址 stub，**不會斷**；但 `mirror_sync` 只會把舊目錄對齊成 stub，**不會自動安裝接手者** ——
只同步不安裝，agent 會失去那些能力。11 個消費端專案需要行動，判定 **needs-work**（需行動，非資料損毀）。

## Findings

| ID | 嚴重度 | 項目 | 說明 |
|----|--------|------|------|
| F-1 | P1 | 接手者未安裝 | 舊 skill 複本旁沒有接手者：同步後只剩轉址空殼（見 Actions A-1） |
| F-2 | P1 | sync 矩陣／SOUL.md 仍寫舊名 | 下次同步會裝到 stub、SOUL 宣稱的能力指向空殼（見 A-2） |
| F-3 | P1 | ark-agent-cli 2.4.0 行為變更（版號為 minor，pre-push 不會自動提醒） | sub-agent 預設唯讀；`exec` 含 shell 控制字元要 `--allow-shell`；`build_argv` 回三元組 |
| F-4 | P2 | 殘留 stub 可刪 | 接手者已在同一個 agent 的舊目錄，可刪可留（保留期兩班列車） |

## Evidence

- **E-1**（支持 F-1、F-2、F-4）：`check_consumers.py` 掃描結果（每專案各類處數）：

| 專案 | 缺接手者 | 矩陣寫舊名 | SOUL 寫舊名 | stub 可刪 | 要安裝 |
|---|---:|---:|---:|---:|---|
| ai-workshop | 12 | 13 | 0 | 8 | pipeline-recipes、quality-gates |
| fish-team-agent | 26 | 14 | 16 | 4 | pipeline-recipes、quality-gates、superpowers |
| fish-bot | 2 | 0 | 0 | 0 | quality-gates |
| game-team-agent | 34 | 0 | 0 | 13 | env-doctor、pipeline-recipes、quality-gates |
| nana-team-agent | 32 | 5 | 0 | 3 | env-doctor、pipeline-recipes、quality-gates |
| ninja-bot | 4 | 0 | 0 | 2 | pipeline-recipes、quality-gates |
| ninja-team-agent | 13 | 0 | 0 | 8 | pipeline-recipes、quality-gates |
| paddy-bot | 10 | 0 | 0 | 5 | pipeline-recipes、quality-gates |
| slot-team-agent | 16 | 14 | 17 | 4 | pipeline-recipes、quality-gates、superpowers |
| slot-bot | 2 | 0 | 0 | 0 | quality-gates |
| slotverse-team-agent | 17 | 16 | 20 | 4 | pipeline-recipes、quality-gates、superpowers |

- **E-2**（支持 F-3）：ark-agent-cli SKILL.md「2.4.0 — Breaking」段；目前**沒有任何 skill `depends_on` ark-agent-cli**，
  直接呼叫其程式的只有 paddy-bot 套件，且 `ark_bot_agent/agent/scripts/` 已對齊 2.4（三元組）

- **E-3**（支持 F-1、F-2，A-1／A-2 的對照）：舊名 → 接手者

| 列車 | 舊 skill（現為 stub） | 接手者 | 去哪裡讀 |
|---|---|---|---|
| r12 | anomaly-detector、chart-generator、cost-tracker、data-contract、etl-pipeline、kpi-calculator、llm-tools、translator | **ark-pipeline-recipes** | `references/<舊名去掉 ark->.md` |
| r13 | dashboard-health | **ark-env-doctor** | `env_doctor.py --endpoints／--sse` |
| r13 | uml-generator | **ark-superpowers** | `references/uml-diagrams.md` |
| r14 | project-planning、doc-coauthoring、planning-with-files | **ark-superpowers** | 工作模式 plan／coauthor／files |
| r15 | code-review、security-audit、test-runner | **ark-quality-gates** | `scripts/quality_gates.py`（可直接執行） |

## Actions

| ID | 動作 | 對應 Finding | 負責 |
|----|------|--------------|------|
| A-1 | 先裝接手者再同步：`cp -r <ark-agent-skills>/<接手者> .kiro/skills/`（各 agent 的 `.kiro/skills` 都要）→ `mirror_sync.py apply --upstream <ark-agent-skills> --target . --yes` | F-1 | 各專案 manager |
| A-2 | `sync_skills.py` 的 MATRIX／COMMON 與各 agent `SOUL.md` 的 skill 條列：舊名換成接手者（同一角色多個舊名合併成一個） | F-2 | 各專案 manager |
| A-3 | 用到 `agent_spawn.py` 的流程：要 sub-agent 改檔 → 明確加 `--access workspace`；`exec --cmd` 含 `\|`、`&&`、`>` → 加 `--allow-shell`；自己 import `build_argv` 的程式改收三元組 `(argv, stdin, prompt_file)` | F-3 | 用到 agent-cli 的專案 |
| A-4 | 接手者裝好後，舊 stub 可刪（或留到兩班列車後一起清） | F-4 | 各專案 manager |
| A-5 | 驗收：在 `~/kiro-cli` 跑 `.kiro/skills/scripts/check_consumers.py`，「已併入」段該專案歸零 | F-1、F-2 | 各專案 manager |

## 邊界聲明

- 本通知**不代消費端同步或改檔**（2026-10-27 定：各專案自行 `mirror_sync`）；上游只負責宣告與提供檢查工具。
- 數字是本機 PC `~/kiro-cli/projects` 的掃描當下狀態；**slot／fish／slotverse／hoyeah 的正本在 AIPC／雲端**，本機只是副本，實際以各環境自己跑 check_consumers 為準。
- 舊名 stub 保留期兩班列車；清除前會再發通知。
