---
name: ark-anomaly-detector
description: |
  產出 KPI 異常偵測模組 + 告警規則引擎 + MCP Tool + 排程整合。
  支援 Z-score、IQR、移動平均偏差三種偵測演算法，
  告警規則以 YAML 配置，支援 Telegram/Slack 通知。
  使用此 Skill 當使用者提及異常偵測、告警規則、KPI 監控、
  anomaly detection、數據告警、指標異常、DAU 突降、
  或任何需要自動偵測數據異常並發送通知的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-18
---

# ark-anomaly-detector

產出 KPI 異常偵測 + 告警規則引擎，自動監控數據健康。

## 觸發條件

- 「異常偵測」、「告警規則」、「KPI 監控」
- 「anomaly detection」、「數據告警」、「指標異常」
- 「DAU 突降」、「營收異常」、「自動告警」

---

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 專案目錄 |
| `module_name` | `str` | ❌ | `"anomaly"` | 模組名稱 |
| `notify_channel` | `str` | ❌ | `"telegram"` | 通知管道（telegram/slack/webhook） |
| `output_mode` | `str` | ❌ | `"mcp_tool"` | 產出模式 |

---

## 產出指引

### 步驟 1：產出模組結構

```
{project_dir}/src/{package}/anomaly/
├── __init__.py
├── detector.py          # 三種偵測演算法
├── rules.py             # 規則引擎（讀取 YAML）
├── notifier.py          # 通知發送（Telegram/Slack/Webhook）
└── scheduler_hook.py    # 排程整合（每小時/每日檢查）

{project_dir}/config/
└── alert_rules.yaml     # 告警規則配置
```

### 步驟 2：產出 detector.py

```python
"""異常偵測演算法。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DetectionMethod(str, Enum):
    ZSCORE = "zscore"
    IQR = "iqr"
    MOVING_AVG = "moving_avg"


@dataclass
class AnomalyResult:
    """偵測結果。"""
    is_anomaly: bool
    metric: str
    current_value: float
    expected_range: tuple[float, float]  # (lower, upper)
    deviation_pct: float                 # 偏離百分比
    method: str
    severity: str = "info"               # info / warning / critical


def detect_zscore(values: list[float], current: float, threshold: float = 2.0) -> AnomalyResult:
    """Z-score 偵測：current 偏離歷史均值超過 N 個標準差。"""
    import statistics
    if len(values) < 7:
        return AnomalyResult(is_anomaly=False, metric="", current_value=current,
                             expected_range=(0, 0), deviation_pct=0, method="zscore")
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    if std == 0:
        return AnomalyResult(is_anomaly=False, metric="", current_value=current,
                             expected_range=(mean, mean), deviation_pct=0, method="zscore")
    z = (current - mean) / std
    lower = mean - threshold * std
    upper = mean + threshold * std
    deviation = (current - mean) / mean * 100 if mean != 0 else 0
    return AnomalyResult(
        is_anomaly=abs(z) > threshold,
        metric="", current_value=current,
        expected_range=(round(lower, 2), round(upper, 2)),
        deviation_pct=round(deviation, 1),
        method="zscore",
    )


def detect_iqr(values: list[float], current: float, factor: float = 1.5) -> AnomalyResult:
    """IQR 偵測：current 超出 Q1-1.5*IQR ~ Q3+1.5*IQR。"""
    sorted_v = sorted(values)
    n = len(sorted_v)
    q1 = sorted_v[n // 4]
    q3 = sorted_v[3 * n // 4]
    iqr = q3 - q1
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr
    median = sorted_v[n // 2]
    deviation = (current - median) / median * 100 if median != 0 else 0
    return AnomalyResult(
        is_anomaly=current < lower or current > upper,
        metric="", current_value=current,
        expected_range=(round(lower, 2), round(upper, 2)),
        deviation_pct=round(deviation, 1),
        method="iqr",
    )


def detect_moving_avg(values: list[float], current: float,
                      window: int = 7, threshold_pct: float = 20.0) -> AnomalyResult:
    """移動平均偵測：current 偏離近 N 日均值超過 threshold%。"""
    if len(values) < window:
        return AnomalyResult(is_anomaly=False, metric="", current_value=current,
                             expected_range=(0, 0), deviation_pct=0, method="moving_avg")
    recent = values[-window:]
    avg = sum(recent) / len(recent)
    deviation = (current - avg) / avg * 100 if avg != 0 else 0
    lower = avg * (1 - threshold_pct / 100)
    upper = avg * (1 + threshold_pct / 100)
    return AnomalyResult(
        is_anomaly=abs(deviation) > threshold_pct,
        metric="", current_value=current,
        expected_range=(round(lower, 2), round(upper, 2)),
        deviation_pct=round(deviation, 1),
        method="moving_avg",
    )
```

### 步驟 3：產出 alert_rules.yaml

```yaml
# 告警規則配置
rules:
  - name: dau_drop
    metric: dau
    method: moving_avg
    params:
      window: 7
      threshold_pct: 20
    severity: critical
    message: "⚠️ DAU 突降 {deviation_pct}%（當前 {current_value}，預期 {expected_range}）"

  - name: revenue_spike
    metric: revenue
    method: zscore
    params:
      threshold: 3.0
    severity: warning
    message: "📈 營收異常波動 {deviation_pct}%（當前 {current_value}）"

  - name: rtp_drift
    metric: rtp
    method: iqr
    params:
      factor: 1.5
    severity: critical
    message: "🎰 RTP 偏離正常範圍（當前 {current_value}%，預期 {expected_range}）"

  - name: retention_drop
    metric: retention_d1
    method: moving_avg
    params:
      window: 14
      threshold_pct: 15
    severity: warning
    message: "📉 D1 留存率下降 {deviation_pct}%（當前 {current_value}%）"
```

### 步驟 4：產出 rules.py

```python
"""告警規則引擎。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .detector import detect_zscore, detect_iqr, detect_moving_avg, AnomalyResult


@dataclass
class AlertRule:
    name: str
    metric: str
    method: str
    params: dict
    severity: str
    message: str


def load_rules(path: str | Path = "config/alert_rules.yaml") -> list[AlertRule]:
    """載入告警規則。"""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [AlertRule(**r) for r in raw.get("rules", [])]


def evaluate_rule(rule: AlertRule, history: list[float], current: float) -> AnomalyResult | None:
    """評估單一規則，回傳異常結果或 None。"""
    dispatch = {
        "zscore": detect_zscore,
        "iqr": detect_iqr,
        "moving_avg": detect_moving_avg,
    }
    fn = dispatch.get(rule.method)
    if not fn:
        return None
    result = fn(history, current, **rule.params)
    result.metric = rule.metric
    result.severity = rule.severity
    if result.is_anomaly:
        return result
    return None
```

### 步驟 5：產出 notifier.py

```python
"""告警通知發送。"""
from __future__ import annotations

import logging
from .detector import AnomalyResult

logger = logging.getLogger(__name__)


async def notify_telegram(result: AnomalyResult, message_template: str,
                          bot_token: str, chat_id: str) -> None:
    """透過 Telegram Bot 發送告警。"""
    import httpx
    text = message_template.format(
        deviation_pct=result.deviation_pct,
        current_value=result.current_value,
        expected_range=f"{result.expected_range[0]}~{result.expected_range[1]}",
    )
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})
    logger.info(f"告警已發送: {text}")


async def notify_webhook(result: AnomalyResult, message_template: str,
                         webhook_url: str) -> None:
    """透過 Webhook 發送告警。"""
    import httpx
    text = message_template.format(
        deviation_pct=result.deviation_pct,
        current_value=result.current_value,
        expected_range=f"{result.expected_range[0]}~{result.expected_range[1]}",
    )
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={"text": text, "severity": result.severity})
```

### 步驟 6：產出 MCP Tool（如 output_mode="mcp_tool"）

```python
# src/{package}/tools/check_anomaly.py
TOOL_DEFINITION = {
    "name": "check_anomaly",
    "description": "檢查 KPI 是否異常（依據 alert_rules.yaml 規則）",
    "inputSchema": {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "description": "要檢查的指標"},
            "current_value": {"type": "number", "description": "當前值"},
            "history": {"type": "array", "items": {"type": "number"}, "description": "歷史值（近 30 天）"},
        },
        "required": ["metric", "current_value", "history"],
    },
}


async def check_anomaly(params: dict) -> dict:
    """MCP Tool handler。"""
    from ..anomaly.rules import load_rules, evaluate_rule
    rules = load_rules()
    metric_rules = [r for r in rules if r.metric == params["metric"]]
    alerts = []
    for rule in metric_rules:
        result = evaluate_rule(rule, params["history"], params["current_value"])
        if result:
            alerts.append({
                "rule": rule.name,
                "severity": result.severity,
                "deviation_pct": result.deviation_pct,
                "expected_range": result.expected_range,
                "message": rule.message.format(
                    deviation_pct=result.deviation_pct,
                    current_value=result.current_value,
                    expected_range=f"{result.expected_range[0]}~{result.expected_range[1]}",
                ),
            })
    return {"metric": params["metric"], "is_anomaly": len(alerts) > 0, "alerts": alerts}
```

### 步驟 7：驗證

```bash
python -c "
from src.{package}.anomaly.detector import detect_moving_avg
result = detect_moving_avg([100,102,98,101,99,103,97], 75, window=7, threshold_pct=20)
print(f'異常: {result.is_anomaly}, 偏離: {result.deviation_pct}%')
"
# 預期：異常: True, 偏離: -25.0%
```

---

## 注意事項

- 歷史資料至少需要 7 天才能有效偵測
- Z-score 適合常態分佈數據（DAU、Session）
- IQR 適合有離群值的數據（Revenue、RTP）
- 移動平均適合趨勢性數據（留存率）
- 告警規則可熱更新（修改 YAML 不需重啟）
- 通知發送失敗不影響偵測流程（靜默失敗 + 記錄日誌）
