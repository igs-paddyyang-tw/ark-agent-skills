# AC-ID 約定（Acceptance Criteria Identifier）

## 概述

AC-ID 是連結「Plan 驗收條件」與「測試程式碼」的唯一識別碼，取代 keyword matching 的模糊比對，確保 test ↔ spec 映射精準且可追蹤。

---

## 格式規範

### ID 格式

```
AC-{三位數字}
```

範例：`AC-001`、`AC-002`、`AC-015`

### Plan 任務表中的寫法

在任務表的「驗收條件」欄位或獨立驗收清單中標註：

```markdown
| 任務 | 負責人 | 預估工時 | 依賴 | AC-ID | 驗收條件 |
|------|--------|----------|------|-------|----------|
| 實作 /api/send | coder | 4h | — | AC-001 | POST /api/send 回 200 + message_id |
| 錯誤處理 | coder | 2h | AC-001 | AC-002 | 無效 payload 回 422 + error detail |
```

### Test docstring 中的寫法

在 test function 的 docstring 中以 `AC:` 前綴標示：

```python
def test_send_message_success():
    """AC: AC-001

    POST /api/send with valid payload returns 200 and message_id.
    """
    ...

def test_send_message_invalid_payload():
    """AC: AC-002

    POST /api/send with invalid payload returns 422 with error detail.
    """
    ...
```

多條 AC 對應同一 test 時用逗號分隔：

```python
def test_send_and_error_flow():
    """AC: AC-001, AC-002

    驗證正常送出 + 異常 payload 的完整流程。
    """
    ...
```

---

## 正確範例 ✅

### Plan 中

```markdown
## 驗收條件

| AC-ID | 條件描述 |
|-------|----------|
| AC-001 | 呼叫 POST /api/send 帶 valid payload → HTTP 200 + body 含 message_id |
| AC-002 | 呼叫 POST /api/send 帶 invalid payload → HTTP 422 + body 含 error |
| AC-003 | 發送超時 5 秒 → HTTP 504 + retry header |
```

### Test 中

```python
class TestSendEndpoint:
    def test_valid_send(self):
        """AC: AC-001"""
        resp = client.post("/api/send", json={"instance": "a", "message": "hi"})
        assert resp.status_code == 200
        assert "message_id" in resp.json()

    def test_invalid_payload(self):
        """AC: AC-002"""
        resp = client.post("/api/send", json={})
        assert resp.status_code == 422
        assert "error" in resp.json()

    def test_timeout_retry(self):
        """AC: AC-003"""
        resp = client.post("/api/send", json=SLOW_PAYLOAD)
        assert resp.status_code == 504
        assert "Retry-After" in resp.headers
```

---

## 錯誤範例 ❌

### ❌ 沒有 AC-ID 標記

```python
def test_send():
    """測試送出功能。"""  # 沒有 AC: 前綴 → validator 無法映射
    ...
```

### ❌ AC-ID 格式錯誤

```python
def test_send():
    """AC: 1"""  # 缺少 AC- 前綴和三位數字
    ...

def test_send2():
    """AC: AC-1"""  # 不是三位數字
    ...
```

### ❌ Plan 中沒有 AC-ID 欄位

```markdown
| 任務 | 驗收條件 |
|------|----------|
| 實作 /api/send | 能送出訊息 |  <!-- 沒有 AC-ID → 無法精準追蹤 -->
```

---

## Validator 匹配邏輯

### 優先級

1. **AC-ID 精準匹配**（高信度）：test docstring 的 `AC: AC-XXX` 直接對應 plan 中同編號的驗收條件
2. **Keyword matching**（低信度 fallback）：僅在 test 或 plan 中缺少 AC-ID 時啟用

### 匹配流程

```
plan 驗收條件列表
       │
       ├─ 有 AC-ID → 搜尋 tests/ 中 docstring 含相同 AC-ID
       │              ├─ 找到 → ✅ 已覆蓋（高信度）
       │              └─ 沒找到 → ❌ 未覆蓋
       │
       └─ 無 AC-ID → fallback keyword matching
                      ├─ ≥2 關鍵字匹配 → ⚠️ 已覆蓋（低信度）
                      └─ <2 關鍵字匹配 → ❌ 未覆蓋
```

### 報告標示

| 匹配方式 | 信度標示 | 說明 |
|----------|----------|------|
| AC-ID 精準 | `🔗 AC-001` | 高信度，可信賴 |
| Keyword fallback | `⚠️ keyword` | 低信度，建議補 AC-ID |
| 未匹配 | `❌ uncovered` | 缺少對應測試 |

報告範例：

```
📊 測試覆蓋分析

| AC-ID | 驗收條件 | 對應 Test | 信度 |
|-------|----------|-----------|------|
| AC-001 | POST /api/send → 200 | test_valid_send | 🔗 高 |
| AC-002 | invalid → 422 | test_invalid_payload | 🔗 高 |
| AC-003 | timeout → 504 | — | ❌ 未覆蓋 |
| — | 「能查詢歷史」 | test_history | ⚠️ keyword（低信度） |
```

---

## 編號規則

- **從 AC-001 開始**，全專案單調遞增
- 每個 milestone / phase 可自行決定起始區段（如 Phase 2 從 AC-100 開始），但不強制
- **刪除的 AC-ID 不重用** — 避免混淆歷史追蹤
- 一個 AC-ID 對應**一個原子驗收條件**（不要一條 AC 包含多個獨立斷言）
