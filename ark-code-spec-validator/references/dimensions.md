# 驗證維度詳細說明

## 目錄

1. [API 端點驗證](#api-端點驗證)
2. [Schema 驗證](#schema-驗證)
3. [依賴分析](#依賴分析)
4. [測試覆蓋](#測試覆蓋)

---

## API 端點驗證

### 原理

掃描 Python 原始碼中的 FastAPI route 定義（`@app.get`、`app.post` 等），與 docs/ 下 markdown 文件中的 API 表格比對。

### 掃描模式

```python
# 匹配 decorator 模式
@app.get("/api/status")

# 匹配 inline 模式（class method 內）
app.post("/api/send")
```

### Spec 解析模式

```markdown
<!-- 表格格式 -->
| `/api/status` | GET | 說明 |
| GET | /api/status | 說明 |

<!-- 行內格式 -->
GET /api/status — 說明
```

### 評分

- 每個 drift 扣 5 分（100 - drifts × 5，最低 0）
- drift 類型：missing_in_code / extra_in_code / method_mismatch

### 忽略清單

預設忽略：`/healthz`、`/docs`、`/openapi.json`、`/redoc`

---

## Schema 驗證

### 原理

掃描 Pydantic `BaseModel` 和 `@dataclass` 定義，提取欄位名稱、型別、是否必填。

### 掃描模式

```python
class SendRequest(BaseModel):
    instance: str
    message: str
    source: str | None = None

@dataclass
class InstanceConfig:
    name: str = ""
    working_directory: str = ""
```

### 產出

```json
{
  "name": "SendRequest",
  "kind": "pydantic",
  "fields": [
    {"name": "instance", "type": "str", "required": true},
    {"name": "message", "type": "str", "required": true},
    {"name": "source", "type": "str | None", "required": false}
  ]
}
```

### 評分（v2 規劃）

目前只掃描 model 數量。v2 將比對 spec 中的 request/response 定義。

---

## 依賴分析

### 原理

掃描 Python `from X import Y` 和 `import X` 語句，建構模組依賴圖。然後比對 design doc 中的依賴規則。

### 規則格式（design doc 中）

```markdown
telegram.py should not import cost_guard.py
process.py 不應依賴 telegram
```

### 評分

- 每個違規扣 20 分（100 - violations × 20，最低 0）
- 無規則定義時預設 100 分

---

## 測試覆蓋

### 原理

1. 從 `tests/test_*.py` 提取所有 `test_` 函式名 + docstring
2. 從 `docs/` 的「驗收」章節提取 checkbox 條件
3. 用 keyword matching 比對覆蓋率

### 匹配邏輯

- 從驗收條件提取關鍵字（去除停用詞）
- 如果 test 名稱/docstring 包含 ≥2 個關鍵字 → 視為覆蓋

### 評分

- `covered / total × 100`
- 無驗收條件時預設 100 分
