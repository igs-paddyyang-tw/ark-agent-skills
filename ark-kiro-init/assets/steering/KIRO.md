---
inclusion: always
---

# Kiro CLI 運作規範

---

## 一、核心運作關係（系統提詞 + Skill + 知識庫）

Kiro CLI 的三個核心元素：

```
.kiro/steering/SOUL.md    → 你是誰、怎麼說話、什麼態度
.kiro/skills/*/SKILL.md   → 你會做什麼、怎麼做、產出什麼
knowledge/                → 你知道什麼、從哪裡查、往哪裡寫
```

### 知識庫三層架構

查詢知識時，依以下優先順序搜尋：

1. **私有知識**：`knowledge/raw/` 和 `knowledge/wiki/`（你自己的記憶）
2. **共用知識**：`../../knowledge/shared/wiki/`（所有 Agent 共用的通用知識）
3. **專案知識**：`../../knowledge/{project}/wiki/`（特定專案知識，如 hoyeah/）

> 路徑說明：Agent 的 cwd 在 `agents/{name}-agent/`，全域知識庫在根目錄 `knowledge/`，
> 所以要用 `../../knowledge/` 往上跳兩層存取。

### 知識庫寫入規則

- 寫入新記憶 → `knowledge/raw/`（私有，只有你自己查得到）
- 引用知識時 → 標註來源層級：`[私有]`、`[共用]`、`[專案名]`
- `knowledge/raw/` 是唯讀區（AI 只往裡寫，不修改已有檔案）
- `knowledge/wiki/` 由 ingest 工具產生（AI 不直接寫 wiki/）

### 知識庫目錄結構

```
根目錄/
├── knowledge/
│   ├── shared/wiki/        ← 全 Agent 共用知識
│   └── {project}/wiki/     ← 專案專屬知識
│
└── agents/{name}-agent/    ← Kiro CLI 的 cwd
    └── knowledge/
        ├── raw/            ← 私有記憶（寫入處）
        └── wiki/           ← 私有知識頁面
```

---

## 二、Python 程式碼規範

> 讀寫 `src/` 下的 .py 檔案時遵守。

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

## 三、避坑注意事項

- 不要在 async 函式中呼叫阻塞 I/O
- YAML 用 `yaml.safe_load()`
- 路徑用 `Path` 物件
- 外部輸入要驗證
- Token 不要出現在日誌中
- Windows subprocess 需要 `CREATE_NEW_PROCESS_GROUP`
- 檔案讀寫加 `encoding="utf-8"`
- **知識庫路徑**：全域知識用 `../../knowledge/shared/` 或 `../../knowledge/{project}/`，不要假設 cwd 在根目錄
- **frontmatter 跳過**：搜尋 wiki 內容時，先跳過 `---` 之間的 frontmatter 再搜正文

---

## 四、Context Compaction 策略（觸發: 85%）

- **保留**：當前未完成任務、最近 3 輪對話、知識庫查詢結果
- **丟棄**：已完成的操作 log、重複系統訊息、舊 tool output
- **持久化**：重要摘要寫入 `knowledge/raw/`
