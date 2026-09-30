# verify-methods.md — AC 驗證方法解析（ac_verify.py 的唯一規則來源）

| 優先 | 來源 | 方法 | 判定 |
|------|------|------|------|
| 1 | AC 文字 `verify: file` | 產出檔存在且非空 | exit 0 |
| 1 | `verify: import:<module>` | `python -c "import <module>"` | exit 0 |
| 1 | `verify: pytest:<path>` | `pytest <path> -q` | exit 0；並檢查測試檔含 `AC: <AC-ID>` 標記（缺則警告） |
| 1 | `verify: cmd:<shell>` | `sh -c "<shell>"` | exit 0 |
| 1 | `verify: manual` | — | pending，不算通過 |
| 2 | 產出檔在 tests/ 或 test_*.py | pytest 該檔 | 同上 |
| 3 | AC 含 import/載入 | import 由產出路徑推得的完整模組（src/a/b.py → src.a.b；PYTHONPATH 含 ws 與 ws/src） | exit 0 |
| 3 | AC 含 測試/test/pytest 且產出 .py | pytest 產出檔 | exit 0 |
| 3 | AC 含 檔案/存在/建立 | file 存在且非空 | — |
| 4 | 皆不命中 | manual → pending | **fail-closed：不猜、不算通過** |

寫 plan 時的建議：凡是能寫 `verify:` 就寫，讓驗收零歧義；plan_lint PL-006 會標出無法推斷的列。
