# ark-game-gdd — [DEPRECATED → ark-game-spec 2.0.0]

> deprecation：2026-10-07 ｜ 保留至：2027-04-06 ｜ 遷移目標：`ark-game-spec/`（stage `gdd`）
> 本目錄只剩這份說明。企劃規格書 gdd-pack / 素材總覽.html / 創作模式 的全部腳本、references 與測試已原封搬入 ark-game-spec 2.0（搬家不改語意，只改 import 與路徑）。

## 舊 → 新 對照

| 舊 | 新 |
|---|---|
| `ark-game-gdd/scripts/gdd_run.py` | `ark-game-spec/scripts/gdd/gdd_run.py` 或 `ark-game-spec/scripts/gs_run.py --stage gdd` |
| `ark-game-gdd/scripts/*.py` | `ark-game-spec/scripts/gdd/*.py`（檔名不變）|
| `ark-game-gdd/scripts/*_common.py` | `ark-game-spec/_lib/run_common.py`（pack_common / llm_adapter 亦在 _lib）|
| `ark-game-gdd/references/*` | `ark-game-spec/references/`（gdd 的 template-anatomy 改名 gdd-template-anatomy、vu 的 calibration 改名 video-calibration）|
| `ark-game-gdd/scripts/tests/*` | `ark-game-spec/scripts/tests/` |
| env `ARK_GAME_DOMAINS_SKILL` | `ARK_GAME_DOMAINS_DIR=<ark-game-spec>/domains`（舊 env 相容一版）|

消費端（aidev-team-agent 等）請改 steering 與 `.kiro/skills` 複本；詳見 `docs/alignment/2026-10-07-ark-game-spec-v2-notice.md`。
