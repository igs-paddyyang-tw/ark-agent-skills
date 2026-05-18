---
name: ark-kpi-calculator
description: |
  產出標準化 KPI 計算引擎模組 + MCP Tool，支援遊戲類指標（DAU/MAU/ARPU/RTP/留存率/LTV）
  與通用指標（轉換率/流失率/NPS）。產出 Python 模組 + MCP Tool 定義 + pytest 測試。
  使用此 Skill 當使用者提及 KPI 計算、指標引擎、DAU、ARPU、RTP、留存率、
  LTV、遊戲數據指標、calculate kpi、metrics engine、
  或任何需要產出標準化指標計算邏輯的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-18
---

# ark-kpi-calculator

產出標準化 KPI 計算引擎，支援遊戲類 + 通用指標。

## 觸發條件

- 「KPI 計算」、「指標引擎」、「DAU 計算」
- 「ARPU」、「RTP」、「留存率」、「LTV」
- 「遊戲數據指標」、「calculate kpi」、「metrics engine」

---

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 專案目錄 |
| `module_name` | `str` | ❌ | `"kpi"` | 模組名稱 |
| `game_types` | `list[str]` | ❌ | `["slot"]` | 遊戲類型（slot/fish/poker/generic） |
| `output_mode` | `str` | ❌ | `"mcp_tool"` | 產出模式：`mcp_tool` / `module_only` |

---

## 產出指引

### 步驟 1：產出 KPI 模組結構

```
{project_dir}/src/{package}/kpi/
├── __init__.py          # 匯出所有計算函式
├── base.py              # KpiResult dataclass + 共用工具
├── engagement.py        # DAU / MAU / DAU/MAU ratio / Session 指標
├── revenue.py           # Revenue / ARPU / ARPPU / LTV
├── retention.py         # Day-N 留存率 / Cohort 分析
├── game_specific.py     # RTP / Spin Count / 武器分佈（依 game_types）
└── generic.py           # 轉換率 / 流失率 / NPS
```

### 步驟 2：產出 base.py

```python
"""KPI 計算基礎設施。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class KpiResult:
    """標準化 KPI 回傳格式。"""
    metric: str
    value: float
    unit: str = ""                    # "users" / "USD" / "%" / "times"
    period: str = ""                  # "2026-05-17" or "2026-05-11~2026-05-17"
    game: str = "all"
    change_pct: float | None = None   # vs 前期變化百分比
    trend: str = ""                   # "up" / "down" / "stable"
    breakdown: dict = field(default_factory=dict)  # 細分數據

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}
```

### 步驟 3：產出 engagement.py

```python
"""參與度指標：DAU / MAU / Session。"""
from __future__ import annotations

from .base import KpiResult


async def calculate_dau(db, game: str, target_date: str) -> KpiResult:
    """計算 DAU（Daily Active Users）。"""
    sql = f"""
        SELECT COUNT(DISTINCT player_id) as dau
        FROM {{events_table}}
        WHERE event_date = @target_date
        {'AND game_id = @game' if game != 'all' else ''}
    """
    result = await db.query(sql, {"target_date": target_date, "game": game})
    dau = result[0]["dau"] if result else 0

    # 計算前日變化
    prev_result = await db.query(sql, {"target_date": _prev_day(target_date), "game": game})
    prev_dau = prev_result[0]["dau"] if prev_result else 0
    change = ((dau - prev_dau) / prev_dau * 100) if prev_dau > 0 else 0

    return KpiResult(
        metric="dau", value=dau, unit="users",
        period=target_date, game=game,
        change_pct=round(change, 1),
        trend="up" if change > 0 else "down" if change < 0 else "stable",
    )


async def calculate_mau(db, game: str, year_month: str) -> KpiResult:
    """計算 MAU（Monthly Active Users）。"""
    sql = f"""
        SELECT COUNT(DISTINCT player_id) as mau
        FROM {{events_table}}
        WHERE FORMAT_DATE('%Y-%m', event_date) = @year_month
        {'AND game_id = @game' if game != 'all' else ''}
    """
    result = await db.query(sql, {"year_month": year_month, "game": game})
    return KpiResult(metric="mau", value=result[0]["mau"] if result else 0,
                     unit="users", period=year_month, game=game)


async def calculate_avg_session(db, game: str, target_date: str) -> KpiResult:
    """計算平均場次時長（分鐘）。"""
    sql = f"""
        SELECT AVG(TIMESTAMP_DIFF(session_end, session_start, MINUTE)) as avg_min
        FROM {{sessions_table}}
        WHERE DATE(session_start) = @target_date
        {'AND game_id = @game' if game != 'all' else ''}
    """
    result = await db.query(sql, {"target_date": target_date, "game": game})
    return KpiResult(metric="avg_session", value=round(result[0]["avg_min"] or 0, 1),
                     unit="minutes", period=target_date, game=game)
```

### 步驟 4：產出 revenue.py

```python
"""營收指標：Revenue / ARPU / ARPPU / LTV。"""
from __future__ import annotations

from .base import KpiResult


async def calculate_revenue(db, game: str, date_range: list[str]) -> KpiResult:
    """計算區間總營收。"""
    sql = f"""
        SELECT SUM(amount) as total
        FROM {{revenue_table}}
        WHERE created_at BETWEEN @start AND @end
        AND transaction_type = 'deposit'
        {'AND game_id = @game' if game != 'all' else ''}
    """
    result = await db.query(sql, {"start": date_range[0], "end": date_range[1], "game": game})
    return KpiResult(metric="revenue", value=round(result[0]["total"] or 0, 2),
                     unit="USD", period=f"{date_range[0]}~{date_range[1]}", game=game)


async def calculate_arpu(db, game: str, target_date: str) -> KpiResult:
    """計算 ARPU = Revenue / DAU。"""
    from .engagement import calculate_dau
    dau_result = await calculate_dau(db, game, target_date)
    rev_result = await calculate_revenue(db, game, [target_date, target_date])
    arpu = rev_result.value / dau_result.value if dau_result.value > 0 else 0
    return KpiResult(metric="arpu", value=round(arpu, 2),
                     unit="USD", period=target_date, game=game)
```

### 步驟 5：產出 retention.py

```python
"""留存指標：Day-N Retention / Cohort。"""
from __future__ import annotations

from .base import KpiResult


async def calculate_retention(db, game: str, cohort_date: str, day_n: int = 1) -> KpiResult:
    """計算 Day-N 留存率。"""
    sql = f"""
        WITH cohort AS (
            SELECT DISTINCT player_id
            FROM {{events_table}}
            WHERE event_date = @cohort_date
            {'AND game_id = @game' if game != 'all' else ''}
        ),
        returned AS (
            SELECT DISTINCT e.player_id
            FROM {{events_table}} e
            JOIN cohort c ON e.player_id = c.player_id
            WHERE e.event_date = DATE_ADD(@cohort_date, INTERVAL @day_n DAY)
        )
        SELECT
            (SELECT COUNT(*) FROM cohort) as cohort_size,
            (SELECT COUNT(*) FROM returned) as returned_count
    """
    result = await db.query(sql, {"cohort_date": cohort_date, "day_n": day_n, "game": game})
    row = result[0] if result else {"cohort_size": 0, "returned_count": 0}
    rate = row["returned_count"] / row["cohort_size"] * 100 if row["cohort_size"] > 0 else 0

    return KpiResult(
        metric=f"retention_d{day_n}", value=round(rate, 1), unit="%",
        period=cohort_date, game=game,
        breakdown={"cohort_size": row["cohort_size"], "returned": row["returned_count"]},
    )
```

### 步驟 6：產出 game_specific.py（依 game_types）

```python
"""遊戲特定指標。"""
from __future__ import annotations

from .base import KpiResult


# ── Slot 專用 ──

async def calculate_rtp(db, game: str, target_date: str) -> KpiResult:
    """計算 RTP = total_payout / total_bet × 100。"""
    sql = """
        SELECT SUM(win_amount) as payout, SUM(bet_amount) as bet
        FROM slot_events
        WHERE event_date = @target_date
    """
    result = await db.query(sql, {"target_date": target_date})
    row = result[0] if result else {"payout": 0, "bet": 0}
    rtp = row["payout"] / row["bet"] * 100 if row["bet"] > 0 else 0
    return KpiResult(metric="rtp", value=round(rtp, 2), unit="%",
                     period=target_date, game=game)


# ── Fish Game 專用 ──

async def calculate_boss_kill_rate(db, target_date: str) -> KpiResult:
    """計算 Boss 擊殺率。"""
    sql = """
        SELECT
            COUNT(CASE WHEN event_type = 'boss_kill' THEN 1 END) as kills,
            COUNT(CASE WHEN event_type = 'boss_encounter' THEN 1 END) as encounters
        FROM fish_events
        WHERE event_date = @target_date
    """
    result = await db.query(sql, {"target_date": target_date})
    row = result[0] if result else {"kills": 0, "encounters": 0}
    rate = row["kills"] / row["encounters"] * 100 if row["encounters"] > 0 else 0
    return KpiResult(metric="boss_kill_rate", value=round(rate, 1), unit="%",
                     period=target_date, game="fish")
```

### 步驟 7：產出 MCP Tool 定義（如 output_mode="mcp_tool"）

```python
# src/{package}/tools/calculate_kpi.py
"""MCP Tool: calculate_kpi。"""
from __future__ import annotations

from ..kpi import (
    calculate_dau, calculate_mau, calculate_arpu,
    calculate_revenue, calculate_retention, calculate_rtp,
    calculate_avg_session,
)

TOOL_DEFINITION = {
    "name": "calculate_kpi",
    "description": "計算遊戲 KPI 指標（DAU/MAU/Revenue/ARPU/RTP/留存率/平均場次）",
    "inputSchema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["dau", "mau", "revenue", "arpu", "rtp",
                         "retention", "avg_session", "boss_kill_rate"],
                "description": "指標名稱",
            },
            "game": {"type": "string", "default": "all", "description": "遊戲篩選"},
            "date_range": {
                "type": "array", "items": {"type": "string"},
                "description": "[start_date, end_date] 或 [single_date]",
            },
            "day_n": {"type": "integer", "default": 1, "description": "留存天數（retention 用）"},
        },
        "required": ["metric", "date_range"],
    },
}


async def calculate_kpi(params: dict) -> dict:
    """MCP Tool handler。"""
    from ..tools.base import get_db
    db = get_db()
    metric = params["metric"]
    game = params.get("game", "all")
    date_range = params["date_range"]
    target_date = date_range[0]

    dispatch = {
        "dau": lambda: calculate_dau(db, game, target_date),
        "mau": lambda: calculate_mau(db, game, target_date[:7]),
        "revenue": lambda: calculate_revenue(db, game, date_range),
        "arpu": lambda: calculate_arpu(db, game, target_date),
        "rtp": lambda: calculate_rtp(db, game, target_date),
        "retention": lambda: calculate_retention(db, game, target_date, params.get("day_n", 1)),
        "avg_session": lambda: calculate_avg_session(db, game, target_date),
    }

    if metric not in dispatch:
        return {"error": f"不支援的指標: {metric}"}

    result = await dispatch[metric]()
    return result.to_dict()
```

### 步驟 8：產出 pytest 測試

```python
# tests/test_kpi.py
"""KPI 計算模組測試。"""
import pytest
from src.{package}.kpi.base import KpiResult


def test_kpi_result_to_dict():
    r = KpiResult(metric="dau", value=1000, unit="users", period="2026-05-18")
    d = r.to_dict()
    assert d["metric"] == "dau"
    assert d["value"] == 1000
    assert "breakdown" not in d  # 空 dict 不輸出


def test_kpi_result_with_change():
    r = KpiResult(metric="dau", value=1000, change_pct=-15.2, trend="down")
    d = r.to_dict()
    assert d["change_pct"] == -15.2
    assert d["trend"] == "down"
```

---

## 支援的指標清單

| 類別 | 指標 | 計算方式 | 單位 |
|------|------|---------|------|
| 參與度 | DAU | DISTINCT player_id per day | users |
| 參與度 | MAU | DISTINCT player_id per month | users |
| 參與度 | avg_session | AVG(session_duration) | minutes |
| 營收 | revenue | SUM(deposits) | USD |
| 營收 | ARPU | revenue / DAU | USD |
| 營收 | ARPPU | revenue / paying_users | USD |
| 留存 | retention_dN | returned_d{N} / cohort_d0 | % |
| Slot | RTP | total_payout / total_bet | % |
| Fish | boss_kill_rate | kills / encounters | % |
| 通用 | churn_rate | lost_users / prev_active | % |

## 注意事項

- 所有計算函式為 async（支援 BigQuery 非同步查詢）
- SQL 使用參數化查詢（防 injection）
- `KpiResult.change_pct` 自動計算 vs 前期變化
- 日期格式統一 `YYYY-MM-DD`
- 無資料時回傳 value=0，不報錯
