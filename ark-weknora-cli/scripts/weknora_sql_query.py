#!/usr/bin/env python3
"""weknora_sql_query.py — WeKnora 客戶端封裝（設計文件 D-2 / D-5 落地）。

包裝底層 chat 客戶端，提供兩種模式：

  sql-only  以 prompt 契約要求 WeKnora 回傳結構化 JSON（answer/sql/caliber/sources/confidence），
            本腳本負責 JSON 修復、契約驗證、read-only SQL 守門。SQL 交給 ark-db-query 執行，
            本腳本永不執行 BQ（D-1 / D-7）。
  direct    原樣轉送問題，回收敘事回答；檢查 KB citation，數字回答無 citation 即標低信任（D-5）。

底層路徑由 --endpoint 決定（預設 agent，維持已驗證口徑路由）：
  agent      → scripts/weknora_agent_chat.py（agent-chat，範圍跟 agent 配置）
  knowledge  → scripts/weknora_knowledge_chat.py（knowledge-chat，帶 --kb-id / WEKNORA_KB_ID）

用法：
  python weknora_sql_query.py --query "2026-08-30 營收多少" --mode sql-only
  python weknora_sql_query.py --query "..." --mode sql-only --endpoint knowledge --kb-id <uuid>
  python weknora_sql_query.py --query "為什麼上週營收下滑" --mode direct

環境變數：
  ARK_WEKNORA_CMD      覆蓋底層客戶端指令（覆蓋時 --endpoint 選擇失效）
  ARK_WEKNORA_TIMEOUT  底層呼叫逾時秒數（預設 180）

輸出（stdout，單一 JSON 物件）：
  { "mode", "ok", "answer", "sql", "caliber", "sources", "confidence",
    "session_id", "elapsed_ms", "flags": [...], "raw_answer" }

Exit code（deterministic 路由契約）：
  0  契約滿足，可信（sql-only: SQL 可用；direct: 有 citation 或非數字回答）
  2  降級：回傳無法解析 / 無 SQL / SQL 未過 read-only 守門 → 呼叫端回退 R-3 或人工
  3  低信任：數字回答無 KB citation → 必須以 ark-db-query 重驗（D-5）
  4  底層客戶端呼叫失敗（逾時 / 非零退出 / 外層 JSON 壞）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time

# ── 輸出一律 UTF-8（修 Windows terminal 亂碼）─────────────────────────────
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

EXIT_OK, EXIT_DEGRADE, EXIT_LOW_TRUST, EXIT_CLIENT_FAIL = 0, 2, 3, 4

# read-only 守門：只放行 SELECT / WITH 開頭，且全文不得含 DML/DDL 關鍵詞
SQL_ALLOW_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
SQL_DENY_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
KB_CITE_RE = re.compile(r"<kb\s[^>]*chunk_id=", re.IGNORECASE)
HAS_NUMBER_RE = re.compile(r"\d")

SQL_ONLY_PROMPT = """你是資料口徑助理。針對下列問題，只回傳一個 JSON 物件，不要任何其他文字、
不要 markdown 圍欄。JSON 欄位：
  "answer": 一句話中文結論（含關鍵數字，若可得）
  "sql": 可直接在 BigQuery 執行的唯讀 SELECT 語句（口徑正確；無法給 SQL 則填空字串）
  "caliber": 口徑說明（表、欄位、filter、注意事項）
  "sources": 引用的知識庫文件清單（例 ["GameConsume.md#chunk"]；無引用填 []）
  "confidence": "high" | "medium" | "low"

問題：{query}"""


def default_cmd(endpoint: str = "agent") -> str:
    """依 endpoint 選底層客戶端腳本。

    agent     → scripts/weknora_agent_chat.py（agent-chat，範圍跟 agent 配置）
    knowledge → scripts/weknora_knowledge_chat.py（knowledge-chat，帶 kb_ids）
    ARK_WEKNORA_CMD 可整體覆蓋（覆蓋時 endpoint 選擇失效，由該指令自行決定）。
    """
    py = "py" if os.name == "nt" else "python"
    script = "weknora_agent_chat.py" if endpoint == "agent" else "weknora_knowledge_chat.py"
    return f"{py} scripts/{script}"


def call_client(query: str, session_id: str | None, timeout: int,
                endpoint: str = "agent", kb_ids: list[str] | None = None) -> tuple[dict, int]:
    """呼叫底層 chat 客戶端，回傳（外層 JSON, elapsed_ms）。失敗 raise RuntimeError。"""
    cmd_str = os.environ.get("ARK_WEKNORA_CMD") or default_cmd(endpoint)
    cmd = shlex.split(cmd_str, posix=(os.name != "nt"))
    cmd += ["--query", query]
    cmd += ["--session-id", session_id] if session_id else ["--new-session"]
    # knowledge endpoint 需帶 kb_ids（未帶則底層回退 WEKNORA_KB_ID）
    if endpoint == "knowledge":
        for k in (kb_ids or []):
            cmd += ["--kb-id", k]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"weknora client timeout after {timeout}s")
    except FileNotFoundError as e:
        raise RuntimeError(f"weknora client not found: {e}")
    elapsed = int((time.time() - t0) * 1000)
    if proc.returncode != 0:
        raise RuntimeError(f"weknora client exit {proc.returncode}: {(proc.stderr or proc.stdout)[:400]}")
    outer = extract_json(proc.stdout)
    if outer is None:
        raise RuntimeError(f"cannot parse client output: {proc.stdout[:400]}")
    return outer, elapsed


def extract_json(text: str):
    """JSON 修復：去圍欄 → 直接 parse → 取第一段平衡大括號再 parse。失敗回 None。"""
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return None


def sql_gate(sql: str) -> str | None:
    """回傳 None = 通過；否則回傳拒絕原因。"""
    if not sql or not sql.strip():
        return "empty sql"
    if not SQL_ALLOW_RE.match(sql):
        return "sql must start with SELECT/WITH"
    if SQL_DENY_RE.search(sql):
        return "sql contains DML/DDL keyword"
    return None


def run(args) -> int:
    result = {
        "mode": args.mode, "ok": False, "answer": "", "sql": "", "caliber": "",
        "sources": [], "confidence": "", "session_id": "", "elapsed_ms": 0,
        "flags": [], "raw_answer": "",
    }
    query = SQL_ONLY_PROMPT.format(query=args.query) if args.mode == "sql-only" else args.query

    try:
        outer, elapsed = call_client(query, args.session_id, args.timeout,
                                     endpoint=args.endpoint, kb_ids=args.kb_id)
    except RuntimeError as e:
        result["flags"].append(f"client_fail: {e}")
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_CLIENT_FAIL

    data = outer.get("data") or {}
    raw_answer = str(data.get("answer", ""))
    result.update(
        session_id=data.get("session_id", ""),
        elapsed_ms=(outer.get("meta") or {}).get("elapsed_ms", elapsed),
        raw_answer=raw_answer,
    )
    if not outer.get("success", False):
        result["flags"].append("client_reported_failure")
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_CLIENT_FAIL

    has_citation = bool(KB_CITE_RE.search(raw_answer))
    if has_citation:
        result["flags"].append("kb_citation_present")

    if args.mode == "direct":
        result["answer"] = raw_answer
        if HAS_NUMBER_RE.search(raw_answer) and not has_citation:
            result["flags"].append("numeric_without_citation_must_reverify")  # D-5
            print(json.dumps(result, ensure_ascii=False))
            return EXIT_LOW_TRUST
        result["ok"] = True
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK

    # sql-only：解析內層 JSON 契約
    inner = extract_json(raw_answer)
    if inner is None:
        result["flags"].append("inner_json_unparseable")
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_DEGRADE

    result["answer"] = str(inner.get("answer", ""))
    result["sql"] = str(inner.get("sql", "")).strip()
    result["caliber"] = str(inner.get("caliber", ""))
    src = inner.get("sources")
    result["sources"] = src if isinstance(src, list) else ([src] if src else [])
    conf = str(inner.get("confidence", "")).lower()
    result["confidence"] = conf if conf in ("high", "medium", "low") else "low"

    reason = sql_gate(result["sql"])
    if reason:
        result["flags"].append(f"sql_gate_reject: {reason}")
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_DEGRADE

    if not result["sources"] and not has_citation:
        result["flags"].append("no_sources_must_reverify")  # D-5：無引用一律重驗
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_LOW_TRUST

    result["ok"] = True
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True)
    p.add_argument("--mode", choices=["sql-only", "direct"], default="sql-only")
    p.add_argument("--endpoint", choices=["agent", "knowledge"], default="agent",
                   help="底層問答路徑：agent（agent-chat，預設，維持已驗證口徑路由）"
                        " / knowledge（knowledge-chat，查自建 KB，需 --kb-id 或 WEKNORA_KB_ID）")
    p.add_argument("--kb-id", action="append", default=[],
                   help="endpoint=knowledge 時的知識庫（UUID，可多個）；未帶回退 WEKNORA_KB_ID")
    p.add_argument("--session-id", default=None)
    p.add_argument("--timeout", type=int, default=int(os.environ.get("ARK_WEKNORA_TIMEOUT", "180")))
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())
