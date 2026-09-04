#!/usr/bin/env python3
"""metric_registry.py — 指標口徑快取（設計文件 D-3 落地）。

registry 是一個 JSON 檔（預設 registry/metrics.json，可用 ARK_WEKNORA_REGISTRY 覆蓋），
記錄「指標 → 表 + SQL 模板 + 口徑 + 注意事項」。條目生命週期對齊 wiki 兩層信任模型：
seedling（LLM 蒸餾、未人審）→ mature（人審通過，promote 指令晉升）。

子指令：
  lookup   --query "..." [--date YYYY-MM-DD]   以 alias 比對問句；命中則輸出條目與渲染後 SQL
  add      --from-json <file|->                從 weknora_sql_query.py 的輸出建 seedling 條目
           [--metric-id id --aliases a,b,c]    （SQL 中的日期字面值自動模板化為 {date}）
  list                                          列出全部條目（id / status / aliases）
  promote  --id <metric-id>                     seedling → mature（人審後執行）
  render   --id <metric-id> --date YYYY-MM-DD  渲染指定條目的 SQL

Exit code：0 成功（lookup 命中）；1 lookup miss / 條目不存在；2 輸入或檔案錯誤。
輸出一律 JSON（stdout）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

DATE_LITERAL_RE = re.compile(r"(['\"])(\d{4}-\d{2}-\d{2})\1")


def registry_path() -> Path:
    return Path(os.environ.get("ARK_WEKNORA_REGISTRY", "registry/metrics.json"))


def load() -> dict:
    p = registry_path()
    if not p.exists():
        return {"version": 1, "metrics": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"error": f"registry unreadable: {e}", "path": str(p)}, ensure_ascii=False))
        sys.exit(2)


def save(reg: dict) -> None:
    p = registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def templatize(sql: str) -> str:
    """把 SQL 中的 'YYYY-MM-DD' 字面值換成 '{date}' 佔位符（保留原引號）。"""
    return DATE_LITERAL_RE.sub(lambda m: f"{m.group(1)}{{date}}{m.group(1)}", sql)


def render(entry: dict, day: str | None) -> str | None:
    tpl = entry.get("sql_template", "")
    if "{date}" in tpl and not day:
        return None
    return tpl.replace("{date}", day) if day else tpl


def cmd_lookup(args) -> int:
    reg = load()
    q = args.query
    for entry in reg["metrics"]:
        for alias in [entry.get("name", "")] + entry.get("aliases", []):
            if alias and alias in q:
                sql = render(entry, args.date)
                out = {"hit": True, "matched_alias": alias, "entry": entry, "sql": sql}
                if sql is None:
                    out["note"] = "sql_template 需要 --date"
                print(json.dumps(out, ensure_ascii=False))
                return 0
    print(json.dumps({"hit": False}, ensure_ascii=False))
    return 1


def cmd_add(args) -> int:
    raw = sys.stdin.read() if args.from_json == "-" else Path(args.from_json).read_text(encoding="utf-8")
    try:
        src = json.loads(raw)
    except Exception as e:
        print(json.dumps({"error": f"bad input json: {e}"}, ensure_ascii=False))
        return 2
    sql = (src.get("sql") or "").strip()
    if not sql:
        print(json.dumps({"error": "input has no sql; refuse to add empty entry"}, ensure_ascii=False))
        return 2
    metric_id = args.metric_id or f"metric-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    reg = load()
    if any(m.get("id") == metric_id for m in reg["metrics"]):
        print(json.dumps({"error": f"id already exists: {metric_id}"}, ensure_ascii=False))
        return 2
    entry = {
        "id": metric_id,
        "name": args.name or metric_id,
        "aliases": [a.strip() for a in (args.aliases or "").split(",") if a.strip()],
        "sql_template": templatize(sql),
        "caliber": src.get("caliber", ""),
        "sources": src.get("sources", []),
        "status": "seedling",  # 未人審一律 seedling（wiki 兩層信任模型）
        "origin": "weknora-sql-only",
        "added": date.today().isoformat(),
        "last_verified": None,
    }
    reg["metrics"].append(entry)
    save(reg)
    print(json.dumps({"added": entry, "registry": str(registry_path())}, ensure_ascii=False))
    return 0


def cmd_list(_args) -> int:
    reg = load()
    rows = [{"id": m["id"], "name": m.get("name", ""), "status": m.get("status", ""),
             "aliases": m.get("aliases", [])} for m in reg["metrics"]]
    print(json.dumps({"count": len(rows), "metrics": rows}, ensure_ascii=False))
    return 0


def cmd_promote(args) -> int:
    reg = load()
    for m in reg["metrics"]:
        if m.get("id") == args.id:
            m["status"] = "mature"
            m["last_verified"] = date.today().isoformat()
            save(reg)
            print(json.dumps({"promoted": m}, ensure_ascii=False))
            return 0
    print(json.dumps({"error": f"id not found: {args.id}"}, ensure_ascii=False))
    return 1


def cmd_render(args) -> int:
    reg = load()
    for m in reg["metrics"]:
        if m.get("id") == args.id:
            sql = render(m, args.date)
            if sql is None:
                print(json.dumps({"error": "sql_template 需要 --date"}, ensure_ascii=False))
                return 2
            print(json.dumps({"id": args.id, "sql": sql, "caliber": m.get("caliber", "")}, ensure_ascii=False))
            return 0
    print(json.dumps({"error": f"id not found: {args.id}"}, ensure_ascii=False))
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    lk = sub.add_parser("lookup"); lk.add_argument("--query", required=True); lk.add_argument("--date")
    ad = sub.add_parser("add"); ad.add_argument("--from-json", required=True)
    ad.add_argument("--metric-id"); ad.add_argument("--name"); ad.add_argument("--aliases")
    sub.add_parser("list")
    pr = sub.add_parser("promote"); pr.add_argument("--id", required=True)
    rd = sub.add_parser("render"); rd.add_argument("--id", required=True); rd.add_argument("--date")

    args = p.parse_args()
    return {"lookup": cmd_lookup, "add": cmd_add, "list": cmd_list,
            "promote": cmd_promote, "render": cmd_render}[args.cmd](args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
