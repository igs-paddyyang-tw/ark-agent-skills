"""deterministic 自適應門檻：依 timeline 分位數推得，避免對錄影品質寫死絕對值。"""


def percentile(vals, q):
    s = sorted(vals)
    if not s:
        return 0.0
    k = min(len(s) - 1, max(0, int(round(q / 100 * (len(s) - 1)))))
    return s[k]


def settle_thresholds(tl, p):
    """回 (high, low)。若 pack 給了絕對值且 adaptive=false 則照用。"""
    if p.get("adaptive", True):
        p90 = percentile(tl["motion"], 90)
        p50 = percentile(tl["motion"], 50)
        high = max(0.5 * p90, float(p.get("min_high", 0.02)))
        low = max(0.2 * high, p50 * 1.5, float(p.get("min_low", 0.003)))
        low = min(low, high * 0.6)
        return round(high, 5), round(low, 5)
    return float(p.get("high", 0.12)), float(p.get("low", 0.02))
