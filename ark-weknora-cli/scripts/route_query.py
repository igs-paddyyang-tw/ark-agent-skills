#!/usr/bin/env python3
"""route_query.py — 三層 escalation 路由（設計文件 D-4 / D-7 落地）。

輸入一個自然語言問題，輸出「路由決策 JSON」。本腳本永不執行 BigQuery ——
decision.action 告訴呼叫端（agent）下一步做什麼：

  execute_with_ark_db_query   拿 decision.sql 交給 ark-db-query 執行（R-1 / R-2）
  accept_answer               直接採用 decision.answer（R-3，且信任檢查通過）
  reverify_with_ark_db_query  數字回答無 citation，必須重驗（D-5）
  fallback_manual             全部路徑失敗，人工介入

路由順序：
  R-1  registry 命中（metric_registry.py lookup）→ 本地渲染 SQL，零 LLM
  R-2  KPI 型問句但 registry miss → weknora_sql_query.py --mode sql-only
       成功時可用 --auto-registry 自動落一筆 seedling 條目
  R-3  探索式問句 / R-2 降級 → weknora_sql_query.py --mode direct

KPI 分類為 deterministic 規則：問句含指標關鍵詞（內建 + ARK_WEKNORA_KPI_WORDS 擴充，
逗號分隔）且含日期訊號（YYYY-MM-DD / 昨日 / 今日 / 本週 / 上週 / 本月 / 上月）。
uncertain 一律落 R-3（escalation 哲學：不確定走便宜路徑）。

環境變數：
  ARK_WEKNORA_ROUTER_ENABLED  預設 1；設 0 時輸出 {route:"disabled"}，行為與未導入前一致
  ARK_WEKNORA_TELEMETRY       telemetry JSONL 路徑（預設 logs/weknora_telemetry.jsonl）
  ARK_WEKNORA_KPI_WORDS       追加 KPI 關鍵詞（逗號分隔）
  ARK_WEKNORA_REGISTRY / ARK_WEKNORA_CMD / ARK_WEKNORA_TIMEOUT  傳遞給下層腳本

用法：
  python route_query.py --query "2026-08-30 昨日營收是多少 USD"
  python route_query.py --query "為什麼上週營收下滑" 
  python route_query.py --query "..." --date 2026-08-30 --auto-registry

Exit code：0 有可執行決策（execute/accept）；3 需重驗；2 fallback_manual；5 router disabled。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
DEFAULT_KPI_WORDS = [
    "營收", "儲值", "收入", "流水", "付費", "課金", "ARPU", "ARPPU",
    "DAU", "MAU", "留存", "轉換率", "交易", "提領", "revenue",
]
DATE_TOKEN_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
REL_DATE_WORDS = ["昨日", "昨天", "今日", "今天", "本週", "上週", "本周", "上周", "本月", "上月"]
# 探索式/歸因式問句：優先於 R-1/R-2，直落 R-3（要的是敘事解釋，不是一個數字）
EXPLORATORY_RE = re.compile(r"(為什麼|為何|原因|歸因|怎麼會|怎麼回事|解釋|分析一下|診斷)")


def kpi_words() -> list[str]:
    extra = [w.strip() for w in os.environ.get("ARK_WEKNORA_KPI_WORDS", "").split(",") if w.strip()]
    return DEFAULT_KPI_WORDS + extra


def resolve_date(query: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    m = DATE_TOKEN_RE.search(query)
    if m:
        return m.group(0)
    if "昨日" in query or "昨天" in query:
        return (date.today() - timedelta(days=1)).isoformat()
    if "今日" in query or "今天" in query:
        return date.today().isoformat()
    return None


def is_kpi_query(query: str) -> bool:
    has_metric = any(w.lower() in query.lower() for w in kpi_words())
    has_date = bool(DATE_TOKEN_RE.search(query)) or any(w in query for w in REL_DATE_WORDS)
    return has_metric and has_date


def run_py(script: str, argv: list[str], stdin_text: str | None = None) -> tuple[int, dict]:
    """呼叫同目錄腳本，回傳 (exit_code, parsed_json_or_empty)。"""
    cmd = [sys.executable, str(HERE / script)] + argv
    proc = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace",
                          input=stdin_text)
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except Exception:
        payload = {"_unparsed_stdout": proc.stdout[:400]}
    return proc.returncode, payload


def telemetry(record: dict) -> None:
    path = Path(os.environ.get("ARK_WEKNORA_TELEMETRY", "logs/weknora_telemetry.jsonl"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # telemetry 是 best-effort，不影響主流程


def emit(decision: dict, exit_code: int, t0: float, query: str) -> int:
    decision["elapsed_ms"] = int((time.time() - t0) * 1000)
    telemetry({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "query": query,
        "route": decision.get("route"), "action": decision.get("action"),
        "elapsed_ms": decision["elapsed_ms"], "flags": decision.get("flags", []),
        "exit": exit_code,
    })
    print(json.dumps(decision, ensure_ascii=False))
    return exit_code


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True)
    p.add_argument("--date", help="覆蓋日期解析（YYYY-MM-DD）")
    p.add_argument("--auto-registry", action="store_true",
                   help="R-2 成功時自動把口徑落成 seedling 條目")
    p.add_argument("--session-id", default=None)
    args = p.parse_args()
    t0 = time.time()

    if os.environ.get("ARK_WEKNORA_ROUTER_ENABLED", "1") == "0":
        print(json.dumps({"route": "disabled", "action": "fallback_manual",
                          "note": "ARK_WEKNORA_ROUTER_ENABLED=0"}, ensure_ascii=False))
        return 5

    day = resolve_date(args.query, args.date)
    exploratory = bool(EXPLORATORY_RE.search(args.query))

    # ── R-1：registry 命中（探索式問句跳過，直落 R-3）────────────────────
    lk_argv = ["lookup", "--query", args.query] + (["--date", day] if day else [])
    code, hit = (1, {}) if exploratory else run_py("metric_registry.py", lk_argv)
    if code == 0 and hit.get("hit") and hit.get("sql"):
        entry = hit.get("entry", {})
        return emit({
            "route": "R-1", "action": "execute_with_ark_db_query",
            "sql": hit["sql"], "caliber": entry.get("caliber", ""),
            "registry_id": entry.get("id"), "registry_status": entry.get("status"),
            "flags": ["registry_hit"],
        }, 0, t0, args.query)

    # ── R-2：KPI 型問句 → WeKnora sql-only（探索式問句跳過）──────────────
    if not exploratory and is_kpi_query(args.query):
        sq_argv = ["--query", args.query, "--mode", "sql-only"]
        if args.session_id:
            sq_argv += ["--session-id", args.session_id]
        code, res = run_py("weknora_sql_query.py", sq_argv)
        if code == 0 and res.get("sql"):
            decision = {
                "route": "R-2", "action": "execute_with_ark_db_query",
                "sql": res["sql"], "caliber": res.get("caliber", ""),
                "answer_from_weknora": res.get("answer", ""),
                "sources": res.get("sources", []), "session_id": res.get("session_id", ""),
                "flags": res.get("flags", []),
            }
            if args.auto_registry:
                add_code, added = run_py(
                    "metric_registry.py",
                    ["add", "--from-json", "-", "--aliases", ""],
                    stdin_text=json.dumps(res, ensure_ascii=False),
                )
                decision["registry_seedling"] = added.get("added", {}).get("id") if add_code == 0 else None
                decision["flags"].append("registry_seedling_added" if add_code == 0 else "registry_add_failed")
            return emit(decision, 0, t0, args.query)
        if code == 3:
            return emit({
                "route": "R-2", "action": "reverify_with_ark_db_query",
                "sql": res.get("sql", ""), "caliber": res.get("caliber", ""),
                "answer_from_weknora": res.get("answer", ""), "flags": res.get("flags", []),
            }, 3, t0, args.query)
        # code 2/4 → 降級 R-3，繼續往下

    # ── R-3：探索直連 ─────────────────────────────────────────────────────
    dr_argv = ["--query", args.query, "--mode", "direct"]
    if args.session_id:
        dr_argv += ["--session-id", args.session_id]
    code, res = run_py("weknora_sql_query.py", dr_argv)
    if code == 0:
        return emit({
            "route": "R-3", "action": "accept_answer",
            "answer": res.get("answer", ""), "session_id": res.get("session_id", ""),
            "flags": res.get("flags", []),
        }, 0, t0, args.query)
    if code == 3:
        return emit({
            "route": "R-3", "action": "reverify_with_ark_db_query",
            "answer": res.get("answer", ""), "flags": res.get("flags", []),
        }, 3, t0, args.query)
    return emit({
        "route": "R-3", "action": "fallback_manual",
        "flags": res.get("flags", ["client_fail"]),
    }, 2, t0, args.query)


if __name__ == "__main__":
    sys.exit(main())
