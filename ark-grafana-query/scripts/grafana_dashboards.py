#!/usr/bin/env python3
"""Grafana Dashboard / Panel 列表 CLI。

子指令：
  list                         列出所有 Dashboard
  panels  --uid DASHBOARD_UID  列出某 Dashboard 的所有 Panel

用法:
  python grafana_dashboards.py list
  python grafana_dashboards.py panels --uid "abc123"
認證: GRAFANA_URL + GRAFANA_TOKEN 或 GRAFANA_USER + GRAFANA_PASSWORD
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafana_common as C  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Grafana dashboards & panels")
    ap.add_argument("command", choices=["list", "panels"])
    ap.add_argument("--uid", help="Dashboard UID（panels 指令用）")
    ap.add_argument("--folder", help="篩選 folder（list 指令用）")
    ap.add_argument("--out", help="結果落盤路徑")
    ap.add_argument("--out-format", choices=["json", "jsonl"], default="json")
    ap.add_argument("--max-stdout-rows", type=int, default=C.DEFAULT_STDOUT_ROWS)
    ap.add_argument("--timeout", type=int, default=C.DEFAULT_TIMEOUT)
    return ap


def cmd_list(args: argparse.Namespace) -> list[dict]:
    """列出所有 Dashboard。"""
    params: dict = {"type": "dash-db", "limit": 1000}
    if args.folder:
        params["folderIds"] = args.folder

    results = C.grafana_get("/api/search", params=params, timeout=args.timeout)

    rows = []
    for d in results:
        rows.append({
            "uid": d.get("uid", ""),
            "title": d.get("title", ""),
            "folder": d.get("folderTitle", "General"),
            "url": d.get("url", ""),
            "tags": d.get("tags", []),
        })
    return rows


def cmd_panels(args: argparse.Namespace) -> list[dict]:
    """列出某 Dashboard 的所有 Panel。"""
    if not args.uid:
        C.fail("BAD_INPUT", "panels 需要 --uid", "先用 list 查 dashboard uid")

    dashboard = C.grafana_get(f"/api/dashboards/uid/{args.uid}", timeout=args.timeout)
    panels_raw = dashboard.get("dashboard", {}).get("panels", [])

    rows = []
    for p in panels_raw:
        # 處理 row type（包含巢狀 panels）
        if p.get("type") == "row":
            for nested in p.get("panels", []):
                rows.append(_panel_to_row(nested, args.uid))
        else:
            rows.append(_panel_to_row(p, args.uid))
    return rows


def _panel_to_row(p: dict, dashboard_uid: str) -> dict:
    """將 panel JSON 轉為標準 row。"""
    targets = p.get("targets", [])
    expr = ""
    if targets:
        # Prometheus: expr, Loki: expr, CloudWatch: various
        expr = targets[0].get("expr", targets[0].get("expression", ""))

    return {
        "panel_id": p.get("id"),
        "title": p.get("title", ""),
        "type": p.get("type", ""),
        "datasource": _get_datasource_name(p),
        "expr_preview": expr[:120] if expr else "",
        "dashboard_uid": dashboard_uid,
    }


def _get_datasource_name(p: dict) -> str:
    """從 panel 取得 datasource 名稱。"""
    ds = p.get("datasource")
    if isinstance(ds, dict):
        return ds.get("type", "") or ds.get("uid", "")
    if isinstance(ds, str):
        return ds
    return ""


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()

    with C.Timer() as t:
        if args.command == "list":
            rows = cmd_list(args)
        else:
            rows = cmd_panels(args)

    C.finalize_rows(rows, args,
                    {"command": args.command, "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
