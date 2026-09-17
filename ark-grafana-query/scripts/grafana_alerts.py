#!/usr/bin/env python3
"""Grafana 告警查詢 CLI — 查看告警狀態與規則。

子指令：
  list   [--state firing|pending|inactive]  列出告警實例
  rules  [--folder FOLDER]                   列出告警規則定義

用法:
  python grafana_alerts.py list
  python grafana_alerts.py list --state firing
  python grafana_alerts.py rules
  python grafana_alerts.py rules --folder "Infrastructure"
認證: GRAFANA_URL + GRAFANA_TOKEN 或 GRAFANA_USER + GRAFANA_PASSWORD
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafana_common as C  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Grafana alerts")
    ap.add_argument("command", choices=["list", "rules"])
    ap.add_argument("--state", help="篩選告警狀態（firing/pending/inactive/normal）")
    ap.add_argument("--folder", help="篩選 folder（rules 指令用）")
    ap.add_argument("--out", help="結果落盤路徑")
    ap.add_argument("--out-format", choices=["json", "jsonl"], default="json")
    ap.add_argument("--max-stdout-rows", type=int, default=C.DEFAULT_STDOUT_ROWS)
    ap.add_argument("--timeout", type=int, default=C.DEFAULT_TIMEOUT)
    return ap


def cmd_list_alerts(args: argparse.Namespace) -> list[dict]:
    """列出告警實例（alertmanager alerts）。"""
    # Grafana Unified Alerting API
    alerts = C.grafana_get("/api/alertmanager/grafana/api/v2/alerts",
                           timeout=args.timeout)

    rows = []
    for a in alerts:
        state = a.get("status", {}).get("state", "")
        if args.state and state != args.state:
            continue
        labels = a.get("labels", {})
        annotations = a.get("annotations", {})
        rows.append({
            "alertname": labels.get("alertname", ""),
            "state": state,
            "severity": labels.get("severity", ""),
            "summary": annotations.get("summary", "")[:200],
            "starts_at": a.get("startsAt", ""),
            "labels": labels,
        })
    return rows


def cmd_list_rules(args: argparse.Namespace) -> list[dict]:
    """列出告警規則定義。"""
    # Grafana Ruler API
    data = C.grafana_get("/api/ruler/grafana/api/v1/rules",
                         timeout=args.timeout)

    rows = []
    # data 格式: {folder: [{name, rules: [...]}]}
    if isinstance(data, dict):
        for folder, groups in data.items():
            if args.folder and folder != args.folder:
                continue
            for group in groups:
                group_name = group.get("name", "")
                for rule in group.get("rules", []):
                    grafana_alert = rule.get("grafana_alert", {})
                    rows.append({
                        "folder": folder,
                        "group": group_name,
                        "title": grafana_alert.get("title", rule.get("alert", "")),
                        "condition": grafana_alert.get("condition", ""),
                        "state": rule.get("state", ""),
                        "for": rule.get("for", ""),
                        "annotations": rule.get("annotations", {}),
                    })
    return rows


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()

    with C.Timer() as t:
        if args.command == "list":
            rows = cmd_list_alerts(args)
        else:
            rows = cmd_list_rules(args)

    C.finalize_rows(rows, args,
                    {"command": f"alerts_{args.command}", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
