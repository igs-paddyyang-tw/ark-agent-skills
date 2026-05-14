# Runtime 模組精簡版規格

## 設計原則

- 零第三方依賴（除 pyyaml）
- asyncio 原生（手寫 HTTP server，不用 aiohttp）
- 手寫 stdio JSON-RPC（不用 mcp SDK）
- Windows + Linux 相容（subprocess 用 asyncio）
- 總行數 < 1000 行

## 模組規格

### daemon.py（~200 行）

```python
class TeamDaemon:
    def __init__(self, config_path: str): ...
    async def run(self): ...           # 主迴圈
    async def start_instance(self, name, cfg): ...
    async def stop_instance(self, name): ...
    async def stop_all(self): ...
    async def _health_loop(self): ...  # 定期檢查子程序存活
```

職責：
- 讀取 team.yaml → 為每個 instance 啟動 kiro-cli
- 監控子程序健康（hang detection）
- 優雅關閉（SIGINT/SIGTERM）

### backend.py（~150 行）

```python
class KiroBackend:
    def build_command(self, cfg) -> str: ...
    def write_steering(self, cfg, instances): ...
    def write_mcp_config(self, cfg): ...
    def write_team_context(self, cfg, instances): ...
```

職責：
- 組裝 `kiro-cli chat --trust-all-tools --legacy-ui --resume --model auto`
- 寫入 .kiro/steering/（agents.md symlink + team-context.md 動態產生）
- 寫入 .kiro/settings/mcp.json（注入 team MCP server）

### config.py（~100 行）

```python
@dataclass
class InstanceConfig:
    working_directory: str
    description: str
    role: str  # leader | worker

@dataclass
class TeamConfig:
    instances: dict[str, InstanceConfig]
    health_port: int = 13030
    model: str = "auto"
    timeout_minutes: int = 60

def load_config(path: str) -> TeamConfig: ...
```

### process.py（~80 行）

```python
class ManagedProcess:
    def __init__(self, name: str): ...
    async def start(self, cmd: str, cwd: str): ...
    async def kill(self): ...
    def is_alive(self) -> bool: ...
    async def send(self, text: str): ...  # 寫入 stdin
```

### mcp_server.py（~250 行）

stdio JSON-RPC 2.0 MCP Server，提供 10 個工具：

```python
TOOLS = {
    "reply": {"description": "回覆使用者"},
    "send_to_instance": {"description": "發訊息給其他 agent"},
    "delegate_task": {"description": "委派任務"},
    "query_team_status": {"description": "查詢團隊狀態"},
    "create_task": {"description": "建立任務"},
    "update_task": {"description": "更新任務狀態"},
    "log_to_leader": {"description": "私下回報 leader"},
    "list_tasks": {"description": "列出任務板"},
    "record_spend": {"description": "記錄成本"},
    "broadcast_all": {"description": "廣播全員"},
}
```

通訊方式：透過 daemon 的 HTTP API 轉發。

### api.py（~100 行）

手寫 asyncio HTTP server（`asyncio.start_server`）：

```
GET  /health          → {"status": "ok", "instances": {...}}
POST /send/{name}     → 發送訊息給指定 instance
GET  /status          → 全部 instance 狀態
```

### scheduler.py（~80 行）

```python
class TeamScheduler:
    def __init__(self, config_path: str, send_fn): ...
    def start(self): ...
    def stop(self): ...
    def _parse_cron(self, expr: str) -> dict: ...
    async def _trigger(self, target, prompt): ...
```

支援格式：
- 標準 5-field cron：`10 9-21 * * *`
- 簡寫：`daily:21:00`、`hourly:10`
