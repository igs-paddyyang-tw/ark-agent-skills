# ark-agent-skills Changelog

> 各專案同步 skills 時參考此檔案。格式：日期 + 動作 + 影響範圍。

---

## 2026-10-29 (列車 r15：盤點第三批 M-5 —— 三個品質類食譜合併成可執行的 ark-quality-gates)

> 規格：kiro-cli `docs/specs/ark-quality-gates-spec.md`（Paddy 選方案②）。active 50 → 48。

- **新增 `ark-quality-gates` 1.0.0（form: executor）**：`scripts/quality_gates.py` 一支指令跑三道關，輸出 JSON＋Markdown，失敗 exit 1
  - tests：`<python> -m pytest`（有 pytest-cov 加覆蓋率、`--fail-under`）；0 個測試 → skip 並明說
  - lint：語法編譯檢查（標準庫，一定跑）＋ ruff（有裝才跑）
  - security：內建規則用 AST 判函式呼叫（`model.eval()`、`ast.literal_eval` 不誤報）＋密鑰／SQL 拼接 regex；有裝加跑 bandit、pip-audit；`# nosec` 可標記刻意用法（略過數會顯示）
  - 🔴 缺工具一律 skip＋安裝指令，`--strict` 時 skip 算失敗；11 項測試（反證：判定永遠 pass → 2 紅、shell 規則停用 → 1 紅）
  - 實跑本庫：env-doctor、agent-cli 各 2 處 `shell=True`（執行使用者設定的指令，屬刻意用法，未改動，消費端可加 `# nosec`）
- **ark-code-review、ark-security-audit、ark-test-runner → deprecated stub 2.0.0**；原產碼食譜逐位元組搬 `ark-quality-gates/references/recipes/`
- **獨占觸發詞**「覆蓋率」「line coverage」「pytest --cov」owner 改 ark-quality-gates（audit_skills、prompt_lint）
- 改引用（patch／minor）：ark-agent-init 2.6.4、ark-agent-role-profile 1.3.7（7 個角色）、ark-agent-team-builder 3.1.7、ark-browser-tool 3.0.2、ark-code-spec-validator 1.0.2、ark-mobile-adb 2.5.1、ark-web-scraper 1.0.2、ark-wiki-engine 3.0.5、ark-prompt-spec-validator 1.3.0、ark-skills-align 2.9.0

---

## 2026-10-29 (列車 r14：盤點第二批 —— 三個規劃類 skill 併入 superpowers 的工作模式)

> 計畫：kiro-cli `docs/plans/skills-batch2-m4-plan.md`（盤點 M-4）。active 53 → 50。

- **ark-superpowers 1.3.0**：新增「工作模式」路由 —— **plan**（原 ark-project-planning 6 步流程：釐清→規格→拆解→派工→追蹤→驗收）、
  **coauthor**（原 ark-doc-coauthoring 互動共筆＋讀者測試）、**files**（原 ark-planning-with-files 3-File Pattern）；
  原文逐位元組搬到 `references/modes/{plan-workflow,coauthor,files}.md`，description 598 字（含三模式觸發詞），`replaces` 宣告 4 個舊名
- **ark-project-planning 3.0.0、ark-doc-coauthoring 2.0.0、ark-planning-with-files 2.0.0 → deprecated stub**（保留 SKILL.md 與觸發詞）
- **獨占觸發詞**「派工」「共筆」owner 改 ark-superpowers（audit_skills、prompt_lint 兩處）
- **ark-prompt-spec-validator 1.2.0**：PL-017 豁免自己 `metadata.replaces` 列的舊名（與 audit AL-016／AL-032 同判準；superpowers 誤報 8→0）＋測試（反證：拿掉豁免 → 紅）
- 改引用（patch）：ark-agent-init 2.6.3（role-skills-map、AIBI／gamedev 角色、SOUL-leader 範本）、ark-agent-role-profile 1.3.6、ark-agent-team-builder 3.1.6、ark-release-notes 1.0.2；ark-skills-align 2.8.0（觸發詞 owner）

---

## 2026-10-29 (列車 r13：盤點第一批收尾 —— dashboard-health→env-doctor、uml→superpowers；check_consumers 認得 stub 型合併)

> 計畫：kiro-cli `docs/plans/skills-batch1-m2-m3-plan.md`（盤點 M-2、M-3）。active 55 → 53。

- **ark-env-doctor 1.1.0**：新增端點模式 `--endpoints`／`--sse`／`--endpoints-file`（`scripts/endpoints.py`，只用標準庫；任一失敗 exit 1 可接排程）＋ 8 項測試（本機 http.server：2xx／5xx／SSE／連不上；反證：狀態碼判斷改永遠通過 → 3 紅）。
  原 ark-dashboard-health 正文原樣搬 `references/dashboard-health.md`
- **ark-superpowers 1.2.0**：設計階段加「設計圖（Mermaid）」，原 ark-uml-generator 正文原樣搬 `references/uml-diagrams.md`；description 加 UML／序列圖／ERD／Mermaid 觸發詞
- **ark-dashboard-health、ark-uml-generator → deprecated stub 2.0.0**（保留 SKILL.md 與觸發詞）；接手者以 `replaces` 宣告
- **check_consumers（repo 根 scripts/）**：
  - 認得「已併入、stub 仍在」的名字：矩陣／SOUL／蒸餾設定寫舊名、或複本旁沒有接手者 → 回 1，訊息給「改成 X」；複本旁已有接手者 → 提示舊 stub 可刪。
    舊判準只看「上游已不存在」，r12 的 8 個 stub 全部漏網（實測：97 份複本缺接手者、30 處 sync 矩陣、28 份 SOUL.md 仍寫舊名）
  - 實作 v2 設計就規劃、從未落地的 `--impact --json`：與上一班列車（manifest 歷史）比 major 升版 → notice_build.py 的輸入
  - pre-push 原本建議了不存在的 `--impact`；改正並加測試「hook 建議的旗標必須存在」（反證：寫錯旗標 → 紅）
- 改引用（patch）：ark-agent-init 2.6.2、ark-agent-role-profile 1.3.5、ark-agent-team-builder 3.1.5、ark-skills-align 2.7.1（check_consumers／gen_manifest `--out` 用法）

---

## 2026-10-29 (列車 r12：8 個產碼食譜合併成 ark-pipeline-recipes；新守門 AL-032)

> 計畫：kiro-cli `docs/plans/ark-pipeline-recipes-merge-plan.md`（盤點 M-1）。active 62 → 55。

- **新增 `ark-pipeline-recipes` 1.0.0**：SKILL.md 只做「情境 → 食譜」路由，8 份食譜原樣搬到 `references/<名稱>.md`（腳本逐位元組比對 8/8 一致）
- **舊 8 個改 deprecated stub（2.0.0，Breaking）**：ark-anomaly-detector、ark-chart-generator、ark-cost-tracker、ark-etl-pipeline、ark-kpi-calculator、ark-llm-tools、ark-translator、ark-data-contract。
  🔴 stub **保留 SKILL.md**（mirror_sync 會跳過沒有 SKILL.md 的上游目錄），description 保留原觸發詞並轉址
- **新守門 AL-032 `ref-to-deprecated`（P1，ark-skills-align 2.7.0）**：active skill 的 depends_on／description／skill 內 `*.yaml` 指向 deprecated stub 即擋，訊息給出取代者。
  stub 存在時 AL-015／016 都會放行，舊引用會讓新裝的 agent 只拿到空殼。反證：放回一處舊引用 → 轉紅；停用規則 → 3 項轉紅
- **改引用**（patch）：ark-agent-init 2.6.1（role-skills-map、AIBI／gamedev 角色、skill-selection-map）、ark-agent-role-profile 1.3.4（9 個角色檔）、ark-agent-team-builder 3.1.4、ark-html-dashboard 1.0.3、ark-agent-cli 2.2.2、ark-retention-analysis 1.0.2；
  ark-game-spec 2.9.0（depends_on llm-tools → pipeline-recipes；`llm_adapter.py` 註解屬契約檔 → minor）
- 🟡 **消費端**：`mirror_sync` 會把已裝的舊目錄對齊成 stub，但**不會自動裝 `ark-pipeline-recipes`** —— 各專案同步後自行 `cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/`

---

## 2026-10-29 (列車 r11：補版號債＋修兩個守門的根因)

- **補版號債**（r10 之後未升版）：ark-weknora-cli 1.1.0（kb_registry 三層查找）、ark-agent-team-builder 3.1.3（去 BOM）、ark-agent-cli 2.2.1（補連 `references/v2-design.md`，原為孤兒檔）
- 🔴 **「fingerprints.json 永遠別碰」的根因**：`ark-superpowers/scripts/build_fingerprints.py` 不解析參數，**連 `--help` 都重寫**這個被追蹤的檔（只差 generated 日期）
  → 每跑一次 CLI 契約測試就弄髒工作樹，manifest 也記到被改過的 tree_hash（r10 的 superpowers 即是）。
  修：superpowers 1.1.0 —— argparse、`--check`、內容沒變不寫檔；`test_cli_contract.py` 加「`--help` 不得改動 skill 目錄既有檔」（反證：換回舊版即紅）
- **AL-103 誤報修正**（ark-skills-align 2.6.1）：Breaking 說明寫在新主版號的 `X.0.0` 那一行即可（agent-cli「2.0.0 — Breaking」原被 2.2.0 誤判）
- audit P0／P1＝0、P2＝1（weknora tested_against 刻意留空）；manifest `skills-2026.10-r11` 在乾淨工作樹最後產出

---

## 2026-10-29 (ark-agent-init 2.6.0：AGENTS.md 是 Ark Agent 架構單一來源，Claude／Codex 都讀得到)

- 查證（官方文件）：**Codex** 原生讀 AGENTS.md（專案根往下每層一份、**無匯入語法**、合計上限 32 KiB；同層有 AGENTS.md 時 fallback 檔名讀不到 → **CODEX.md 無效**）；
  **Claude Code** 只讀 CLAUDE.md，但支援 `@AGENTS.md` 匯入（官方建議做法，比 symlink 好：Windows 免特權、Claude 專屬內容有地方放）
- 新增 `assets/AGENTS.md`：工具中立、自成一體 —— 這個 workspace 是什麼、**Ark Agent 五層架構**、開場與收尾、共用規範、**各工具入口**（Kiro 的 fs_write／`/context add` 只放這節）
- 新增 `assets/CLAUDE.md`：`@AGENTS.md`＋BRAIN／MEMORY 匯入的薄殼，下方只放 Claude 專屬
- `build_kiro.py`：專案根 AGENTS.md／CLAUDE.md 不存在才產（once）；子 agent 複本改為專案根那份的逐字複本；不產 CODEX.md
- SKILL.md：「多 AI CLI 入口」改寫（匯入取代 symlink、Codex 規則）；「### 2. AGENTS.md」內嵌範例改指向範本（prompt_lint P1 22 → 0、SKILL.md 908 → 831 行）
- 測試新增 6 項（自成一體＋< 32 KiB、共用段工具中立、CLAUDE.md 第一個匯入是 @AGENTS.md、不產 CODEX.md、子 agent 逐字複本、不覆寫）；反證 5 項轉紅
- 實例：kiro-cli（nana-bot）同日改成同一結構（kiro-cli `65e282a`）

> ⚠️ 本次**未重產 manifest**：audit 抓到 r10 之後他人 commit 的版號債（weknora-cli 契約變未升版 P1、team-builder／superpowers 內容變未升版、agent-cli major 無 Breaking 說明）。
> 先重產會把未升版的 hash 記成新基準、把問題洗掉 —— 交主責 nana-bot 補版號後再發列車。

---

## 2026-10-27 (ark-skills-align 2.6.0：mirror_sync 修 Windows 編碼、換行誤判、gitignore 比對)

> nana 回報（Windows 消費端對齊 aibi／aikb／aimkt／aiqa／aidev 時發現）。

- **編碼**：`export_upstream`／`check-ignore` 的 git 輸出改以 UTF-8 解碼。原本 Windows 預設 cp950，遇中文路徑 → `stdout` 為 None → `AttributeError`，plan／apply 皆中止
- **換行**：文字檔比對前 CRLF→LF；歷史比對加算 LF／CRLF 兩種版本。實測 aidev：舊版 8 個 LOCAL 全為誤報 → 新版 0
- **gitignore**：`check-ignore` 改 `-z` 位元組收送（Windows 文字模式把 `
` 轉 `
`，原本上游 `.gitignore` 判定在 Windows 從未生效）；新增消費端 `.gitignore` 判定 —— 命中者不列本地資料、**apply 時保留**
- 測試：`test_mirror_sync.py` 10 → 15（CRLF same／CRLF stale／二進位不正規化／消費端 gitignored 保留／中文路徑），Windows 不設 `PYTHONUTF8` 全過
- 說明：`references/mirror-sync.md` 判定表與 Windows 注意事項

## 2026-10-27 (遊戲製程：素材版控分層 L1～L4（佈局契約 v3.8）＋網頁遊戲上線前資安；ark-web-game 0.11.1、game-proto 1.8.0、game-prob 1.7.0、game-spec 2.8.0)

> aidev 回貢（豬來蓋福、神燈寶藏兩款實作與驗收）。

### 素材版控分層：讓 ⑦ 試玩版與 ⑧ 正式 Client 能從 git 一次重產
- **ark-game-spec 2.8.0**：佈局契約 v3.8——§1a L1 原始碼／L2 可出貨素材（定版家 `art/`，另計 < 5 MB、單檔 < 1 MB）／L3 內部參考（只登錄 `analysis/source/manifest.json` 逐檔 sha256）／L4 重產物；`game-layout.yaml` 加 `asset_layers`、`art` 額度
- **ark-game-prob 1.7.0**：ps_layout 新增 **L-ART**（art/ 只收 webp／png／ogg／m4a＋README、單檔 > 1 MB、合計 > 5 MB → error；不計入定版家 1 MB）
- **ark-game-proto 1.8.0**：`stage_build --slug` 找不到內部參考素材 → 佔位模式照常建置（`stage.yaml` 有 `bundles:` 時不產分包 release，否則必要 bundle 為空會擋下整個建置）；清冊加 `assets_mode`、不再寫各機器絕對路徑；`--require-assets`
- **ark-web-game 0.10.0**：`wg_pack_assets` 來源順序 override → --set → dir → env → generator；成品 WebP 與同名音效**直通**（出貨位元組＝git 裡的檔，兩款重打包 releaseId 不變）；`--regen`／`--export` 凍結美術成品；Docker 建置內打包、不依賴 output
- 驗收（`git archive` 乾淨目錄、沒有 output 與外部資料夾）：Client 測試 69／69、兩款打包／建置／⑦ stage_build 成功

### 網頁遊戲上線前資安（ark-web-game 0.11.0／0.11.1）
- 範本預設安全：`wg_server_init` 產的 Server 映像預設 CMD **不帶 `-dev`**（fail closed：缺 `-redis` 拒絕啟動）；client-template 正式 build **不產 source map**（`PGP_SOURCEMAP=1` 才產）
- references/delivery §6：dev（`compose.yaml`）與 release（`compose.release.yaml` 覆寫檔）分開；nginx 安全標頭 snippet＋`server_tokens off`，以及「location 有自己的 `add_header` 就不繼承 server 層標頭」的陷阱
- 決策樹加「資安」分支、守門表加資安兩列；client-template 附 `tools/sec_check.py`（唯讀稽核器：只讀設定與打包、唯讀 GET）
- 兩款實測：上線前判定由 4 FAIL、2 WARN → 0 FAIL、0 WARN

### 其他
- ark-web-game 合併上游 0.9.2（category → scaffolder）
- 測試：web-game 17、game-proto 37（12 skip）、game-prob 93、game-spec 78；audit P0／P1 = 0
- manifest `skills-2026.10-r11`

## 2026-10-27 (BRAIN.md 統一「判準＋角色」：ark-agent-init 2.5.0、bot-builder 3.2.0；docker-deploy 1.1.0 補 Node／Go)

### BRAIN.md 同名兩種內容 → 統一（Paddy 定：方案 1）
- 現況衝突：skill 範本＝**五層判準**（只能手抄）；ark_team_agent daemon 產的＝**角色知識**（無判準）；ark_bot_agent **注入卻不產** → nana-bot 手抄範本帶 leader 私有路徑上線
- **ark-agent-init 2.5.0**：`build_kiro.py` 產 BRAIN.md ＝ 判準段（`assets/steering/BRAIN.md`，移除原混入的 leader 專屬「附註」「品質護欄」）
  ＋ 角色段（新 `assets/steering/brain-roles/<role>.md`，源自 team 套件 10 個角色範本，leader 帶品質護欄；`_default.md` 待填骨架）；
  選法同 daemon（`template` → instance 名 → role 對應），私有櫃路徑依 instance 渲染，**已存在不覆寫**；`--validate` 要求 BRAIN.md
- **ark-agent-bot-builder 3.2.0**：依 agents.yaml 為根目錄與各 agent 委派 `_write_brain` 產 BRAIN.md（根目錄私有櫃以 bot 名命名）；
  移除根層 `knowledge/raw/memory-archive`（違反「根層不放 raw/」紅線，bot 套件程式早已不讀寫）→ 改建 `memory/archive/`
- 測試：init 新增 6 項（反證 10 項轉紅）、bot-builder 新增 3 項（反證 3 項轉紅）
- 🟡 套件側（協助範圍、另案）：team 角色範本補判準段，讓 daemon 直接產合併版；bot `paths.py` docstring 仍寫 `raw/memory-archive`

### ark-docker-deploy 1.1.0：補 Node／Go 範本並實機驗證
- description 宣稱支援 Python／Node／Go，實際只有 Python 範本 → 補 Node（node:22-slim multi-stage、健康檢查用內建 fetch）與 Go（golang:1.23 → alpine:3.20、靜態連結、uid 65534、busybox wget 健檢）
- 實測：Node 25 秒 healthy／227MB；Go 15 秒 healthy／13MB；`tested_against` 補三條路徑；description 補「不適用於」

### 守門
- ark-prompt-spec-validator 1.1.2：觸發詞擁有者表的複本指向已不存在的 `ark-agent-builder`／`ark-llm-cli`（bot-builder 被誤報 P1）→ 改正；
  `test_taxonomy_vocab.py` 加擁有者一致＋存在檢查（反證轉紅）
- manifest `skills-2026.10-r10`

---

## 2026-10-27 (ark-wiki-engine 3.0.4：跨平台支援 Windows)

`wiki_index.py` 原在模組頂層 `import fcntl`（POSIX-only），Windows 原生 Python 無此模組 →
載入即 `ModuleNotFoundError`，連帶 17 項測試失敗。fcntl 實際只用於 build index 的併發互斥鎖。

### 修正
- `wiki_index.py`：`import fcntl` 改為條件 import —— POSIX 用 `fcntl.flock`、Windows 用
  `msvcrt.locking`，封裝成 `_acquire_lock` / `_release_lock`，行為對等（非阻塞，取不到回 `BUILD_LOCKED`）。零第三方依賴
- `tests/test_wiki_v3.py`：鎖測試改用 `wiki_index._acquire_lock/_release_lock` 封裝，三平台皆可跑（不再直接 import fcntl）
- `SKILL.md`：新增「跨平台相容性」章節（四平台能力矩陣 + Windows 用法 + 網路磁碟限制）

### 更正認知
- **macOS 本就支援**（POSIX 有 fcntl）—— 先前「只能 Linux/WSL」的說法不精確；真正不支援的只有 Windows
- llm-wiki-agent 的 Windows runtime 走自己的 `src/skills/wiki_skills/`（無 fcntl），不受此 bug 影響；本修正針對「直接使用本 skill scripts」的情境

### 驗證
- Linux/WSL 全測試 112 passed；反證鎖有效：手動持鎖後第二個 build 回 rc=2 + BUILD_LOCKED
- 設計文件：`docs/designs/2026-10-27-wiki-engine-cross-platform.md`
- 版號 3.0.3 → 3.0.4（patch，無契約變更）

### 待辦（版本分岔）
- 🔴 上游（本次合併前）3.0.3 vs `.kiro/skills/` 複本 3.0.3（schema 1.1 vs 1.2）分岔中 —— 複本領先上游兩版，複本的 3.0.4/3.0.3 改動尚未回流上游。本次跨平台修正做在上游 3.0.1 基礎上，與複本合併時需處理版號與 schema 差異

## 2026-10-27 (ark-github-cli 1.0.0：正式定版)

- 0.x 卻 `status: active`、每次收尾都在用 → 定 **1.0.0**；CLI／stdout 契約與 0.2.3 相同，無破壞性變更（版本表註明，AL-103 通過）
- manifest `skills-2026.10-r9`

---

## 2026-10-27 (ark-skills-align 2.5.0：補實作 AL-102／103／106 ＋ tree_hash 不再吃 .pytest_cache)

- **AL-102**（P1）契約檔變了版號沒升、**AL-108**（P2，新）內容變了版號沒升、**AL-103**（P2）major 無 Breaking 說明、**AL-106**（P3）updated 早於契約 commit ——
  v2 規格（09-17）只登記代號，今天補實作；基準是 repo 內上一班 manifest，audit 要在 gen_manifest 前跑
- 🔴 修 **tree_hash 被執行期產物污染**：原本全目錄掃描，`.pytest_cache`（自帶 `.gitignore: *`）被算進去 → 先跑測試再產 manifest 就記下錯的 hash
  （r7 的 ark-agent-init 即是，乾淨 checkout 永遠對不上）。改為只算 `git ls-files -co --exclude-standard`；非 git 環境排除 `__pycache__`／`.pytest_cache`／`node_modules`，align_sync 同規則
- AL-106 降 P3 的理由：回貢流程「消費端先開發、數天後才推上游」，commit 日必晚於真正修改日（game-proto 1.7.0：10-23 開發、10-27 回貢）
- 新增 `scripts/tests/test_version_drift.py` 7 項（含污染回歸、未 commit 新檔要算進去）；反證：拿掉新邏輯 3 項轉紅
- manifest 重產 **`skills-2026.10-r8`**（乾淨 hash，取代 r7 被污染的 ark-agent-init 值）

---

## 2026-10-27 (ark-agent-init 2.4.0：AGENTS.md 落點單一權威)

來源：nana-team 標準化時 AGENTS.md 落點被人工校正兩次 → review `kiro-cli/docs/designs/ark-agent-init-agents-md-placement-improvement.md`（F-1~F-4）。
根因是套件內四處說法互相矛盾，且程式產出與人工定案相反、測試把錯誤落點鎖死。

- **A-1 單一權威**：SKILL.md 頂部一句定死「AGENTS.md 一律放 workspace 根：專案根＝SSOT、子 agent 工作目錄根＝複本、`.kiro/steering/` 永遠不放（指回根的 symlink 除外）」，
  SKILL.md 其餘 9 處、`references/defaults/README.md`、`five-layer-architecture.md` 改為引用；修正「AGENTS.md 會被 daemon 覆寫」（實為 policy `once`）
- **A-2 程式**：`build_kiro.py` 子 agent 複本改落工作目錄根（與 ark_team_agent 1.2.19 daemon `_write_root_agents_md` 落點一致），profile 片段併入同一落點；重跑不再長回 steering/
- **A-3 測試**：原斷言「子 agent steering/ 應有 AGENTS.md」是反的 → 改為斷言 steering 0 份、wd 根有複本、重跑不復發、validate 抓放錯的實體複本、接受指回根的 symlink；反證：改回舊落點 9 項轉紅
- **A-4 稽核**：新增 `scripts/audit_agents_layout.py`（只看 team.yaml 編制內 agent、訊息帶「應改放哪」、缺 team.yaml 明說跳過、認得 symlink）；`build_kiro.py --validate` 共用同一套規則（專案根缺 SSOT 不在 validate 擋：daemon 首次啟動才產）
- 順帶：`ark-web-game` 0.9.2 category `executor` → `scaffolder`（新 skill 沿用 1.1 混軸舊值，三軸測試與 audit `category-axis-mixed` 皆紅）；README 補重產

---

## 2026-10-27 (aidev 網頁遊戲與還原局優化回貢：5 個 skill 升版＋新增 ark-web-game)

來源：aidev-team-agent 2026-10-22～23 實戰（豬來蓋福、神燈寶藏網頁正式版；Go 世代 26 款還原局）。

- **ark-web-game 0.9.1（新增）**：網頁遊戲 ⑦⑧ 工程——單局結果契約、Go 網路層 wire 協定與 WsService、⑧ 抽離 SOP（game.js → Go prob.Game）、Go Server 範本（34 檔）、素材打包（WebP／ogg＋m4a／manifest）、正式 Client 範本、Docker 發佈
- **ark-game-proto 1.3.0 → 1.7.0**：引擎回放試玩（⑦-lite，`engine_trace`）、連線版 `service/wire.js`、神燈寶藏 adapter、還原局拍板包 `--no-play`、description 縮到 PL-020 限度內
- **ark-game-prob 1.4.8 → 1.6.0**：`ps_extract`／`ps_diff` 支援 hoyeah 機率表與裁決、匯入 qt-report
- **ark-game-quicktest 2.1.5 → 2.2.1**：路線 B（用 ⑧ Go Server 機率模組模擬）、路線 C（C++ 快測 → Go 移植、Go 世代線上重跑）、`references/cpp-port-sop.md`、`restore-stages-sop.md`；frontmatter 併入上游 schema 1.2 與依賴範圍
- **ark-game-spec 2.6.1 → 2.7.0**：佈局契約 v3.7
- **ark-wiki-engine 3.0.2 → 3.0.3**：`wiki_index` 舊索引目錄刪不掉（共用資料夾、同步碟）時改名，不中斷建置；新增 `test_index_no_delete.py`（無 fcntl 的平台自動跳過）

**測試**：spec 57、quicktest 31、prob 92、proto 31、web-game 14 全過；wiki-engine 在 Windows 有 17 項失敗，與上游 3.0.2 原版在同一台機器的失敗完全相同（`wiki_index.py` 用 fcntl，索引建置只能在 Linux／WSL 跑），非本次引入。audit P0／P1 = 0。

---

## 2026-10-21 (ark-docker-deploy 1.0.2：實機驗證)

- 照 SKILL.md 範本產 Python 專案（python:3.12-slim multi-stage）→ `docker compose build`／`up -d` → 35 秒內 healthy、`/api/status` 200，
  builder 階段裝的套件正確帶到 runtime → 補 `tested_against`（docker 28.3.3、docker-compose 2.39.1；**只驗 Python 路徑**）
- 實測抓到：compose 範本頂層 `version: "3.8"` 在 Compose v2 每個指令都印 obsolete 警告 → 移除，注意事項補說明
- ark-skills-align 2.4.2（metadata-schema.md 實測紀錄）；audit P2 2 → **1**（僅 weknora-cli 刻意留空）；manifest `skills-2026.10-r6`

---

## 2026-10-21 (P2 收尾：孤兒 asset、tested_against 實測紀錄)

- ark-game-quicktest 2.1.5：SKILL.md 補連 `references/quicktest-targets.template.yaml`（quicktest.yaml 範本，原本 agent 讀不到）
- ark-game-report 0.2.5：`gr_run.py --help` exit 0（CLI 契約全綠）
- ark-skills-align 2.4.1：metadata-schema.md 記 tested_against 實測證據 ——
  weknora-cli `kb-list` 對內網 WeKnora 唯讀成功，但伺服器版本查不到（system/info 403）→ **刻意留空**；
  docker-deploy 範本未獲授權實機 build → 留空。「憑空的版本比空白更糟」
- audit P2 3 → **2**（只剩上述兩個有意留空）；manifest `skills-2026.10-r5`

---

## 2026-10-21 (ark-game-report 0.2.7：結案報告照樣板版型)

- closeout HTML 改照樣板「樂奇 aidev 結案報告」（ark-html-report boardroom）：header、摘要、KPI 卡、00～10 節、階段卡、④ 觸發表（`rtp-report.gate.checks`）、⑥ 對帳表、⑦ 冒煙截圖內嵌；CSS `assets/closeout.css`（自足、不外連字型）
- 敘事走 12 個人工區 `<!-- human:<key> -->`，重產保留（舊 `human:notes` 仍讀）
- 🔴 修：⑨ 只看 review/index.html 就判完成 → 改為拍板欄全填才完成，否則「送審中」（與 ark-game-proto review_build 同規則）
- 🔴 修：⑥ 對帳把 `go-parity.json` 與分檔重複加總（HuffNPuff 56 萬 → 正確 16 萬）
- ⑩ 只放本款成效；未上線寫「上線後補」，不引用別款

---

## 2026-10-21 (ark-game-report 0.2.6：並行測試改量重疊)

- `test_query_parallel_export` 不再比總耗時（Windows 起 Python 慢時 28 秒 > 門檻 23.4 秒，但並行其實有效）；改由假 bq_export 每支寫一個起訖時間檔，驗 workers 4 時同時在跑 ≥ 3 支
- 多程序同寫一個 log 檔在 Windows 會併行掉行 → 每支一檔

---

## 2026-10-21 (佈局契約 v3.5 補充：1 MB 額度不計 html)

- ark-game-spec 2.6.1：`data_total_kb` 1 MB 額度不含 `game/`、`review/` 與 `*.html` View 軌（使用者決議，比照 `single_file_kb` 排除 html）
- ark-game-prob 1.4.8：`ps_layout` L-SIZE 新增定版家總量檢查（依上述口徑，超過 → warning），`facts.size` 多 `data_kb`／`data_limit_kb`；測試 `test_layout_data_budget_excludes_html`
- 實測 HuffNPuff：含 html 1,242 KB → 依新口徑 633 KB

---

## 2026-10-20 (佈局契約 v3.5：拍板包不與各階段產出重疊)

規格：aidev `docs/specs/2026-10-20-review-pack-dedup-spec.md`；分析：`docs/reports/review/2026-10-20-huffnpuff-review-overlap-analysis.md`。

### ark-game-proto 1.3.0（review_build）
- `publish_docs`：定版家 md 旁產同名 html（`content-src` 戳記、冪等、不覆寫他工具的成對 html）
- `clean_review`：白名單外舊檔清掉（1.2.4 起複製進來的 docs/、prob-spec.html、proto.html 與孤兒檔）
- 成品改 `../<stage>/…` 相對連結，不複製；清冊多 `links`、來源改相對 repo 路徑；結案報告不進送審包
- `--export <資料夾>` 產可帶走的完整包（拒寫 data/）；輸出 `broken_links` 檢查人工章節寫死的舊路徑

### ark-game-prob 1.4.7（ps_layout）
- L-STAMP 掃描擴到 analysis/report、spec、quicktest/qt-report、game；L-REVIEW 同時驗清冊 `links`

### ark-game-spec 2.6.0（佈局契約 v3.5）
- review/ 只放拍板書、checks/、定版家放不下的自足單檔；spec／game 允許 md 旁的 html

### ark-superpowers 1.0.3（doc_lint）
- 🔴 修：SP-001 把 frontmatter（`type: spec`、`language: zh-TW`）、章節標題、表格標題列／分隔列、粗體標籤行當成模板殘留 → **每份文件都 P0**。結構行改為豁免
- SP-002：行內 code 裡的 `{slug}` 等字面路徑不算 placeholder；測試子程序加 `-X utf8`（Windows cp950）

### 結果
HuffNPuff 拍板包 5,004 KB → 4,433 KB、與定版家重複 0、斷連結 0；ps_layout L-STAMP／L-REVIEW 0 error

## 2026-10-20 (depends_on 帶版本範圍 + AL-105／依賴環守門)

### 資料（20 個 skill、38 條依賴）
- `depends_on` 全部由字串改為 `{ name, version }`：範圍預設 `^<上游主版號>.0.0`；文件寫明最低版本的兩條用該版本
  （game-proto → game-prob `^1.4.0`、game-spec → html-report `^1.2.0`）
- **拆 ark-game-prob ⇄ ark-game-quicktest 依賴環**：game-prob 只讀 quicktest 的產出檔（qt 模式的 rtp-report），
  不呼叫其程式 → 移除 prob → quicktest；quicktest → prob（`--probspec` 呼叫 `ps_run.py`）保留
- 版號：上述 20 個升 patch；ark-skills-align 2.4.0（守門規則）

### 守門（audit_skills.py）
- 🔴 修：斷鏈檢查與反向依賴原本用 `str(ref)` 取名稱 —— 物件格式會變成 `"{'name': ...}"` 而**靜默跳過**。改用 `dep_name()`
- 補實作 **AL-105**（P0，v2 規格 AC-07 只登記代號）：上游現行版本不滿足範圍
- 新增 AL-030 依賴環（P1）、AL-031 範圍無法解析（P1）—— `semver.satisfies()` 對亂寫的範圍只回 False，不先驗語法會誤報成 P0
- 新增 `scripts/tests/test_depends_on.py`（8 項：含物件格式斷鏈回歸、P0／P1 分流、環偵測、全庫可滿足且無環）

### 結果
audit P2 41 → **3**（剩 tested_against 2、孤兒 asset 1）；manifest `skills-2026.10-r4`

---

## 2026-10-20 (分類三軸化：category × form × domain，schema 1.2)

規格：`docs/specs/2026-10-20-skill-taxonomy-three-axis-spec.md`。
1.1 把「形態」（`executor`）與「領域」（`domain`）塞進 `category`，違反 taxonomy.md 自己的
「判準是產出物而非手段」；受控詞彙 4 份複本、規格文件 3 份互相矛盾。

### 欄位（全庫 61 個 SKILL.md）
- 新增 `form`（executor 17／instruction 44）、`domain`（game 9／general 52）；`schema_version` 全部升 `"1.2"`
- `category` 移除 `executor`、`domain`，12 個依產出物重歸類：db-query／wiki-engine → pipeline；
  grafana-query／github-cli／mobile-adb → ops；game-spec／game-prob／game-report／marketing／retention-analysis → document；
  game-proto → view；game-quicktest → process
- 版號：metadata 變動 → 全部升 patch；ark-skills-align 2.3.0、ark-prompt-spec-validator 1.1.0（守門規則變更）

### 守門
- `audit_skills.py`：`FORM_CODES`／`DOMAIN_CODES`；1.2 缺 form／domain → P1，舊 schema → P3；
  category 為 executor／domain → P2 `category-axis-mixed`（AL-025~029）；舊別名 `sop` 改指 `document`（原指向已移除的 domain）
- `prompt_lint.py` PL-010、`quick_validate.py`、`backfill_metadata.py` 同步新詞彙
- 新增 `scripts/tests/test_taxonomy_vocab.py`：四份詞彙複本一致、全庫三軸齊全、舊別名不懸空

### 文件
- `references/metadata-schema.md` 為欄位唯一權威（補 schema_version 表、版號規則、status: experimental、upstream 等實際在用的欄位）
- `references/taxonomy.md` 補 form／domain 判準；`docs/skill-metadata-schema.md` 改指路頁
- README 每列顯示形態／領域；manifest 重產 `skills-2026.10-r3`

---

## 2026-10-20 (版號治理：manifest 自我參照、漏升版、列車 r2)

起點是全庫盤點：manifest 落後 SKILL.md 4 個 skill、9 個 skill 升版後仍有修改未升版、
本檔停在 09-04（一個半月未登錄）。

### 守門
- `gen_manifest.py`／`align_sync.py`：tree_hash **排除頂層 `release/`**（`HASH_EXCLUDE_DIRS`）——
  manifest 放在 `ark-skills-align/release/`，原本每次重產都讓 ark-skills-align 自己的 tree_hash 變動卻沒升版（自我參照）。兩支腳本同規則，已驗證 hash 一致、改 release/ 不影響 hash

### 補升版（升版後仍有修改的 9 個）
| skill | 版本 | 原因 |
|---|---|---|
| ark-agent-team-builder | 3.0.0 → **3.1.0** | validate_team 新檢查（a99036e）+ tested_against |
| ark-agent-team-design | 1.1.0 → **1.2.0** | gen_team 新功能（a99036e）+ r2 對齊 |
| ark-agent-role-profile | 1.3.0 → 1.3.1 | 改引用的 skill 舊名 |
| ark-superpowers | 1.0.0 → 1.0.1 | 改引用的 skill 舊名 |
| ark-prompt-spec-validator | 1.0.0 → 1.0.1 | ignore 指令被 HTML 註解尾吃掉（7e0c72c） |
| ark-agent-bot-builder | 3.1.0 → 3.1.1 | tested_against |
| ark-db-query | 3.0.0 → 3.0.1 | tested_against；category 行內註解移到獨立行（逐行解析的工具會誤讀） |
| ark-github-cli | 0.2.0 → 0.2.1 | 測試檔改唯一檔名 |
| ark-skills-align | 2.2.0 → 2.2.1 | 本次 tree_hash 修正 |

### 資料
- manifest 重產為 **`skills-2026.10-r2`**（60 個 active；experimental 的 ark-game-report 依規則不收），SKILL.md ↔ manifest 版本 0 不一致
- README 重產（`gen_readme --check` 原為紅）

### 已知未修
- `scripts/tests/test_cli_contract.py`：`ark-game-report/gr_run.py --help` 回 2（origin 既有，非本次引入）
- audit P2=41（38 個 depends_on 無版本範圍、2 個缺 tested_against、1 個孤兒 asset）
- category 混用三軸（形態／產出／領域）—— 另案出規格

### 09-05 ~ 10-20 未登錄期間的版本快照
> 本檔 09-04 後未更新；以下為各 skill 現行版本與最後一次修改，作為補登基準（逐筆沿革見 git log）。

| skill | 現行版本 | status | 09-05 後 commit 數 | 最後一次 |
|---|---|---|---:|---|
| `ark-agent-bot-builder` | 3.1.1 | active | 8 | 2026-09-18 `652f21a` feat(metadata): 補 3 個消費端型 skill 的 tested_against + 定義該欄位形狀 |
| `ark-agent-cli` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-agent-init` | 2.3.1 | active | 41 | 2026-10-19 `468b6d2` fix(ark-agent-init): 2.3.1 bot 根 skills/ 是 BaseSkill 插件包慣例，分 |
| `ark-agent-role-profile` | 1.3.1 | active | 10 | 2026-10-07 `2a5de92` feat(ark-game-spec): v2.0.0 五合一整併（遊戲製程 skill 7→3 Phase B） |
| `ark-agent-team-builder` | 3.1.0 | active | 24 | 2026-09-18 `652f21a` feat(metadata): 補 3 個消費端型 skill 的 tested_against + 定義該欄位形狀 |
| `ark-agent-team-design` | 1.2.0 | active | 6 | 2026-09-30 `23fd7ca` chore(ark-skills-align): 全庫版號對齊 release train r2 + 修 gen_man |
| `ark-anomaly-detector` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-book` | 1.1.0 | active | 2 | 2026-10-19 `6d4bcc5` feat(review): 拍板包導覽修正＋三隻小豬繪本風格（ark-game-proto 1.2.4、ark-book |
| `ark-browser-tool` | 3.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-chart-generator` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-code-review` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-code-spec-validator` | 1.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-community-cli` | 1.1.2 | active | 5 | 2026-09-29 `0abf4ee` fix(ark-community-cli): digest 跨窗 cluster_rep 加 default 回退，修 |
| `ark-cost-tracker` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-daily-news` | 2.1.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-dashboard-health` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-data-contract` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-db-query` | 3.0.1 | active | 10 | 2026-09-18 `652f21a` feat(metadata): 補 3 個消費端型 skill 的 tested_against + 定義該欄位形狀 |
| `ark-doc-coauthoring` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-docker-deploy` | 1.0.0 | active | 1 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-docx-tool` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-env-doctor` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-etl-pipeline` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-frontend-design` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-game-prob` | 1.4.4 | active | 18 | 2026-10-19 `5c6c3e6` feat(game-pipeline): 拍板書——review/ 導覽頁改用 ark-book 架構 |
| `ark-game-proto` | 1.2.5 | active | 10 | 2026-10-20 `a990c3e` feat(game-pipeline): 佈局契約 v3.4 十階段（ark-game-spec 2.5.5、ark-g |
| `ark-game-quicktest` | 2.1.2 | active | 8 | 2026-10-13 `be318fe` feat(ark-game-*): G-1 gs_run --stage publish + G-2 ARK_GAME_ |
| `ark-game-report` | 0.2.2 | experimental | 3 | 2026-10-20 `4bdd2b6` feat(ark-game-report): 0.2.2——預設快速版（只撈本機，D+7 初判）＋同期分析快取 |
| `ark-game-spec` | 2.5.5 | active | 15 | 2026-10-20 `a990c3e` feat(game-pipeline): 佈局契約 v3.4 十階段（ark-game-spec 2.5.5、ark-g |
| `ark-github-cli` | 0.2.1 | active | 2 | 2026-10-08 `81f4e5d` fix: gdd_export 擋路徑越界檔名 + 測試檔重名改唯一檔名 |
| `ark-grafana-query` | 1.0.0 | active | 1 | 2026-09-17 `7d2ff1b` feat: add ark-grafana-query skill (executor 型 Grafana 監控查詢) |
| `ark-grill-me` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-html-dashboard` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-html-report` | 1.3.0 | active | 6 | 2026-10-15 `0067f75` feat: 消費端本地修改回貢 + mirror_sync --accept-upstream |
| `ark-kpi-calculator` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-llm-tools` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-marketing` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-mcp-builder` | 1.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-md-report` | 1.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-mobile-adb` | 2.4.0 | active | 11 | 2026-10-15 `dba7acb` feat(ark-mobile-adb): 2.3.0 → 2.4.0 gamepack 校準資料解耦（--pack-d |
| `ark-pdf-tool` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-planning-with-files` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-pptx-tool` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-project-planning` | 2.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-prompt-spec-validator` | 1.0.1 | active | 9 | 2026-10-12 `7e0c72c` fix(prompt-spec-validator): ignore 指令被 HTML 註解尾 -- 吃掉導致失效 |
| `ark-release-notes` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-retention-analysis` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-security-audit` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-skill-creator` | 2.0.0 | active | 7 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-skills-align` | 2.2.1 | active | 53 | 2026-10-19 `468b6d2` fix(ark-agent-init): 2.3.1 bot 根 skills/ 是 BaseSkill 插件包慣例，分 |
| `ark-spec-executor` | 2.0.1 | active | 6 | 2026-10-16 `ae62318` feat(ark-game-spec): 2.4.0 to 2.5.0 slot-game pack 1.1 + 遊戲產 |
| `ark-superpowers` | 1.0.1 | active | 12 | 2026-10-07 `2a5de92` feat(ark-game-spec): v2.0.0 五合一整併（遊戲製程 skill 7→3 Phase B） |
| `ark-telegram-sender` | 2.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-test-runner` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-translator` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-uml-generator` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-web-scraper` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-webapp-generator` | 2.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-weknora-cli` | 1.0.1 | active | 8 | 2026-10-15 `0067f75` feat: 消費端本地修改回貢 + mirror_sync --accept-upstream |
| `ark-wiki-engine` | 3.0.1 | active | 22 | 2026-10-15 `4c4eb72` fix(ark-wiki-engine): ingest 沿用 raw frontmatter 的 title / re |
| `ark-xlsx-tool` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
---

## 2026-09-04 (executor 分類補登記 + 兩道守門對齊)

起點是一次全庫盤點：`audit_skills.py --repo .` 回 **P1=1 / P2=3，四條全在
`ark-db-query`** —— 08-19 的 v2 executor 化改造引入了新 category 與
`schema_version: "1.1"`，但守門與規格文件都沒跟著改。

### 守門
- `audit_skills.py`：`CATEGORY_CODES` 加 `executor`；`schema_version` 檢查抽成
  `SCHEMA_VERSIONS = {"1", "1.1"}` 並改**字串比對** ——
  原本 `!= 1` 對 YAML 讀成 str 的 `"1.1"` 恆為真
- `gen_readme.py`：`SECTIONS` 登記 `executor`（不登記 db-query 會落到「⚠️ 未分類」）；
  **移除 ⑤ `presentation-content` 並重編號** —— 該值在 `audit_skills.py` 已是
  legacy 別名（P3 → `document`），這裡卻當現行分類展示且恆印「（目前無）」

### 資料
- `ark-db-query`：`outputs` 的 `json` / `jsonl/csv` → 單一 `{format: data, audience: ai}`
  （沿用既有詞彙，不放寬守門。全庫實際只用 md 44 / code 9 / html 8 / data 3）

### 文件（三處分岔，不修就會留下新的）
- `docs/skill-metadata-schema.md`：`outputs.format` 原列 `xlsx|pptx|docx` 且**缺 `data`**，
  與守門的 `OUTPUT_FORMATS` 不同 —— 照文件設會被 P2 擋下
- `README.md` 分類規格表：`processess`、`viewation-content` 兩處全域替換誤傷
- `README.md` 統計行：手寫的「60 active + 3 stubs = 63」已過期（實際 stubs=0）

### 驗收
`gen_readme.py --check` ✅（原本是紅的，stale 到 08-19 之前，db-query 定位還是 v1 描述）·
`audit_skills.py` **P0/P1/P2/P3 全 0**（rc=0）·
反證：把 `executor` 移出詞彙、`SCHEMA_VERSIONS` 縮回 `{"1"}` → 立刻回 P1×1 + P2×1

---

## 2026-08-12 (ark-skills-align W2~W5)

### 治理（W2 — schema 回填 + 觸發詞）
- 全庫 60 個 active SKILL.md 回填 `schema_version: 1` + `status: active`
- 4 個 deprecated stubs 正確跳過
- `ark-news-daily` 加 negative trigger（不適用於網頁抓取）
- `ark-grill-me` 加 negative trigger（不適用於產 spec/design/plan）
- `ark-llm-cli` / `ark-llm-tools` 加互斥邊界聲明

### 治理（W3 — 呈現引擎收編 + README 重建）
- `ark-html-report` 確認 schema_version: 1 + status: active ✅
- `ark-md-report` 確認 schema_version: 1 + status: active ✅
- `ark-news-daily` 加 `depends_on: [ark-html-report]` ✅
- `ark-html-dashboard` 對齊共享 token 系統 ✅
- `docs/report-frontmatter-standard.md` 已建立 ✅
- README.md 完整重建（60 active + 7 deprecated 分類表）

### 治理（W4 — 條件執行 D-6~D-8）
- D-6: `ark-report-template` 確認為 deprecated stub ✅
- D-7: `ark-file-export` **保留**（有獨立價值：pipeline 最後一哩寫入）+ 加邊界聲明
- D-8: `ark-cost-tracker` **保留**（有獨立資料管線：data/costs/{date}.json）

### 統計（W5）
- Active：**60**（process 9 / scaffolder 9 / pipeline 20 / view 6 / content 1 / document 8 / domain 4 / ops 3）
- Deprecated：**7**（4 有 SKILL.md + 3 stub）
- 目錄總數：**67**（+ scripts/ = 68 個子目錄）

---

## 2026-08-12 (原始變更)

### 新增
- `ark-md-report` — Content 軌報告引擎（5 類型 × frontmatter 契約 × AI 寫作規則）
  - `scripts/report_lint.py` — 契約守門驗證（275 行）
  - `scripts/report_pair.py` — MD↔HTML 漂移檢查（119 行）
  - `scripts/report_register.py` — 索引 + 日報 log（112 行）
  - `references/agent-operating-guide.md` — 三件套運作契約
- `ark-html-report` — View 軌呈現引擎（5 風格 token × 17 元件 × Chart.js）
- `ark-api-doc-sync` — FastAPI route → docs API 表格自動同步
- `ark-eval-runner` — LLM 輸出回歸評測
- `ark-ingest-guard` — 知識入庫 prompt injection 消毒
- `ark-data-contract` — 管線元件間 schema 契約驗證
- `ark-release-notes` — git log → 結構化 changelog

### 移除（deprecated stub 保留 6 個月）
- `ark-report-template` → 被 `ark-md-report` + `ark-html-report` 取代
- `ark-postmortem` → 併入 `ark-md-report` type: incident
- `ark-ai-bot-builder` → 與 `ark-agent-builder` 完全重複
- `ark-daily-decision-digest` → 廢棄
- `ark-policy-translate` → 廢棄

### 修正
- `ark-wiki-engine` — 全面優化（受控詞彙表 + ingest guard + trust 欄位 + 雙模式路由 + 三件套銜接）
- `ark-code-spec-validator` — 四段工作流鏈優化（17 任務）
  - 評分公式定義 + 比例制 + drift 加權
  - AC-ID 約定 + loop-rules.md + 方向分流
  - pipeline 狀態檔 schema
  - evals.json
- `ark-superpowers` — 15 任務優化
  - plan 模板改 executor 相容 7 欄格式
  - checker one-pager 支援 + 空白章節攔截
  - build_docs.py --slug + upgrade 指令
  - ADR 單一來源 + hooks + parity check + evals
- `ark-html-dashboard` — theme: auto/dark/light
- `ark-data-dashboard` — theme: auto + depends_on html-dashboard
- `ark-webapp-generator` — theme: auto

### 治理
- 全庫 57 個 SKILL.md 回填 `category` / `outputs` frontmatter
- 5 組觸發詞衝突加 negative trigger 聲明
- `docs/skill-metadata-schema.md` — frontmatter 擴充規格
- `docs/report-frontmatter-standard.md` — 報告類 MD 標準
- `docs/trigger-matrix.md` — 衝突解法對照表

---

## 2026-08-05~07

### 新增
- `ark-grill-me` — 實作前拷問設計（加入預設 skills）
- `ark-spec-executor` — 執行 plan.md 任務清單（加入預設 skills）

### 修正
- `ark-wiki-engine` — 全面優化（受控詞彙表 + ingest guard + trust 欄位 + 雙模式路由 + 三件套銜接）
- `ark-wiki-engine` — 本地化 7 scripts（ingest/query/lint/graph/index/build/validate）

---

## 同步指南

```bash
# 從 kiro-cli 根目錄同步到子專案
cp -r ~/kiro-cli/.kiro/skills/ark-{skill-name} your-project/.kiro/skills/

# 批量同步核心 6 skills 到所有 agent
for agent in agents/*/; do
  for skill in ark-grill-me ark-superpowers ark-spec-executor ark-code-spec-validator ark-skill-creator ark-wiki-engine; do
    rm -rf "$agent/.kiro/skills/$skill"
    cp -r ~/kiro-cli/.kiro/skills/$skill "$agent/.kiro/skills/"
  done
done

# 同步報告雙軌
cp -r ~/kiro-cli/.kiro/skills/ark-md-report your-project/.kiro/skills/
cp -r ~/kiro-cli/.kiro/skills/ark-html-report your-project/.kiro/skills/
```

### 移除已廢棄 skills

```bash
rm -rf agents/*/.kiro/skills/ark-daily-decision-digest
rm -rf agents/*/.kiro/skills/ark-policy-translate
```
