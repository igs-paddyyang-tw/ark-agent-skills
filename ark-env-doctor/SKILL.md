---
name: ark-env-doctor
description: |
  當使用者遇到開發環境問題時使用此技能。觸發條件包括：環境檢查、套件缺失、
  Python/Go/Node 版本問題、venv 建立、requirements.txt 安裝失敗、
  ModuleNotFoundError、ImportError、新手環境設定、一鍵安裝、
  DevContainer 建立、或任何「我的環境跑不起來」相關問題。
  也適用於產出 setup 腳本、修復腳本、或環境診斷報告。
  另有端點模式（原 ark-dashboard-health 併入）：檢查已部署服務的 API 端點、SSE 連線、頁面可用性，
  使用此 Skill 當使用者提及 dashboard 正常嗎、API 測試、SSE 測試、健康檢查、端點測試、
  dashboard health、服務可用性。
  不適用於：服務的業務指標與數值異常請用 ark-pipeline-recipes（anomaly-detector 頁）。
metadata:
  version: "1.1.0"
  replaces: [ark-dashboard-health]
  schema_version: "1.2"
  status: active
  updated: 2026-10-29
  category: ops
  form: executor
  domain: general
  outputs:
    - format: md
      audience: ai
  author: paddyyang
---

# ark-env-doctor

檢查、診斷並修復開發環境的 Skill。

## 工作流程

1. 偵測當前環境狀態
2. 比對專案需求（requirements.txt / go.mod / package.json）
3. 產出診斷報告
4. 自動修復或產出修復腳本

## 使用方式

```bash
# 完整診斷
python scripts/env_doctor.py

# 自動修復模式
python scripts/env_doctor.py --fix

# 僅檢查特定語言
python scripts/env_doctor.py --check python
python scripts/env_doctor.py --check go
python scripts/env_doctor.py --check node
```

## 端點模式（已部署服務，原 ark-dashboard-health）

開發機環境以外，也檢查**已經跑起來的服務**：狀態碼、回應時間、SSE 連線。任一失敗 exit 1，可直接接排程。

```bash
# 一般端點（預設預期 2xx）＋ SSE（只驗 content-type，不等事件）
python scripts/env_doctor.py --endpoints http://localhost:8888/health --sse http://localhost:8888/api/events
# 端點多時用清單檔（JSON；YAML 需 PyYAML）：每筆 {name, url, method?, expect_status?, contains?, sse?}
python scripts/env_doctor.py --endpoints-file endpoints.json --output docs/endpoint-report.md
```

- 實作在 `scripts/endpoints.py`（只用標準庫：環境壞了也能跑）；測試 `scripts/tests/test_env_doctor_endpoints.py`
- 原 dashboard-health 的端點表、前端元件檢查、排程範例原樣保留在 [`references/dashboard-health.md`](references/dashboard-health.md)
  （當時寫死 port 13030、6 個 agent，套用前改成你的服務）

## 偵測項目

| 項目 | 檢查內容 |
|------|----------|
| Git | 版本、是否在 PATH 中 |
| Gemini CLI | 版本、全域 npm 安裝狀態 |
| Kiro CLI | 版本、是否可用 |
| Python | 版本、路徑、venv 狀態、pip 可用性 |
| Go | 版本、GOPATH、go.mod 存在 |
| Node | 版本、npm/pnpm、node_modules 狀態 |
| 套件 | requirements.txt / go.mod / package.json 缺失比對 |
| 系統 | OS、架構、PATH 設定 |

## 輸出格式

### 診斷報告（Markdown）

```markdown
# 🧠 Environment Report

## System
- OS: Windows 11 x64
- Shell: PowerShell 7.4

## Python ✅
- Version: 3.11.5
- Path: C:\Python311\python.exe
- venv: active (./venv)
- pip: 24.0

## Go ⚠️
- Not found in PATH
- Fix: `winget install GoLang.Go`

## Missing Packages (3)
- google-genai
- pydantic>=2.5.0
- playwright

## Fix Commands
pip install google-genai pydantic>=2.5.0 playwright
```

### 修復腳本

自動產出 `fix_env.sh`（Linux/Mac）和 `fix_env.ps1`（Windows），包含：
- 缺失工具安裝指令
- 套件安裝指令
- venv 建立與啟用
- 環境變數設定

## 修復策略

1. **venv 不存在** → 建立 venv + 安裝 requirements
2. **套件缺失** → pip install / go get / npm install
3. **工具未安裝** → 提供安裝指令（winget/brew/apt）
4. **版本不符** → 提示升級路徑

## DevContainer 產出

當使用者需要容器化開發環境時，產出：

```
.devcontainer/
├── devcontainer.json
└── Dockerfile
```

使用 `templates/` 中的範本，根據偵測到的語言組合產出。

## 注意事項

- 優先使用 venv 隔離，避免全域安裝
- Windows 使用 `py` launcher，Linux/Mac 使用 `python3`
- 修復前先確認使用者同意（除非 `--fix` 模式）
- 大型安裝（如 CUDA、Docker）僅提供指引，不自動執行

---

## Workshop 模式

當使用者說「檢查我的開發環境」且專案有 Workshop 教材時，優先檢查 Workshop 必要項目：

### agent-team-workshop 必要項目

| 項目 | 檢查 | 修復 |
|------|------|------|
| Python 3.12+ | 版本 ≥ 3.12 | 提示升級 |
| Git | `git --version` | 平台對應安裝指令 |
| Kiro CLI | `kiro-cli --version` | 官方安裝腳本 |
| `.kiro/skills/` | 目錄存在且有 SKILL.md | `git clone` 指令 |
| TELEGRAM_BOT_TOKEN | `.env` 中有值 | 引導到 @BotFather |

### ai-bot-workshop 必要項目

| 項目 | 檢查 | 修復 |
|------|------|------|
| Python 3.12+ | 版本 ≥ 3.12 | 提示升級 |
| Node.js 20+ | 版本 ≥ 20 | 提示升級 |
| Git | `git --version` | 平台對應安裝指令 |
| Gemini CLI | `gemini --version` | `npm install -g @google/gemini-cli` |
| `.kiro/skills/` | 目錄存在 | `git clone` 指令 |

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 1.1.0 | 2026-10-29 | 新增端點模式 `--endpoints`／`--sse`／`--endpoints-file`（`scripts/endpoints.py`＋測試）；ark-dashboard-health 併入，原文在 `references/dashboard-health.md` |
