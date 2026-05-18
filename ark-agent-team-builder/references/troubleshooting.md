# 環境問題排查指南

## 前置條件

使用 `ark-team-agent team start` 前，必須確認以下環境：

### 1. Kiro CLI 安裝

| 項目 | 說明 |
|------|------|
| 需要的工具 | `kiro-cli`（terminal agent），**不是** `kiro`（IDE 入口） |
| 安裝方式 | `irm https://cli.kiro.dev/install.ps1 \| iex`（Windows） |
| 預設路徑 | `%LOCALAPPDATA%\kiro-cli\kiro-cli.exe`（Windows） |
| 驗證 | `kiro-cli --version` 應顯示 `kiro-cli-chat X.X.X` |

⚠️ **常見混淆：** 系統可能有 `kiro` 命令（Kiro IDE 的 Electron 入口），這**不是** Kiro CLI。`_resolve_binary()` 已修正為**只找 `kiro-cli`，不找 `kiro`**，避免啟動 IDE 而非 terminal agent。

```
kiro --version     → "0.11.133"（IDE，❌ 會開 Electron 視窗然後 process died）
kiro-cli --version → "kiro-cli-chat 2.2.2"（✅ 這才是 terminal agent）
```

**v0.12.0 修正：** `backend.py _resolve_binary()` 搜尋順序：
1. `shutil.which("kiro-cli")`（PATH）
2. `%LOCALAPPDATA%\kiro-cli\kiro-cli.exe`（Windows 預設安裝路徑）
3. `~/.local/bin/kiro-cli`（Linux/Mac）
4. 都找不到 → 報錯

### 2. 認證

| 方式 | 說明 |
|------|------|
| 互動式登入 | `kiro-cli` 首次執行會開瀏覽器登入（session 全域保存） |
| API Key（headless） | 設定 `KIRO_API_KEY` 環境變數（CI/CD 用） |
| 驗證 | `kiro-cli whoami` 應顯示登入資訊 |

### 3. PATH 設定

如果 `kiro-cli` 不在 PATH：

```powershell
# Windows — 加到使用者 PATH
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:LOCALAPPDATA\kiro-cli", "User")
```

```bash
# Linux/Mac
export PATH="$HOME/.local/bin:$PATH"
```

`ark-team-agent` 的 `backend.py` 有 fallback 邏輯會自動找預設安裝路徑，但建議還是加到 PATH。

### 4. Telegram Bot Token

| 環境變數 | 用途 |
|---------|------|
| `TELEGRAM_BOT_TOKEN` | 外部團隊 Bot |
| `TELEGRAM_BOT_TOKEN_INNER` | 內部團隊 Bot（如果分開） |

在 `.env` 檔案中設定，daemon 啟動時自動載入。

---

## 常見錯誤

### ❌ "kiro-cli not found in PATH"

**原因：** `kiro-cli.exe` 不在 PATH，且不在預設安裝路徑。

**解法：**
1. 確認已安裝：`ls $env:LOCALAPPDATA\kiro-cli\kiro-cli.exe`
2. 加到 PATH 或確認 `backend.py` 的 fallback 路徑正確

### ❌ "Instance xxx process died during startup"

**可能原因（依序排查）：**

| # | 原因 | 排查方式 | 解法 |
|---|------|---------|------|
| 1 | **找到 `kiro`（IDE）而非 `kiro-cli`** | 看 pid 是否開了 Electron 視窗 | 確認 `_resolve_binary()` 回傳 `kiro-cli.exe` 路徑 |
| 2 | kiro-cli 未認證 | `kiro-cli whoami` | 執行 `kiro-cli` 手動登入一次 |
| 3 | READY_PATTERN 不匹配 | 看 daemon log 的 output | 更新 `backend.py` READY_PATTERN |
| 4 | MCP server 連不上 | 檢查 health_port 是否被佔用 | 換 port 或殺佔用程序 |
| 5 | working_directory 不存在 | 檢查路徑是否正確 | 建立目錄或修正路徑 |
| 6 | .kiro/settings/mcp.json 格式錯 | 手動檢查 JSON | 刪除讓 daemon 重新產生 |

### ❌ "0 of N mcp servers initialized"

**原因：** kiro-cli 啟動時 MCP team server 還沒 ready（daemon API 還沒起來）。

**解法：** 這是正常的 — kiro-cli 會等待 MCP server，不會因此退出。如果超時退出，檢查 daemon API port 是否正確。

### ❌ 找到 `kiro` 但不是 Kiro CLI

**原因：** 系統有 Kiro IDE 的 `kiro.cmd`（Electron），被誤認為 Kiro CLI。

**排查：**
```powershell
Get-Command kiro | Select-Object Source
# 如果顯示 ...\Programs\Kiro\bin\kiro.cmd → 這是 IDE，不是 CLI
```

**解法：** 確保 `kiro-cli` 在 PATH 中優先於 `kiro`，或直接用完整路徑。

---

## 環境驗證 Checklist

啟動前跑一遍：

```powershell
# 1. Kiro CLI 存在
kiro-cli --version
# 預期：kiro-cli-chat 2.x.x

# 2. 已認證
kiro-cli whoami
# 預期：Logged in with ...

# 3. Port 未被佔用
Test-NetConnection -ComputerName 127.0.0.1 -Port 23030
# 預期：TcpTestSucceeded: False（沒人佔用）

# 4. .env 存在
Test-Path agents/.env
# 預期：True

# 5. team.yaml 有效
py .kiro/skills/ark-agent-team-builder/scripts/validate_team.py agents/team.yaml
# 預期：✅ valid
```
