---
name: ark-docker-deploy
description: |
  產出容器化部署配置（Dockerfile + docker-compose.yaml + .dockerignore + 部署腳本），
  支援 Python / Node / Go 專案自動偵測，multi-stage build 最佳化。
  使用此 Skill 當使用者提及 Docker 部署、容器化、docker compose、
  Dockerfile、部署腳本、containerize、打包部署、
  或任何需要將專案容器化的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-18
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

### 步驟 3：產出 docker-compose.yaml

```yaml
version: "3.8"

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
- `data/` 目錄用 volume 持久化（SQLite DB）
- HEALTHCHECK 確保 orchestrator 能偵測服務狀態
- `restart: unless-stopped` 確保 crash 後自動重啟
- Windows 用 `deploy.ps1`，Linux/Mac 用 `deploy.sh`
