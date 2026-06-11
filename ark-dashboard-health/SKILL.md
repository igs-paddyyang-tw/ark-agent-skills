---
author: paddyyang
name: ark-dashboard-health
description: |
  自動化測試 Dashboard 所有 API 端點 + SSE 連線 + 前端頁面可用性。
  產出 Health Report（通過/失敗清單 + 回應時間）。
  使用此 Skill 當使用者提及 dashboard 正常嗎、API 測試、SSE 測試、
  健康檢查、端點測試、dashboard health、服務可用性、
  或任何需要驗證 Web Dashboard 是否正常運作的場景。
metadata:
  version: "1.0"
  updated: 2026-06-07
---

# ark-dashboard-health

自動化測試 Dashboard API + SSE + 頁面可用性，產出 Health Report。

## 觸發條件

- 「dashboard 正常嗎」、「API 測試」、「SSE 測試」
- 「健康檢查」、「端點測試」、「dashboard health」
- 「服務可用性」、「跑一次 health check」

## 測試項目

| # | 測試 | 方法 | 通過條件 |
|---|------|------|---------|
| 1 | Health | `GET /health` | 200 + `{"status": "ok"}` |
| 2 | Status | `GET /status` | 200 + 6 agent 狀態 |
| 3 | Send | `POST /send` | 200 或 404 |
| 4 | Dashboard 頁面 | `GET /dashboard` | 200 + HTML |
| 5 | SSE | `GET /api/events` | content-type: text/event-stream |
| 6 | Messages | `GET /api/messages` | 200 + JSON array |
| 7 | Tasks | `GET /api/tasks` | 200（或標記缺失） |

## 操作流程

```python
import httpx, asyncio, time

BASE = "http://localhost:13030"

async def check():
    results = []
    async with httpx.AsyncClient(timeout=5) as c:
        for name, method, path, validator in TESTS:
            t0 = time.time()
            try:
                r = await getattr(c, method)(f"{BASE}{path}")
                ms = int((time.time() - t0) * 1000)
                passed = validator(r)
                results.append((name, passed, r.status_code, ms))
            except Exception as e:
                results.append((name, False, 0, 0))
    return results
```

## 輸出格式

```
📊 Dashboard Health — Score: {score}/100

| 端點 | 狀態 | 回應時間 |
|------|------|---------|
| ✅ GET /health | 200 | 12ms |
| ✅ GET /status | 200 | 15ms |
| ✅ GET /dashboard | 200 | 8ms |
| ✅ GET /api/events | SSE OK | — |
| ❌ GET /api/tasks | 404 | 5ms |

缺失：/api/tasks（spec 定義但未實作）
💡 建議：補實作 Task Board API
```

## 進階：Dashboard 前端檢查

API 全過時進一步檢查 HTML：

| 元件 | 條件 |
|------|------|
| Status Panel | HTML 含 `agent-card` × 6 |
| Message Flow | 有 `EventSource('/api/events')` |
| Task Board | 有 task-board 區塊 |

## 排程整合

```yaml
- name: dashboard-health
  target: ad-agent
  prompt: "🏥 Dashboard Health Check，回報結果。"
  cron: "0 9 * * *"
```

## 注意事項

- 服務須已啟動（port 13030）
- SSE 只驗連線不等事件
- 報告產出到 `docs/dashboard-health-report.md`
