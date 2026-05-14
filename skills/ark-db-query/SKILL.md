---
name: ark-db-query
description: |
  產出 db_query.py Skill，支援多種資料庫查詢並回傳標準格式（list[dict]），
  可直接串接 etl-pipeline 和 chart-generator。
  支援 SQLite、MongoDB、MSSQL、BigQuery、PostgreSQL、MySQL。
  使用此 Skill 當使用者提及資料庫查詢、SQL、db query、MongoDB、
  查詢資料表、資料庫連線、或任何需要從資料庫取得資料的場景。
---

# ark-db-query

產出 `src/skills/python_skills/db_query.py`，多資料庫查詢回傳標準格式，可獨立運作。

## 觸發條件

- 「資料庫查詢」、「SQL」、「db query」
- 「MongoDB」、「MSSQL」、「BigQuery」
- 「查詢資料表」、「資料庫連線」

## 支援的資料庫

| db_type | 資料庫 | 驅動套件 | 查詢方式 |
|---------|--------|---------|---------|
| sqlite | SQLite | 內建 | SQL |
| mongodb | MongoDB | pymongo | filter + projection |
| mssql | SQL Server | pymssql | SQL |
| bigquery | Google BigQuery | google-cloud-bigquery | SQL |
| postgresql | PostgreSQL | asyncpg | SQL |
| mysql | MySQL | aiomysql | SQL |

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `db_type` | `str` | ❌ | `"sqlite"` | 資料庫類型 |
| `db_path` | `str` | ✅ | — | 連線路徑（SQLite 檔案路徑 / MongoDB host:port/dbname / MSSQL host / BigQuery project_id） |
| `sql` | `str` | ⚠️ | — | SQL 查詢語句（SQL 類資料庫必要） |
| `collection` | `str` | ⚠️ | — | MongoDB collection 名稱 |
| `filter` | `dict` | ❌ | `{}` | MongoDB 查詢條件 |
| `projection` | `dict` | ❌ | `{}` | MongoDB 欄位投影 |
| `sort` | `list` | ❌ | `[]` | MongoDB 排序 |
| `limit` | `int` | ❌ | `50` | 回傳筆數上限 |
| `username` | `str` | ❌ | — | 認證帳號（MongoDB / MSSQL） |
| `password` | `str` | ❌ | — | 認證密碼 |
| `auth_source` | `str` | ❌ | `"admin"` | MongoDB authSource |
| `database` | `str` | ❌ | — | MSSQL / BigQuery 資料庫名稱 |

## 產出檔案

- `src/skills/python_skills/db_query.py`

---

## 產出指引

### 步驟 1：參數模型

```python
class DbQueryInput(SkillParam):
    """DB Query 輸入參數。"""
    db_type: str = Field(default="sqlite", description="sqlite/mongodb/mssql/bigquery/postgresql/mysql")
    db_path: str = Field(default="./data/app.db", description="連線路徑")
    sql: str = Field(default="", description="SQL 查詢語句")
    collection: str = Field(default="", description="MongoDB collection")
    filter: dict = Field(default_factory=dict, description="MongoDB 查詢條件")
    projection: dict = Field(default_factory=dict, description="MongoDB 欄位投影")
    sort: list = Field(default_factory=list, description="排序")
    limit: int = Field(default=50, description="回傳筆數上限")
    username: str = Field(default="", description="認證帳號")
    password: str = Field(default="", description="認證密碼")
    auth_source: str = Field(default="admin", description="MongoDB authSource")
    database: str = Field(default="", description="資料庫名稱")
```

### 步驟 2：Skill 類別

```python
class DbQuerySkill(BaseSkill):
    skill_id = "db_query"
    skill_type = SkillType.PYTHON
    description = "資料庫查詢：支援 SQLite / MongoDB / MSSQL / BigQuery"
    input_schema = DbQueryInput
```

### 步驟 3：路由到對應驅動

```python
async def execute(self, params: dict) -> SkillResult:
    db_type = params.get("db_type", "sqlite")
    try:
        if db_type == "mongodb":
            return await self._query_mongo(params)
        elif db_type == "mssql":
            return await self._query_mssql(params)
        elif db_type == "bigquery":
            return await self._query_bigquery(params)
        elif db_type == "postgresql":
            return await self._query_postgres(params)
        else:
            return await self._query_sqlite(params)
    except Exception as e:
        return SkillResult(success=False, error=f"Query failed: {e}")
```

### 步驟 4：各資料庫實作

#### SQLite（內建）

```python
async def _query_sqlite(self, params: dict) -> SkillResult:
    import sqlite3
    conn = sqlite3.connect(params["db_path"])
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(params["sql"])
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return SkillResult(success=True, data={"rows": rows, "count": len(rows)})
```

#### MongoDB（pymongo）

```python
async def _query_mongo(self, params: dict) -> SkillResult:
    from pymongo import MongoClient
    # 支援 host:port/dbname 格式或 mongodb:// URI
    client = MongoClient(host, port, username=..., password=..., authSource=...)
    coll = client[db_name][params["collection"]]
    cursor = coll.find(params["filter"], params["projection"]).sort(params["sort"]).limit(params["limit"])
    rows = [{**doc, "_id": str(doc["_id"])} for doc in cursor]
    return SkillResult(success=True, data={"rows": rows, "count": len(rows)})
```

#### MSSQL（pymssql）

```python
async def _query_mssql(self, params: dict) -> SkillResult:
    import pymssql
    conn = pymssql.connect(
        server=params["db_path"],
        user=params.get("username", ""),
        password=params.get("password", ""),
        database=params.get("database", ""),
    )
    cursor = conn.cursor(as_dict=True)
    cursor.execute(params["sql"])
    rows = cursor.fetchmany(params.get("limit", 50))
    conn.close()
    return SkillResult(success=True, data={"rows": rows, "count": len(rows)})
```

#### BigQuery（google-cloud-bigquery）

```python
async def _query_bigquery(self, params: dict) -> SkillResult:
    from google.cloud import bigquery
    client = bigquery.Client(project=params["db_path"])
    query_job = client.query(params["sql"])
    rows = [dict(row) for row in query_job.result()]
    return SkillResult(success=True, data={"rows": rows[:params.get("limit", 50)], "count": len(rows)})
```

---

## 輸出格式（統一）

所有資料庫回傳相同格式，可直接串接 etl-pipeline：

```json
{
  "success": true,
  "data": {
    "rows": [
      {"player_id": 93079334, "vip_level": 6, "ltv": {"total_spend": 186581}},
      {"player_id": 12345678, "vip_level": 5, "ltv": {"total_spend": 95000}}
    ],
    "count": 2
  }
}
```

## Workflow 串接範例

### MongoDB → ETL → 圖表

```yaml
- id: query_vip
  type: skill
  skill: db_query
  params:
    db_type: "mongodb"
    db_path: "${MONGO_HOST}/player_profile"
    username: "${MONGO_USER}"
    password: "${MONGO_PASS}"
    collection: "player_profiles"
    filter:
      vip_level:
        $gte: 5
    sort:
      - - "ltv.total_spend"
        - -1
    limit: 20
  output: vip_data
```

### MSSQL → ETL → 報表

```yaml
- id: query_revenue
  type: skill
  skill: db_query
  params:
    db_type: "mssql"
    db_path: "${MSSQL_HOST}"
    username: "${MSSQL_USER}"
    password: "${MSSQL_PASS}"
    database: "GameDB"
    sql: "SELECT TOP 100 player_id, SUM(amount) as total FROM deposits GROUP BY player_id ORDER BY total DESC"
  output: revenue_data
```

### BigQuery → ETL → Dashboard

```yaml
- id: query_bq
  type: skill
  skill: db_query
  params:
    db_type: "bigquery"
    db_path: "my-project-id"
    sql: "SELECT date, SUM(revenue) as daily_revenue FROM `dataset.daily_kpi` GROUP BY date ORDER BY date DESC LIMIT 30"
  output: bq_data
```

## 依賴套件

| db_type | 套件 | 安裝指令 |
|---------|------|---------|
| sqlite | 內建 | — |
| mongodb | pymongo | `pip install pymongo` |
| mssql | pymssql | `pip install pymssql` |
| bigquery | google-cloud-bigquery | `pip install google-cloud-bigquery` |
| postgresql | asyncpg | `pip install asyncpg` |
| mysql | aiomysql | `pip install aiomysql` |

## 注意事項

- 所有資料庫回傳統一 `{"rows": list[dict], "count": int}` 格式
- MongoDB 使用 filter/projection 而非 SQL
- MSSQL 使用 `pymssql`（支援 Windows 認證和 SQL 認證）
- BigQuery 需要 GCP 服務帳號金鑰（`GOOGLE_APPLICATION_CREDENTIALS` 環境變數）
- 使用參數化查詢防止 SQL injection
- `limit` 預設 50 筆，避免大量資料佔用記憶體
- 認證資訊建議放 `.env`，Workflow 中用 `${ENV_VAR}` 引用
