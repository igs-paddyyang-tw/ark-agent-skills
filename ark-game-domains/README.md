# ark-game-domains — [DEPRECATED → ark-game-spec 2.0.0]

> deprecation：2026-10-07 ｜ 保留至：2027-04-06 ｜ 遷移目標：`ark-game-spec/`（stage `pack`）
> 本目錄只剩這份說明。domain pack 註冊庫（資料搬到 ark-game-spec/domains/） 的全部腳本、references 與測試已原封搬入 ark-game-spec 2.0（搬家不改語意，只改 import 與路徑）。

## 舊 → 新 對照

| 舊 | 新 |
|---|---|
| `ark-game-domains/scripts/pack_lint.py` | `ark-game-spec/scripts/pack/pack_lint.py` 或 `ark-game-spec/scripts/gs_run.py --stage pack` |
| `ark-game-domains/scripts/*.py` | `ark-game-spec/scripts/pack/*.py`（檔名不變）|
| `ark-game-domains/domains/**` | `ark-game-spec/domains/**`（原封，pack_sha256 不變）|
| `ark-game-domains/scripts/*_common.py` | `ark-game-spec/_lib/run_common.py`（pack_common / llm_adapter 亦在 _lib）|
| `ark-game-domains/references/*` | `ark-game-spec/references/`（gdd 的 template-anatomy 改名 gdd-template-anatomy、vu 的 calibration 改名 video-calibration）|
| `ark-game-domains/scripts/tests/*` | `ark-game-spec/scripts/tests/` |
| env `ARK_GAME_DOMAINS_SKILL` | `ARK_GAME_DOMAINS_DIR=<ark-game-spec>/domains`（舊 env 相容一版）|

消費端（aidev-team-agent 等）請改 steering 與 `.kiro/skills` 複本；詳見 `docs/alignment/2026-10-07-ark-game-spec-v2-notice.md`。
