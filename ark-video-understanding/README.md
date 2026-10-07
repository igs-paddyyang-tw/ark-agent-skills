# ark-video-understanding — [DEPRECATED → ark-game-spec 2.0.0]

> deprecation：2026-10-07 ｜ 保留至：2027-04-06 ｜ 遷移目標：`ark-game-spec/`（stage `video`）
> 本目錄只剩這份說明。影片 → evidence（抽幀 / 偵測器 / contact sheet） 的全部腳本、references 與測試已原封搬入 ark-game-spec 2.0（搬家不改語意，只改 import 與路徑）。

## 舊 → 新 對照

| 舊 | 新 |
|---|---|
| `ark-video-understanding/scripts/vu_run.py` | `ark-game-spec/scripts/video/vu_run.py` 或 `ark-game-spec/scripts/gs_run.py --stage video` |
| `ark-video-understanding/scripts/*.py` | `ark-game-spec/scripts/video/*.py`（檔名不變）|
| `ark-video-understanding/scripts/*_common.py` | `ark-game-spec/_lib/run_common.py`（pack_common / llm_adapter 亦在 _lib）|
| `ark-video-understanding/references/*` | `ark-game-spec/references/`（gdd 的 template-anatomy 改名 gdd-template-anatomy、vu 的 calibration 改名 video-calibration）|
| `ark-video-understanding/scripts/tests/*` | `ark-game-spec/scripts/tests/` |
| env `ARK_GAME_DOMAINS_SKILL` | `ARK_GAME_DOMAINS_DIR=<ark-game-spec>/domains`（舊 env 相容一版）|

消費端（aidev-team-agent 等）請改 steering 與 `.kiro/skills` 複本；詳見 `docs/alignment/2026-10-07-ark-game-spec-v2-notice.md`。
