#!/usr/bin/env python3
"""Grafana 數據查詢 CLI — 查 Panel 數據或直接跑 datasource query。

兩種模式：
  1. Panel 查詢：--uid DASHBOARD_UID --panel-id N [--from 1h]
     → 用 Grafana 的 /api/ds/query 模擬 panel 的查詢
  2. Datasource 直查：--datasource-uid DS --expr "..." [--from 1h]
     → 直接對 datasource 發 query（Prometheus/Loki/CloudWatch）

用法:
  python grafana_query.py --uid "abc" --panel-id 4 --from 1h
  python grafana_query.py --datasource-uid "prometheus" --expr "up{job='slotverse'}" --from 1h
  python grafana_query.py --datasource-uid "loki" --expr '{app="bison"} |= "error"' --from 30m --limit 50
認證: GRAFANA_URL + GRAFANA_TOKEN 或 GRAFANA_USER + GRAFANA_PASSWORD
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grafana_common as C  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Grafana data query")
    # Panel 模式
    ap.add_argument("--uid", help="Dashboard UID")
    ap.add_argument("--panel-id", type=int, help="Panel ID")
    # Datasource 直查模式
    ap.add_argument("--datasource-uid", help="Datasource UID（直查模式）")
    ap.add_argument("--expr", help="查詢表達式（PromQL / LogQL / SQL）")
    # 時間範圍
    ap.add_argument("--from", dest="time_from", default="1h",
                    help="起始時間（相對: 1h/6h/1d/7d 或 ISO 格式）")
    ap.add_argument("--to", dest="time_to", default="now", help="結束時間")
    # 其他
    ap.add_argument("--limit", type=int, default=100, help="結果筆數上限")
    ap.add_argument("--step", help="查詢步長（如 60s, 5m），預設自動")
    ap.add_argument("--out", help="結果落盤路徑")
    ap.add_argument("--out-format", choices=["json", "jsonl"], default="json")
    ap.add_argument("--max-stdout-rows", type=int, default=C.DEFAULT_STDOUT_ROWS)
    ap.add_argument("--timeout", type=int, default=C.DEFAULT_TIMEOUT)
    return ap


def parse_time(s: str) -> int:
    """解析時間字串為 unix ms。"""
    if s == "now":
        return int(time.time() * 1000)

    # 相對時間: 1h, 6h, 1d, 7d, 30m
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    if len(s) >= 2 and s[-1] in units and s[:-1].isdigit():
        delta = int(s[:-1]) * units[s[-1]]
        return int((time.time() - delta) * 1000)

    # ISO 格式
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        C.fail("BAD_INPUT", f"無法解析時間: {s}", "支援格式: 1h / 6h / 1d / 7d / ISO datetime")
    return 0  # unreachable


def query_panel(args: argparse.Namespace) -> list[dict]:
    """透過 Dashboard JSON 取得 Panel 的 targets，再查詢。"""
    dashboard = C.grafana_get(f"/api/dashboards/uid/{args.uid}", timeout=args.timeout)
    panels = dashboard.get("dashboard", {}).get("panels", [])

    # 找到目標 panel（包含 row 內巢狀的）
    target_panel = None
    for p in panels:
        if p.get("id") == args.panel_id:
            target_panel = p
            break
        if p.get("type") == "row":
            for nested in p.get("panels", []):
                if nested.get("id") == args.panel_id:
                    target_panel = nested
                    break
            if target_panel:
                break

    if not target_panel:
        C.fail("NOT_FOUND", f"Panel ID {args.panel_id} 不存在於 dashboard {args.uid}",
               "用 grafana_dashboards.py panels --uid ... 查看可用 panel")

    targets = target_panel.get("targets", [])
    if not targets:
        C.fail("BAD_INPUT", "此 Panel 沒有 targets（無查詢定義）", "")

    # 取 datasource（panel 層級，target 可能各自覆蓋）
    ds = target_panel.get("datasource", {})
    panel_ds_uid = ds.get("uid", "") if isinstance(ds, dict) else str(ds)

    # 用第一個 target 的 expr 查詢（Prometheus / Loki）
    first_target = targets[0]
    expr = first_target.get("expr", first_target.get("expression", ""))

    if expr:
        return _query_datasource(panel_ds_uid, expr, args)

    # 無 expr：InfluxDB / SQL 等 datasource，把原生 target 整包送 /api/ds/query，
    # 讓 Grafana 自己翻譯查詢語言（InfluxQL / Flux / SQL 皆通用）。
    return _query_ds_native(panel_ds_uid, targets, args)


def query_datasource_direct(args: argparse.Namespace) -> list[dict]:
    """直接對 datasource 發 query。"""
    if not args.datasource_uid:
        C.fail("BAD_INPUT", "直查模式需要 --datasource-uid", "")
    if not args.expr:
        C.fail("BAD_INPUT", "直查模式需要 --expr", "")

    return _query_datasource(args.datasource_uid, args.expr, args)


def _query_datasource(ds_uid: str, expr: str, args: argparse.Namespace) -> list[dict]:
    """通用 datasource query（Prometheus range_query / Loki query）。"""
    import requests

    cfg = C.get_grafana_config()
    from_ms = parse_time(args.time_from)
    to_ms = parse_time(args.time_to)

    # 先嘗試 Prometheus range query
    from_s = from_ms // 1000
    to_s = to_ms // 1000
    step = args.step or _auto_step(to_s - from_s)

    # 嘗試 Prometheus API
    prom_path = f"/api/datasources/proxy/uid/{ds_uid}/api/v1/query_range"
    params = {"query": expr, "start": from_s, "end": to_s, "step": step}

    try:
        resp = requests.get(f"{cfg['url']}{prom_path}",
                            headers=cfg["headers"], params=params, timeout=args.timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        C.fail("CONN_FAILED", f"Datasource proxy 連線失敗: {e}", "")

    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "success":
            return _parse_prometheus_response(data, args.limit)

    # Fallback: 嘗試 Loki query
    loki_path = f"/api/datasources/proxy/uid/{ds_uid}/loki/api/v1/query_range"
    params_loki = {"query": expr, "start": from_s * 10**9, "end": to_s * 10**9,
                   "limit": args.limit}

    try:
        resp = requests.get(f"{cfg['url']}{loki_path}",
                            headers=cfg["headers"], params=params_loki, timeout=args.timeout)
    except (requests.ConnectionError, requests.Timeout):
        pass
    else:
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return _parse_loki_response(data, args.limit)

    # 都不行，用 Grafana unified query API
    return _query_via_unified_api(ds_uid, expr, from_ms, to_ms, args)


def _query_via_unified_api(ds_uid: str, expr: str, from_ms: int, to_ms: int,
                           args: argparse.Namespace) -> list[dict]:
    """使用 Grafana /api/ds/query（統一查詢 API）。"""
    import requests

    cfg = C.get_grafana_config()
    payload = {
        "queries": [{
            "datasourceId": 0,
            "datasource": {"uid": ds_uid},
            "expr": expr,
            "refId": "A",
            "maxDataPoints": args.limit,
            "intervalMs": 60000,
        }],
        "from": str(from_ms),
        "to": str(to_ms),
    }

    try:
        resp = requests.post(f"{cfg['url']}/api/ds/query",
                             headers={**cfg["headers"], "Content-Type": "application/json"},
                             json=payload, timeout=args.timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        C.fail("CONN_FAILED", f"Unified query 失敗: {e}", "")

    if resp.status_code >= 400:
        C.fail("QUERY_FAILED", f"HTTP {resp.status_code}: {resp.text[:300]}", "")

    data = resp.json()
    frames = data.get("results", {}).get("A", {}).get("frames", [])
    rows = []
    for frame in frames[:args.limit]:
        schema = frame.get("schema", {})
        fields = schema.get("fields", [])
        values_data = frame.get("data", {}).get("values", [])
        if not values_data:
            continue
        # 轉為 row-based
        field_names = [f.get("name", f"field_{i}") for i, f in enumerate(fields)]
        num_rows = len(values_data[0]) if values_data else 0
        for i in range(min(num_rows, args.limit - len(rows))):
            row = {}
            for j, name in enumerate(field_names):
                row[name] = values_data[j][i] if j < len(values_data) else None
            rows.append(row)
    return rows


def _query_ds_native(panel_ds_uid: str, targets: list, args: argparse.Namespace) -> list[dict]:
    """把 panel 的原生 target 結構整包送 /api/ds/query，由 Grafana 代理查詢。

    適用 InfluxDB（InfluxQL/Flux）、SQL 等非 PromQL/LogQL 的 datasource ——
    這些 target 沒有 expr，但有 measurement/select/rawSql 等結構，
    Grafana 會依 datasource 類型自行翻譯執行。
    """
    import requests

    cfg = C.get_grafana_config()
    from_ms = parse_time(args.time_from)
    to_ms = parse_time(args.time_to)
    interval_ms = _auto_interval_ms(to_ms // 1000 - from_ms // 1000)

    queries = []
    for i, t in enumerate(targets):
        if t.get("hide"):
            continue
        q = dict(t)  # 保留原生欄位（measurement/select/groupBy/tags/rawSql...）
        q.setdefault("refId", chr(ord("A") + i))
        # datasource：target 自帶優先，否則用 panel 層級的
        if not q.get("datasource"):
            q["datasource"] = {"uid": panel_ds_uid}
        q["maxDataPoints"] = args.limit if args.limit else 200
        q["intervalMs"] = interval_ms
        queries.append(q)

    if not queries:
        C.fail("BAD_INPUT", "此 Panel 所有 target 皆為 hidden，無可查詢項", "")

    payload = {"queries": queries, "from": str(from_ms), "to": str(to_ms)}

    try:
        resp = requests.post(f"{cfg['url']}/api/ds/query",
                             headers={**cfg["headers"], "Content-Type": "application/json"},
                             json=payload, timeout=args.timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        C.fail("CONN_FAILED", f"Native query 失敗: {e}", "")

    if resp.status_code >= 400:
        C.fail("QUERY_FAILED", f"HTTP {resp.status_code}: {resp.text[:300]}",
               "確認 datasource 支援、tags/measurement 是否存在")

    return _parse_ds_query_frames(resp.json(), args.limit)


def _parse_ds_query_frames(data: dict, limit: int) -> list[dict]:
    """解析 /api/ds/query 的 frames 為 rows（支援多 refId、time_series 格式）。"""
    rows: list[dict] = []
    results = data.get("results", {})
    for ref_id, res in results.items():
        for frame in res.get("frames", []):
            schema = frame.get("schema", {})
            fields = schema.get("fields", [])
            values = frame.get("data", {}).get("values", [])
            if not values or not fields:
                continue
            # series 名稱（InfluxDB 常放在 frame name 或 field labels）
            series_name = schema.get("name", "") or frame.get("name", "")
            field_names = [f.get("name", f"field_{j}") for j, f in enumerate(fields)]
            num_rows = len(values[0])
            for r in range(num_rows):
                if len(rows) >= limit:
                    return rows
                row = {"refId": ref_id}
                if series_name:
                    row["series"] = series_name
                for j, name in enumerate(field_names):
                    val = values[j][r] if r < len(values[j]) else None
                    # 時間欄位（Grafana 回 unix ms）轉 ISO
                    ftype = fields[j].get("type", "")
                    if ftype == "time" and isinstance(val, (int, float)):
                        row[name] = datetime.fromtimestamp(
                            val / 1000, tz=timezone.utc).isoformat()
                    else:
                        row[name] = val
                rows.append(row)
    return rows


def _auto_interval_ms(range_seconds: int) -> int:
    """依時間範圍自動決定 interval（毫秒）。"""
    step_str = _auto_step(range_seconds)
    units = {"s": 1000, "m": 60000, "h": 3600000}
    return int(step_str[:-1]) * units.get(step_str[-1], 1000)


def _parse_prometheus_response(data: dict, limit: int) -> list[dict]:
    """解析 Prometheus response 為 rows。"""
    rows = []
    result = data.get("data", {}).get("result", [])
    for series in result:
        metric = series.get("metric", {})
        values = series.get("values", [])
        metric_str = json.dumps(metric, ensure_ascii=False) if metric else ""
        for ts, val in values[-limit:]:
            rows.append({
                "metric": metric_str,
                "timestamp": ts,
                "time": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                "value": float(val) if val != "NaN" else None,
            })
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break
    return rows


def _parse_loki_response(data: dict, limit: int) -> list[dict]:
    """解析 Loki response 為 rows。"""
    rows = []
    result = data.get("data", {}).get("result", [])
    for stream in result:
        labels = stream.get("stream", {})
        label_str = json.dumps(labels, ensure_ascii=False)
        for entry in stream.get("values", []):
            ts_ns, line = entry[0], entry[1]
            ts_s = int(ts_ns) / 1e9
            rows.append({
                "labels": label_str,
                "timestamp": ts_s,
                "time": datetime.fromtimestamp(ts_s, tz=timezone.utc).isoformat(),
                "line": line[:500],
            })
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break
    return rows


def _auto_step(range_seconds: int) -> str:
    """自動計算查詢步長。"""
    if range_seconds <= 3600:
        return "15s"
    if range_seconds <= 21600:
        return "60s"
    if range_seconds <= 86400:
        return "5m"
    if range_seconds <= 604800:
        return "30m"
    return "1h"


def main() -> None:
    C.load_env()
    args = build_parser().parse_args()

    # 判斷模式
    if args.uid and args.panel_id is not None:
        mode = "panel"
    elif args.datasource_uid and args.expr:
        mode = "datasource"
    else:
        C.fail("BAD_INPUT",
               "需要 --uid + --panel-id（panel 模式）或 --datasource-uid + --expr（直查模式）",
               "見 SKILL.md 的呼叫範例")

    with C.Timer() as t:
        if mode == "panel":
            rows = query_panel(args)
        else:
            rows = query_datasource_direct(args)

    C.finalize_rows(rows, args,
                    {"command": f"query_{mode}", "elapsed_ms": t.elapsed_ms,
                     "time_from": args.time_from, "time_to": args.time_to})


if __name__ == "__main__":
    main()
