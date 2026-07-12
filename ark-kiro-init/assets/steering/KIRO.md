---
inclusion: fileMatch
fileMatchPattern: "src/**/*.py"
---

# 🤖 Python 程式碼規範

> 只在讀寫 `src/` 下的 .py 檔案時自動載入。

---

## 一、程式碼風格

### 模組開頭

```python
"""模組一句話說明。"""
from __future__ import annotations
```

### 型別標註

- 使用 Python 3.11+ 語法：`str | None`、`list[str]`
- 所有公開函式必須有完整型別標註
- dataclass 欄位必須標註型別

### 非同步模式

- 所有 I/O 操作使用 `async/await`
- 超時用 `asyncio.wait_for()`
- Task 要保存引用（防 GC）

### 日誌

- 每個模組：`log = logging.getLogger(__name__)`
- 使用 `%s` 格式化（不用 f-string）

---

## 二、避坑注意事項

- 不要在 async 函式中呼叫阻塞 I/O
- YAML 用 `yaml.safe_load()`
- 路徑用 `Path` 物件
- 外部輸入要驗證
- Token 不要出現在日誌中
- Windows subprocess 需要 `CREATE_NEW_PROCESS_GROUP`
- 檔案讀寫加 `encoding="utf-8"`
