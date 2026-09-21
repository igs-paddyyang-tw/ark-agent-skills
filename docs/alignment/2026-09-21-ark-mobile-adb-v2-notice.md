# Alignment Notice — ark-mobile-adb v1.x → v2.0（破壞性升版）

- **日期**：2026-09-21
- **skill**：`ark-mobile-adb`
- **變更類型**：major（1.x → 2.0，架構重寫）
- **commit**：`1c513ac`（47 檔，+3637/-728）
- **觸發**：pre-push 守門偵測到 major 升版（D-1 建議廣播）

## 為什麼是破壞性變更

v1.x 是**純裝置層**（Python CLI 包 adb：doctor/devices/tap/swipe/screenshot…）。
v2.0 在其上疊了一整套 **aiqa 遊戲 QA 鏈**，並移除了 v1.x 的舊入口檔：

| 動作 | 檔案 |
|------|------|
| 🗑️ 移除 | `DESIGN.md`、`README.md`、`install.sh`、`install.ps1`、`skill.json`、`tests/test_cli.py`、`examples/bluestacks.json`、`examples/game-loop.md` |
| ➕ 新增 | `scripts/aiqa_{testgen,run,report,oracle,device,fake_game,pack,llm,common}.py`、`gamepacks/`（demo-slot/ghy + 模板）、`references/`、`requirements.txt`、`scripts/tests/` |
| ✏️ 修改 | `SKILL.md`（version 2.0.0、觸發詞擴充）、`scripts/ark_mobile_adb.py` |

**破壞點**：任何直接引用 v1.x 路徑（`install.sh`、`skill.json`、`tests/test_cli.py`、
舊 examples）的消費端會斷鏈。裝置層 CLI（`ark_mobile_adb.py`）介面向後相容。

## 影響面掃描結果：0 消費者

上游做移除／改名就由上游負責掃消費端（本庫既有判準）。已掃：

| 掃描面 | 範圍 | 結果 |
|--------|------|------|
| `check_consumers.py --name ark-mobile-adb` | `~/kiro-cli/projects` | **0 處** |
| grep 全機引用 | `projects/` + `agents/`（含巢狀） | **0 檔** |
| 上游 repo 內引用 | role-skills-map / sync 矩陣 / SOUL | **0 處**（僅 skill 自身） |

→ **目前無任何 agent／專案裝了此 skill，沒有需要遷移的下游。**
此 notice 僅作破壞性變更的歷史記錄，供日後首次部署者參考。

## 守門驗證（收尾時）

- `py_compile`：10/10 腳本 OK
- CLI `--help` 契約：6 個主 CLI rc=0，零副作用
- `audit_skills.py --repo .`：RC=0，P0/P1=0，**ark-mobile-adb 本身 0 findings**，active=60

## 首次部署者須知

- 執行需 `adb` + Android/BlueStacks 裝置（真跑）；無裝置可用 `aiqa_fake_game` 合成測試驗腳本邏輯
- gamepack 校準（UI 地圖/ROI/模板圖）是使用時補的領域資料，非 skill 內建
- 三鐵律：AI 只看不判 / 無證據不 PASS / 做不到就 BLOCK
