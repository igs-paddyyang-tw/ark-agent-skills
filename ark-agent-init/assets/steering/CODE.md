---
inclusion: fileMatch
fileMatchPattern: "{src,scripts}/**/*.py"
---

# 🤖 Python 程式碼與腳本規範

> 讀寫 `src/` 或 `scripts/` 下的 `.py` 檔案時自動載入。
> 「一、通用」適用所有 Python；「三、長駐 async 服務」只在你寫 daemon / bot / 常駐服務時才適用。

---

## 一、通用（所有 .py 都遵守）

### 模組開頭

```python
"""模組一句話說明。"""
from __future__ import annotations
```

### 型別標註

- 使用 Python 3.12+ 語法：`str | None`、`list[str]`、`dict[str, int]`
- 所有公開函式必須有完整型別標註；dataclass 欄位必須標註型別

### 路徑與 I/O

- 路徑一律用 `pathlib.Path`，不用字串拼接、不用 `os.path`
- 檔案讀寫一律帶 `encoding="utf-8"`
- YAML 用 `yaml.safe_load()`（禁 `yaml.load`）；JSON 用標準庫 `json`

### 安全

- 外部輸入（CLI 參數、API 回應、檔案內容）一律當不可信，用前先驗證
- `subprocess` 用 **list 形式**（`["git", "status"]`），**禁 `shell=True`**；禁 `os.system` / `eval` / `exec`
- Token／密鑰只從環境變數讀，**不寫進 log、不落 config 版控**
- 拼 SQL 用參數化查詢，不用字串插值

---

## 二、CLI 腳本規範（scripts/ 下的一次性/工具腳本）

> 多數 agent 腳本是**同步** CLI 工具（非常駐服務），不要為了 async 而 async。

- 用 `argparse`；`--help` 必須 **rc=0 且零副作用**（不建目錄、不寫檔、不打 API）——
  若腳本啟動要做 preflight／建目錄，**先攔 `--help` 再做那些事**
- exit code 有語意：`0` 成功、`1` 一般失敗、`2` 參數錯誤；守門類可再分流（如 `3` 衝突）
- 看 rc 不要接 pipe（`cmd | tail` 會吃掉非 0 的 rc）
- 副作用集中在 `main()`，純函式可測；有守門就寫**反證測試**（故意違規要紅、還原要綠）
- 日誌：`log = logging.getLogger(__name__)`；logging 呼叫用 `%s` 惰性格式化（不用 f-string），
  一般 print 給人看則不限

---

## 三、長駐 async 服務（daemon / bot / 常駐服務才適用）

> ⚠️ 只有你在寫「跑著不停的服務」時才套這節。一次性腳本請走「二、CLI 腳本規範」。

- I/O 操作用 `async/await`；**不要在 async 函式裡呼叫阻塞 I/O**（用 executor 包）
- 超時用 `asyncio.wait_for()`
- `asyncio.create_task()` 的回傳值要保存引用（防被 GC 提前回收）
- 優雅關閉：接 signal → 取消 task → await 收尾
- Windows 下 `subprocess` 需要 `CREATE_NEW_PROCESS_GROUP`（跨平台服務才需注意）
