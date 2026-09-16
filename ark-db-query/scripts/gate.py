"""L1 read-only 守門 — allowlist + 註解剝除（ADR-001 第一層）。

v2.0 的問題（F-01/F-02）：denylist 正則只錨語句開頭，前置註解、巢狀/腳本寫入
都能繞過。v3.0 改為 **allowlist**：剝除註解與字串常數後，每個語句的首 keyword
必須 ∈ 讀白名單，否則拒絕（封閉集合，預設拒絕）。

- 剝註解：自寫狀態機處理 `--` 行註解、`/* */` 區塊註解、字串常數內的分號/註解符
  （不引入 sqlparse，規則封閉可測）
- allowlist：SELECT / WITH / SHOW / DESCRIBE / DESC / EXPLAIN / PRAGMA（讀態子集）
- 兜底：即使首 token 合法（如 WITH … CTE），語句內若含寫入 keyword（DELETE/UPDATE/
  INSERT/DROP/CREATE/ALTER/TRUNCATE/MERGE/REPLACE/CALL/EXEC/EXECUTE/COPY/LOAD/GRANT/
  REVOKE/VACUUM/ATTACH/DETACH/REINDEX/INTO）→ 拒絕。這攔下 `WITH x AS(..) DELETE`。

`gate_explain(sql)` 回傳 (allowed, layer, reason, token) 供 --gate-explain。
"""
from __future__ import annotations

import re

# 讀查詢 allowlist（語句首 keyword）
READ_KEYWORDS = frozenset({
    "SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "PRAGMA",
})

# 寫入 / 危險 keyword（出現在任何位置即拒絕，兜底 CTE 尾巴寫入等）
WRITE_KEYWORDS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "MERGE", "REPLACE", "CALL", "EXEC", "EXECUTE", "COPY", "LOAD", "GRANT",
    "REVOKE", "VACUUM", "ATTACH", "DETACH", "REINDEX", "INTO", "UPSERT",
})

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def strip_comments(sql: str) -> str:
    """剝除 SQL 註解與字串常數（字串以空白取代，保留分號結構）。

    狀態機：normal / line-comment(--) / block-comment(/* */) / single-quote / double-quote。
    字串常數整段以空白取代，避免字串內的分號/關鍵字/註解符誤判。
    """
    out: list[str] = []
    i, n = 0, len(sql)
    state = "normal"
    while i < n:
        c = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if state == "normal":
            if c == "-" and nxt == "-":
                state = "line"; i += 2; continue
            if c == "/" and nxt == "*":
                state = "block"; i += 2; continue
            if c == "'":
                state = "sq"; out.append(" "); i += 1; continue
            if c == '"':
                state = "dq"; out.append(" "); i += 1; continue
            out.append(c); i += 1; continue
        if state == "line":
            if c == "\n":
                state = "normal"; out.append("\n")
            i += 1; continue
        if state == "block":
            if c == "*" and nxt == "/":
                state = "normal"; i += 2; continue
            i += 1; continue
        if state == "sq":
            if c == "'" and nxt == "'":     # escaped ''
                i += 2; continue
            if c == "'":
                state = "normal"
            i += 1; continue
        if state == "dq":
            if c == '"' and nxt == '"':
                i += 2; continue
            if c == '"':
                state = "normal"
            i += 1; continue
    return "".join(out)


def _statements(clean: str) -> list[str]:
    return [s.strip() for s in clean.split(";") if s.strip()]


def gate_explain(sql: str) -> tuple[bool, str, str, str]:
    """回傳 (allowed, layer, reason, token)。layer 恆為 'L1'（本模組）。"""
    clean = strip_comments(sql)
    stmts = _statements(clean)
    if not stmts:
        return False, "L1", "剝除註解後無有效語句", ""
    for stmt in stmts:
        m = _TOKEN_RE.search(stmt)
        first = m.group(0).upper() if m else ""
        if first not in READ_KEYWORDS:
            return False, "L1", f"語句首 keyword 不在讀白名單: {first or '(空)'}", first
        # PRAGMA 只放行唯讀查詢型；帶 '=' 的賦值型（如 PRAGMA writable_schema = ON）是寫入態
        if first == "PRAGMA" and "=" in stmt:
            return False, "L1", "PRAGMA 賦值型（寫入態）不放行，僅允許唯讀 PRAGMA 查詢", "PRAGMA"
        # 兜底：讀關鍵字開頭但語句內含寫入 keyword（CTE 尾巴寫入等）
        for tok in _TOKEN_RE.findall(stmt.upper()):
            if tok in WRITE_KEYWORDS:
                return False, "L1", f"語句含寫入 keyword: {tok}", tok
    return True, "L1", "首 keyword 皆為讀查詢，且無寫入 keyword", ""


def check(sql: str, allow_write: bool) -> tuple[bool, str, str, str]:
    """守門主入口。allow_write=True 一次解除。回傳 gate_explain 同型。"""
    if allow_write:
        return True, "L1", "allow_write 明示放行", ""
    return gate_explain(sql)
