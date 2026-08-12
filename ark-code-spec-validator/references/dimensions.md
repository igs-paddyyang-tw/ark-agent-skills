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

### 評分（比例制 + drift 類型加權）

**公式**：

```
score = (1 - weighted_drift_ratio) × 100
weighted_drift_ratio = weighted_drift_count / total_endpoints
```

**drift 類型加權**：

| drift 類型 | 權重 | 理由 |
|-----------|------|------|
| `method_mismatch` | ×3 | 路徑存在但方法錯 → 最危險，可能導致 runtime error |
| `missing_in_code` | ×2 | spec 有但 code 沒實作 → 功能缺失 |
| `extra_in_code` | ×1 | code 有但 spec 沒記錄 → 文件欠更新，風險較低 |

**計算步驟**：

1. 統計 `total_endpoints`（spec 定義 + code 獨有端點的聯集）
2. 對每個 drift 依類型乘以權重，加總得 `weighted_drift_count`
3. `weighted_drift_ratio = weighted_drift_count / total_endpoints`
4. `score = max(0, (1 - weighted_drift_ratio) × 100)`

### 對照範例

#### 大專案（60 endpoints，drift 6）

| drift | 類型 | 權重 | 加權值 |
|-------|------|------|--------|
| PUT /api/users → spec 寫 PATCH | method_mismatch | ×3 | 3 |
| GET /api/reports | missing_in_code | ×2 | 2 |
| POST /api/export | missing_in_code | ×2 | 2 |
| GET /api/internal/debug | extra_in_code | ×1 | 1 |
| GET /api/internal/cache | extra_in_code | ×1 | 1 |
| DELETE /api/temp | extra_in_code | ×1 | 1 |

- weighted_drift_count = 3 + 2 + 2 + 1 + 1 + 1 = **10**
- weighted_drift_ratio = 10 / 60 = 0.167
- **score = (1 - 0.167) × 100 = 83.3**

#### 小專案（8 endpoints，drift 2）

| drift | 類型 | 權重 | 加權值 |
|-------|------|------|--------|
| POST /api/send → spec 寫 PUT | method_mismatch | ×3 | 3 |
| GET /api/stats | missing_in_code | ×2 | 2 |

- weighted_drift_count = 3 + 2 = **5**
- weighted_drift_ratio = 5 / 8 = 0.625
- **score = (1 - 0.625) × 100 = 37.5**

> 💡 同樣是「6 vs 2 個 drift」，比例制讓小專案獲得更嚴格的評判 — 這才合理，因為小專案的每個 drift 佔比更高。

### 忽略清單

預設忽略：`/healthz`、`/docs`、`/openapi.json`、`/redoc`

---

## Schema 驗證

> ⚠️ **Informational Only（v2 前不計入總分）**
> 目前只掃描 model 數量，尚無 spec 比對邏輯。此維度於報告中呈現但不影響 total score。

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

> 此分數**不計入總分**，僅供參考。v2 實裝比對後再正式納入。

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

### N/A 判定

> 若 design doc **未定義任何依賴規則**（即找不到「should not import」、「不應依賴」等模式），該維度判定為 **N/A**，不計入總分。權重依總分公式重分配給其餘維度。

判定流程：
1. 掃描 `docs/` 下所有 markdown 檔案
2. 搜尋依賴規則模式（`should not import`、`不應依賴`、`禁止引用`、`must not depend on` 等）
3. 若**零條規則** → N/A
4. 若有規則但**零違規** → 100 分（滿分，非 N/A）

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

---

## 總分公式

### 加權計算（三維度）

```
total = API × 0.5 + 依賴 × 0.2 + 測試覆蓋 × 0.3
```

| 維度 | 權重 | 理由 |
|------|------|------|
| API 端點 | 0.5 | 最直接反映 code ↔ spec 一致性 |
| 依賴 | 0.2 | 架構健康度，違規影響大但頻率低 |
| 測試覆蓋 | 0.3 | 驗收條件覆蓋率＝交付信心 |
| Schema | — | Informational，不計入 |

### N/A 處理

當某維度為 N/A（例：無 design doc 依賴規則 → 依賴維度 N/A），**權重重分配給其餘維度**，按原比例等比縮放：

```
有效權重_i = 原始權重_i / Σ(參與維度的原始權重)
```

### 計算範例

#### 範例 1：三維度皆有分數

| 維度 | 原始分數 | 權重 | 加權 |
|------|---------|------|------|
| API 端點 | 85 | 0.5 | 42.5 |
| 依賴 | 100 | 0.2 | 20.0 |
| 測試覆蓋 | 70 | 0.3 | 21.0 |
| **Total** | | **1.0** | **83.5** |

結論：⚠️ 83.5/100（建議回 spec-executor 修復測試缺口）

#### 範例 2：依賴為 N/A（無規則定義）

參與維度：API（0.5）+ 測試覆蓋（0.3）＝ 0.8

重分配權重：
- API：0.5 / 0.8 = **0.625**
- 測試覆蓋：0.3 / 0.8 = **0.375**

| 維度 | 原始分數 | 有效權重 | 加權 |
|------|---------|---------|------|
| API 端點 | 90 | 0.625 | 56.25 |
| 依賴 | N/A | — | — |
| 測試覆蓋 | 80 | 0.375 | 30.00 |
| **Total** | | **1.0** | **86.25** |

結論：⚠️ 86.25/100（兩項皆不錯但未達 90 門檻）

---

## Ignore 配置（.ark-validator.yaml）

### Schema

```yaml
# .ark-validator.yaml（放在專案根目錄）
ignore:
  endpoints:      # list[str] — "METHOD /path" 格式
    - "GET /health"
    - "GET /metrics"
    - "GET /internal/*"      # 支援尾部 wildcard

  modules:        # list[str] — glob 模式，匹配的檔案不參與依賴分析
    - "tests/*"
    - "scripts/*"
    - "migrations/*"

  dependencies:   # list[str] — 標籤名稱，跳過含此標籤的依賴規則
    - "dev-only"
    - "test-fixtures"
```

### 欄位行為

| 欄位 | 對應維度 | 效果 |
|------|---------|------|
| `ignore.endpoints` | API 端點 | 不計入 drift，也不計入 `total_endpoints` 分母 |
| `ignore.modules` | 依賴分析 | 不掃描這些路徑的 import 語句 |
| `ignore.dependencies` | 依賴分析 | 跳過 design doc 中標記此標籤的規則 |

### 注意事項

- 若 `.ark-validator.yaml` 不存在 → 全部掃描（預設行為）
- 若 YAML 格式錯誤 → 報錯並 fallback 到全部掃描
- 被忽略的項目在報告中以 `⏭️ ignored` 標示，保持可稽核性
- `endpoints` 中的 wildcard `*` 只能出現在路徑末尾（如 `GET /internal/*`）
