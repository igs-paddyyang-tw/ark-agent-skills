# 守門能力矩陣（各引擎 L1/L2/L3）

read-only 守門在各引擎的實際生效層不同。`meta.gate.read_only` 會回報實際生效層，
本表供 agent 判斷差異（尤其 MSSQL）。

| 引擎 | L1 allowlist | L2 引擎 read-only session | L3 伺服端判定 |
|------|:---:|---|:---:|
| BigQuery | ✅ | 無對應機制 | ✅ dry-run `statement_type == SELECT` |
| PostgreSQL | ✅ | ✅ `SET default_transaction_read_only = on` | — |
| MySQL | ✅ | ✅ `SET SESSION TRANSACTION READ ONLY` | — |
| SQLite | ✅ | ✅ `connect("file:…?mode=ro", uri=True)` | — |
| MSSQL | ✅ | ⚠️ 無 session 級 read-only；`IMPLICIT_TRANSACTIONS ON` + 結尾 `ROLLBACK` 兜底 | — |
| MongoDB | N/A（只暴露 find） | ✅ 不暴露任何寫 API | — |

## 三層語意

- **L1 allowlist**：語句首 keyword 必須 ∈ {SELECT, WITH, SHOW, DESCRIBE, DESC, EXPLAIN, PRAGMA}
  （剝除註解與字串常數後判定）。非讀關鍵字開頭、或語句內含寫入 keyword（CTE 尾巴寫入）→ 拒絕。
- **L2 引擎 read-only**：由資料庫本身拒絕寫入，與 SQL 文字無關。最強的一層（BQ 無此機制）。
- **L3 伺服端判定（僅 BQ）**：dry-run 回傳的 `statement_type`，伺服端解析、零費用、100% 準確。

`--allow-write` 一次解除 L1/L2/L3，沒有部分放行的中間態。ledger 稽核行記 `allow_write=true`。

## 🔴 MSSQL 的差異（必讀）

MSSQL 沒有 session 級 read-only。v3.0 的 L2 是**兜底**（隱式交易 + ROLLBACK），
不是真正的引擎拒絕。**需要強保證時，請使用唯讀帳號連線**（帳號權限層的 read-only）。
`meta.gate.read_only` 對 MSSQL 只會列 `L1`（+ ROLLBACK 兜底），不會宣稱 L2 真唯讀。
