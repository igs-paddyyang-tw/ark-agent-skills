---
name: ark-docker-deploy
description: |
  產出容器化部署配置（Dockerfile + docker-compose.yaml + .dockerignore + 部署腳本），
  支援 Python / Node / Go 專案自動偵測，multi-stage build 最佳化。
  使用此 Skill 當使用者提及 Docker 部署、容器化、docker compose、
  Dockerfile、部署腳本、containerize、打包部署、
  或任何需要將專案容器化的場景。
  不適用於：Kubernetes／雲端部署管線（本 skill 只到 docker compose）；本機常駐服務用 systemd user service；
  新建整個應用骨架請用 ark-webapp-generator。
metadata:
  schema_version: "1.2"
  status: active
  category: scaffolder
  form: instruction
  domain: general
  outputs:
    - format: code
      audience: ai
  author: paddyyang
  version: "1.1.0"
  updated: 2026-10-27
  # 實測：照本檔範本產最小專案 → compose build／up -d → healthy＋/api/status 200
  #   2026-10-21 Python（python:3.12-slim）35 秒；2026-10-27 Node（node:22-slim，227MB）25 秒、
  #   Go（golang:1.23 → alpine:3.20，13MB、uid 65534）15 秒
  tested_against:
    docker: "28.3.3"
    docker-compose: "2.39.1"
    python-image: "3.12-slim"
    node-image: "22-slim"
    go-image: "golang:1.23 → alpine:3.20"
---

# ark-docker-deploy

產出容器化部署配置，一鍵 Docker 化任何專案。

## 觸發條件

- 「Docker 部署」、「容器化」、「docker compose」
- 「Dockerfile」、「部署腳本」、「containerize」
- 「打包部署」、「Docker 化」

---

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 專案目錄 |
| `services` | `list[str]` | ❌ | 自動偵測 | 服務清單（如 `["team-agent", "webbot"]`） |
| `python_version` | `str` | ❌ | `"3.12"` | Python 版本 |
| `node_version` | `str` | ❌ | `"22"` | Node 版本（需 18+，健康檢查用內建 fetch） |
| `go_version` | `str` | ❌ | `"1.23"` | Go 版本（對齊 go.mod 的 `go` 指令） |
| `entry` | `str` | ❌ | `"server.js"` | Node 入口檔 |
| `main_pkg` | `str` | ❌ | `"."` | Go main 套件路徑（如 `./cmd/server`） |
| `health_port` | `int` | ✅ | — | 健康檢查與對外 port（`/api/status`） |
| `expose_ports` | `dict` | ❌ | `{}` | 服務對外 port（如 `{"api": 8000}`） |
| `env_file` | `str` | ❌ | `".env"` | 環境變數檔案 |

## 前置條件

- 專案有 `requirements.txt` 或 `pyproject.toml`（Python）
- 或 `package.json`（Node）
- 或 `go.mod`（Go）

---

## 產出指引

### 步驟 1：偵測專案類型

```python
# 自動偵測邏輯
if (project_dir / "pyproject.toml").exists() or (project_dir / "requirements.txt").exists():
    lang = "python"
elif (project_dir / "package.json").exists():
    lang = "node"
elif (project_dir / "go.mod").exists():
    lang = "go"
```

### 步驟 2：產出 Dockerfile（Python multi-stage）

```dockerfile
# ── Build Stage ──
FROM python:{python_version}-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime Stage ──
FROM python:{python_version}-slim

WORKDIR /app

# 系統依賴（如需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製已安裝的套件
COPY --from=builder /install /usr/local

# 複製原始碼
COPY . .

# 環境變數
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 健康檢查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:{health_port}/api/status || exit 1

# 啟動
CMD ["python", "start.py"]
```

### 步驟 2b：產出 Dockerfile（Node multi-stage）

```dockerfile
# ── Build Stage ──
FROM node:{node_version}-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
# TypeScript／打包專案：改 `RUN npm ci && npm run build`，runtime 只複製 dist/ 與 production 依賴

# ── Runtime Stage ──
FROM node:{node_version}-slim

WORKDIR /app

# 複製已安裝的依賴（.dockerignore 排除本機 node_modules，這裡只用 builder 裝的）
COPY --from=builder /app/node_modules ./node_modules

# 複製原始碼
COPY . .

ENV NODE_ENV=production

# 健康檢查（node 18+ 內建 fetch，不另裝 curl）
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD node -e "fetch('http://localhost:{health_port}/api/status').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# 啟動
CMD ["node", "{entry}"]
```

> `npm ci` 需要 `package-lock.json`；沒有就先在本機 `npm install --package-lock-only` 產一份並進版控。

### 步驟 2c：產出 Dockerfile（Go multi-stage）

```dockerfile
# ── Build Stage ──
FROM golang:{go_version} AS builder

WORKDIR /src
# go.sum* 用萬用字元：沒有外部依賴的專案沒有 go.sum，go.mod 命中即可
COPY go.mod go.sum* ./
RUN go mod download

COPY . .
# 靜態連結，runtime 不需要 libc
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/app {main_pkg}

# ── Runtime Stage ──
FROM alpine:3.20

WORKDIR /app
COPY --from=builder /out/app /app/app

# 非 root 執行
USER 65534

# 健康檢查（alpine 內建 busybox wget，不另裝 curl）
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:{health_port}/api/status >/dev/null || exit 1

# 啟動
CMD ["/app/app"]
```

> `{main_pkg}` 預設 `.`；`cmd/server` 這類多 binary 專案填 `./cmd/server`。
> 用 alpine 而不是 distroless：distroless 沒有 shell 與 wget，HEALTHCHECK 無法執行。

### 步驟 3：產出 docker-compose.yaml

```yaml
services:
  {service_name}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {service_name}
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "{health_port}:{health_port}"
    volumes:
      - ./data:/app/data          # 持久化資料
      - ./config:/app/config      # 配置檔
    healthcheck:
      # 與 Dockerfile HEALTHCHECK 同一個指令：Python 用 curl；Node 用
      # ["CMD", "node", "-e", "fetch(...)..."]；Go 用 ["CMD", "wget", "-qO-", "http://localhost:{health_port}/api/status"]
      test: ["CMD", "curl", "-f", "http://localhost:{health_port}/api/status"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 步驟 4：產出 .dockerignore

```
.git
.venv
venv
__pycache__
*.pyc
.pytest_cache
.env
*.egg-info
node_modules
.kiro
agents/*/output
data/*.db
```

### 步驟 5：產出部署腳本

**deploy.sh：**

```bash
#!/bin/bash
set -e

echo "🐳 Building and deploying..."

# Build
docker compose build --no-cache

# Stop old containers
docker compose down

# Start
docker compose up -d

# Wait for health
echo "⏳ Waiting for health check..."
sleep 10
curl -f http://localhost:{health_port}/api/status && echo "✅ Deployed!" || echo "❌ Health check failed"

# Show logs
docker compose logs --tail=20
```

**deploy.ps1（Windows）：**

```powershell
Write-Host "🐳 Building and deploying..."

docker compose build --no-cache
docker compose down
docker compose up -d

Start-Sleep -Seconds 10
try {
    Invoke-RestMethod http://localhost:{health_port}/api/status
    Write-Host "✅ Deployed!"
} catch {
    Write-Host "❌ Health check failed"
}

docker compose logs --tail=20
```

### 步驟 6：驗證

```bash
# Build
docker compose build

# 啟動
docker compose up -d

# 確認健康
docker compose ps
curl http://localhost:{health_port}/api/status

# 查看日誌
docker compose logs -f
```

---

## 產出檔案清單

```
{project_dir}/
├── Dockerfile
├── docker-compose.yaml
├── .dockerignore
└── scripts/
    ├── deploy.sh
    └── deploy.ps1
```

## 多服務範例（team-agent + webbot）

```yaml
services:
  team-agent:
    build: .
    command: python start.py
    env_file: .env
    ports: ["13030:13030"]
    restart: unless-stopped

  webbot:
    build: .
    command: python -m ark_team_webbot start
    env_file: .env
    ports: ["3030:3030"]
    depends_on:
      team-agent:
        condition: service_healthy
    restart: unless-stopped
```

## 注意事項

- multi-stage build 減少 image 大小（~200MB vs ~800MB）
- `.env` 不進 image（透過 `env_file` 掛載）
- compose 檔**不寫頂層 `version:`** —— Compose v2 已廢除該欄位，寫了每個指令都會印 obsolete 警告（2026-10-21 實測 2.39.1）
- `data/` 目錄用 volume 持久化（SQLite DB）
- HEALTHCHECK 確保 orchestrator 能偵測服務狀態
- `restart: unless-stopped` 確保 crash 後自動重啟
- Windows 用 `deploy.ps1`，Linux/Mac 用 `deploy.sh`
