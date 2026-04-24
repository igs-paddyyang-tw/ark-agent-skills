# Schedule YAML 格式規範

本文件定義 ScheduleEngine 使用的排程 YAML 格式，所有排程定義檔案存放於 `workflows/schedules/` 目錄下。

---

## 頂層結構

排程定義檔案包含一個 `schedules` 陣列，每個元素代表一個排程實例。

```yaml
schedules:
  - id: ...
    workflow_id: ...
    cron: ...
    enabled: ...
    params: ...
```

---

## Schedule 欄位定義

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `id` | `str` | ✅ | 排程唯一識別碼（snake_case，全域唯一） |
| `workflow_id` | `str` | ✅ | 對應的工作流 `id`（必須在 `workflows/` 中存在） |
| `cron` | `str` | ✅ | APScheduler cron 表達式（5 欄位格式） |
| `enabled` | `bool` | ✅ | 是否啟用此排程（`true` / `false`） |
| `params` | `dict` | ❌ | 傳入工作流的參數，支援 `${ENV_VAR}` 環境變數引用 |

---

## Cron 表達式格式

使用 APScheduler 的 5 欄位 cron 格式：

```
分鐘  小時  日  月  星期
 ┃     ┃    ┃   ┃    ┃
 ┃     ┃    ┃   ┃    ┗━ 星期幾（0-6 或 mon-sun，0=週日）
 ┃     ┃    ┃   ┗━━━━━ 月份（1-12 或 jan-dec）
 ┃     ┃    ┗━━━━━━━━━ 日期（1-31）
 ┃     ┗━━━━━━━━━━━━━━ 小時（0-23）
 ┗━━━━━━━━━━━━━━━━━━━━ 分鐘（0-59）
```

常用範例：

| 表達式 | 說明 |
|--------|------|
| `"30 8 * * 1-5"` | 週一至週五 08:30 |
| `"0 14 * * 1-5"` | 週一至週五 14:00 |
| `"0 9 * * *"` | 每天 09:00 |
| `"*/30 * * * *"` | 每 30 分鐘 |
| `"0 0 1 * *"` | 每月 1 日 00:00 |

APScheduler 的 `CronTrigger.from_crontab(cron)` 可直接解析此格式。

---

## 環境變數引用

排程 `params` 中支援 `${ENV_VAR}` 語法引用環境變數。ScheduleEngine 在排程觸發時（非載入時）進行替換。

語法規則：
- `${VAR_NAME}` — 引用環境變數 `VAR_NAME`
- 若環境變數未設定，替換為空字串 `""`
- 替換使用 `os.environ.get(VAR_NAME, "")` 實作
- 支援巢狀 dict 中的環境變數引用（遞迴替換）

```yaml
params:
  notify_chat_id: "${NOTIFY_CHAT_ID}"       # 從環境變數取得
  source: "slotcatalog"                      # 固定值
  provider: "${DEFAULT_PROVIDER}"            # 從環境變數取得
```

替換邏輯（`_resolve_env_vars`）：

```python
import os
import re

def _resolve_env_vars(params: dict) -> dict:
    """遞迴替換 params 中的 ${ENV_VAR} 引用。"""
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str):
            resolved[key] = re.sub(
                r"\$\{(\w+)\}",
                lambda m: os.environ.get(m.group(1), ""),
                value,
            )
        elif isinstance(value, dict):
            resolved[key] = _resolve_env_vars(value)
        else:
            resolved[key] = value
    return resolved
```

---

## 完整範例：slot_morning_report.yaml

```yaml
# workflows/schedules/slot_morning_report.yaml
# 每日老虎機趨勢報表排程定義

schedules:
  # 晨報：週一至週五 08:30 推送
  - id: slot_morning_report
    workflow_id: daily_slot_report
    cron: "30 8 * * 1-5"
    enabled: true
    params:
      source: "slotcatalog"
      notify_chat_id: "${NOTIFY_CHAT_ID}"
      days: 7

  # 下午幹部簡報：週一至週五 14:00 推送（可選）
  - id: slot_afternoon_brief
    workflow_id: daily_slot_report
    cron: "0 14 * * 1-5"
    enabled: false
    params:
      source: "slotcatalog"
      notify_chat_id: "${MANAGER_CHAT_ID}"
      days: 3
      provider: "${DEFAULT_PROVIDER}"
```

---

## ScheduleEngine 行為規範

### 載入（`load_schedules`）

1. 讀取 YAML 檔案，解析 `schedules` 陣列
2. 驗證每個排程的必要欄位（`id`、`workflow_id`、`cron`、`enabled`）
3. 回傳排程定義清單（不進行環境變數替換）

### 啟動（`start`）

1. 建立 `AsyncIOScheduler` 實例
2. 遍歷所有排程定義，僅對 `enabled=True` 的排程：
   - 使用 `CronTrigger.from_crontab(cron)` 建立觸發器
   - 註冊 `_trigger_workflow` 為 job
3. 啟動 scheduler

### 觸發（`_trigger_workflow`）

1. 取得排程定義的 `params`
2. 呼叫 `_resolve_env_vars(params)` 替換環境變數
3. 呼叫 `workflow_engine.run(workflow_id, resolved_params)`
4. 若工作流執行失敗，記錄錯誤日誌，不拋出例外

### 切換（`toggle`）

1. 找到指定 `schedule_id` 的排程定義
2. 翻轉 `enabled` 狀態
3. 若切換為啟用 → 註冊新 job
4. 若切換為停用 → 移除既有 job
5. 回傳切換後的 `enabled` 狀態

### 停止（`stop`）

1. 呼叫 `scheduler.shutdown(wait=False)` 優雅關閉
2. 清理所有已註冊的 job
