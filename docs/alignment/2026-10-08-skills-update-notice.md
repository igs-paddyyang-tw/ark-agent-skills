# Skill 更新通知（2026-10-06 ~ 10-08）

> 給各消費端 agent：請照本文件把 `.kiro/skills/` 同步到上游最新版。
> **上游**：`igs-paddyyang-tw/ark-agent-skills`，`main` @ **`c261eb1`** 以後（release `skills-2026.10-r1`）
> **本文件位置**：skills repo 的 `docs/alignment/2026-10-08-skills-update-notice.md`（同步 skill 後就在 `.kiro/skills/docs/alignment/`）

## 1. 一句話

遊戲製程原本 7 個 skill，整併成 **ark-game-spec**（遊戲規格書）、**ark-game-prob**（機率規格書）、**ark-game-quicktest**（Go 快測）三個。**舊的 5 個 skill 已經刪除**。另外 ark-html-report 新增放圖引擎。

## 2. 版本對照（同步後應該要是這些版本）

| skill | 新版 | 舊版 | 等級 |
|---|---|---|---|
| `ark-game-spec` | **2.3.0** | 1.x | 🔴 破壞性（五合一） |
| `ark-game-prob` | **1.1.0** | （新 skill） | 🟢 新增 |
| `ark-game-quicktest` | **2.1.0** | 1.x | 🔴 破壞性（機率規格書腳本已移出） |
| `ark-html-report` | **1.2.0** | 1.0 / 1.1 | 🟡 新功能（需要 Pillow） |
| `ark-github-cli`、`ark-spec-executor` | 版本沒變 | — | ⚪ 只改了測試檔名 |

> ⚠️ **aidev 請注意**：你本地 `output/` 裡的 `ark-game-spec-2.2.0.zip`、`ark-html-report-1.1.0.zip` **已經合併進上游**，請改從上游同步 2.3.0 / 1.2.0，**不要再裝 output 裡的包**。
> 上游的 html-report 1.1.0 和你的 1.1.0 內容不同（版號撞了），1.2.0 兩邊的內容都有。

## 3. 已刪除的 skill（消費端要刪目錄、改引用）

| 已刪除 | 改用 |
|---|---|
| `ark-video-understanding` | `ark-game-spec`（`gs_run --stage video`） |
| `ark-game-analysis` | `ark-game-spec`（`--stage detect / analyze`） |
| `ark-game-gdd` | `ark-game-spec`（`--stage gdd`） |
| `ark-game-atlas` | `ark-game-spec`（`--stage atlas`） |
| `ark-game-domains` | `ark-game-spec/domains/`（`ARK_GAME_DOMAINS_DIR` 可以覆寫） |
| ~~`ark-game-design-doc`~~（10-01 已刪） | `ark-game-spec` 的「從構想產 GDD」創作模式 |

消費端要用 grep 清掉這些舊名字的引用，範圍包括 steering、agents、role-skills-map、sync matrix、skills.lock。

## 4. 破壞性變更（升級前先看）

1. **ark-game-spec 2.0：五合一**。入口統一用 `python scripts/gs_run.py --stage <video|detect|analyze|report|draft|decide|dev|restore|gdd|atlas|bundle|pack|all>`，旗標會原樣傳給各階段的腳本。
2. **ark-game-quicktest 2.0**：`qt_probspec` / `ps_lint` / `qt_probtable` 三支已刪。`qt_run --probspec` 會轉呼叫同一層的 `ark-game-prob/scripts/ps_run.py`，所以**兩個 skill 要一起裝**。
3. **ark-game-spec 2.1：gdd 圖夾改英文名**。`symbols/`、`illustrations/`、`spec-reference-images/` 取代原本的「圖騰／全示意圖／規格書競品圖」。舊的中文夾**讀取時還相容**，lint 會給 `GDD-ASSET-LEGACY` 警告；新產出一律用英文夾。
4. **gs_run 關閉旗標縮寫**（`allow_abbrev=False`）：旗標要寫全名，例如不能用 `--exp` 代替 `--export`。
5. **gdd_export 擋帶路徑的檔名**：`symbols/screens/info` 裡的 `file` 和 `ref_files` 只能寫純檔名（例如 `S1.png`），帶 `/`、`\`、`..` 或絕對路徑會 exit 3。

## 5. 新功能

| skill | 功能 | 指令 |
|---|---|---|
| ark-game-prob 1.0 | 機率表 xlsx → prob-data.json → prob-spec.md / html，加上 lint 和設定檔逐鍵對照（ps_diff） | `ps_run.py` |
| ark-game-prob 1.1 | 產 Excel（機率表／審核簿／檢核表，用活公式、每頁有總判定 OK/!/X、可偵測過期）；`verify_xlsx_formulas.py` 用 formulas 套件真的重算公式 | `ps_xlsx.py --kind …`、`ps_run --excel` |
| ark-game-prob | `ps_run --dest <dir>`：產物直接放進 `output/games/<slug>/prob/`，不再多一層 | |
| ark-game-quicktest | `qt_report --version-id <id>`：依 `quicktest.yaml.versions[]` 各版的 expect 給判定；道具卡可設 `rtp_denominator: item_price` | |
| ark-game-spec 2.1 | `gdd_export`：產出跟企劃樣板（kaiji-gdd-sample）同結構的交付夾 | `--stage gdd … --export [--export-out] [--export-all-assets]` |
| ark-game-spec 2.2 | **bundle**：競品分析 md 加上 gdd-pack，合成一份圖片內嵌的單檔 HTML（需要同層 ark-html-report ≥ 1.2） | `--stage bundle --bundle <bundle.yaml>` |
| ark-game-spec 2.3 | **restore 還原模式**：已上線的 ProbSetting JSON → `config-spec.yaml`（`mode: restore-live`，每個參數的 value 都是 `{$ref}` 指回設定檔，不抄數值） | `--stage restore --config <json> [--xlsx] --out output/games/<slug>/spec`、`--stage restore --check <config-spec.yaml>` |
| ark-game-quicktest 2.1 | qt_report 第③項檢查遇到 `mode: restore-live`，改成檢查每個 `$ref` 都能對回設定檔（舊規則「有附 decision 就算過」在還原模式下會一律通過） | `qt_report --config-spec <restore config-spec>` |
| ark-html-report 1.2 | `html_images.py`：縮圖 → 轉 WebP → 去重 → 內嵌，產出不需外部請求的單檔，可加圖庫和點圖放大 | `html_images.py embed report.html --layout --lightbox` |

**還原遊戲的完整流程**：
`gs_run --stage restore` → `ps_run --dest output/games/<slug>/prob`（會一起跑 ps_diff）→ `qt_report --version-id <各版> --config-spec <spec>/config-spec.yaml`

## 6. 消費端同步步驟

```bash
# 1) 同步（方式依各環境：align_sync／git pull／rsync）
python .kiro/skills/ark-skills-align/scripts/align_sync.py plan   # 確認後 apply；或用你的環境既有方式（git pull／rsync）
# 2) 刪掉第 3 節的舊 skill 目錄，並清掉引用
grep -rn "ark-video-understanding\|ark-game-analysis\|ark-game-gdd\|ark-game-atlas\|ark-game-domains\|ark-game-design-doc" .kiro/ CLAUDE.md AGENTS.md
# 3) 依賴
pip install pyyaml jinja2 openpyxl Pillow formulas   # Pillow：html_images；formulas：prob Excel 真值驗證（選配）
# 4) 驗收
python .kiro/skills/ark-game-spec/scripts/gs_run.py --stage pack --all
python -m pytest -q .kiro/skills/ark-game-spec/scripts/tests .kiro/skills/ark-game-prob/scripts/tests \
                    .kiro/skills/ark-game-quicktest/scripts/tests .kiro/skills/ark-html-report/scripts/tests
# 5) 重產 skills.lock（如果你的環境有）
```

**上游驗收基準**：spec 48 passed（缺 ffmpeg / openpyxl 的會自動跳過），quicktest 21 passed，html-report + bundle 全過；全庫 audit 沒有 P0/P1。

## 7. 待消費端回報

- **aidev**：用真的 `a-standard.json` 驗收 `--stage restore` 加上 `qt_report --config-spec`：55 個參數鍵全列、`$ref` 全部能解析、三個版本的判定都對。結果請回報上游。
- 用舊中文圖夾的 gdd-pack 會一直出現 `GDD-ASSET-LEGACY` 警告，建議趁這次改成英文夾名。
