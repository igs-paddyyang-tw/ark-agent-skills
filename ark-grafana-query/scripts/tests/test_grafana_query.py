"""ark-grafana-query 離線單元測試 —— 純邏輯，不需 Grafana 連線。

涵蓋：時間解析、自動步長/間隔、frame 解析（含本 skill 的 InfluxDB /api/ds/query 路徑）。
執行：python -m pytest scripts/tests/  或  python scripts/tests/test_grafana_query.py
"""
from __future__ import annotations

import os
import sys
import time

# 讓 test 能 import 同層 scripts 的模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grafana_query as Q  # noqa: E402


def test_parse_time_relative() -> None:
    """相對時間（1h/6h/1d/7d/30m）解析為 unix ms。"""
    now_ms = int(time.time() * 1000)
    one_h = Q.parse_time("1h")
    assert abs((now_ms - one_h) - 3600 * 1000) < 5000  # 誤差 5s 內
    seven_d = Q.parse_time("7d")
    assert abs((now_ms - seven_d) - 7 * 86400 * 1000) < 5000
    thirty_m = Q.parse_time("30m")
    assert abs((now_ms - thirty_m) - 1800 * 1000) < 5000


def test_parse_time_now() -> None:
    """'now' 解析為目前時間。"""
    assert abs(Q.parse_time("now") - int(time.time() * 1000)) < 5000


def test_auto_step() -> None:
    """依時間範圍決定步長。"""
    assert Q._auto_step(3600) == "15s"       # 1h
    assert Q._auto_step(21600) == "60s"      # 6h
    assert Q._auto_step(86400) == "5m"       # 1d
    assert Q._auto_step(604800) == "30m"     # 7d
    assert Q._auto_step(999999999) == "1h"   # 超長


def test_auto_interval_ms() -> None:
    """步長轉毫秒。"""
    assert Q._auto_interval_ms(3600) == 15 * 1000       # 15s
    assert Q._auto_interval_ms(604800) == 30 * 60 * 1000  # 30m


def test_parse_ds_query_frames_influxdb() -> None:
    """InfluxDB /api/ds/query 的 frame 解析（本 skill 新增的核心路徑）。

    模擬 Grafana 回傳的 time_series frame：一個 time 欄 + 一個 value 欄，
    time 欄應轉成 ISO 字串，帶 refId 與 series 名。
    """
    ts_ms = 1_726_000_000_000  # 某個 unix ms
    fake = {
        "results": {
            "A": {
                "frames": [{
                    "schema": {
                        "name": "bison-gs.system.cpu.idle.mean",
                        "fields": [
                            {"name": "time", "type": "time"},
                            {"name": "value", "type": "number"},
                        ],
                    },
                    "data": {"values": [[ts_ms], [88.5]]},
                }],
            },
        },
    }
    rows = Q._parse_ds_query_frames(fake, limit=50)
    assert len(rows) == 1
    row = rows[0]
    assert row["refId"] == "A"
    assert row["series"] == "bison-gs.system.cpu.idle.mean"
    assert row["value"] == 88.5
    # time 欄轉 ISO（含年份即可，不綁時區細節）
    assert isinstance(row["time"], str) and "20" in row["time"]


def test_parse_ds_query_frames_respects_limit() -> None:
    """limit 生效：frame 有多筆時只回 limit 筆。"""
    times = list(range(1_726_000_000_000, 1_726_000_000_000 + 10))
    vals = [float(i) for i in range(10)]
    fake = {
        "results": {"A": {"frames": [{
            "schema": {"name": "m", "fields": [
                {"name": "time", "type": "time"}, {"name": "value", "type": "number"}]},
            "data": {"values": [times, vals]},
        }]}},
    }
    rows = Q._parse_ds_query_frames(fake, limit=3)
    assert len(rows) == 3


def test_parse_ds_query_frames_empty() -> None:
    """空 frame 不炸、回空 list。"""
    assert Q._parse_ds_query_frames({"results": {"A": {"frames": []}}}, limit=10) == []
    assert Q._parse_ds_query_frames({}, limit=10) == []


def _run() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
