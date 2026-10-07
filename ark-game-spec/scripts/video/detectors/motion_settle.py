def detect(tl, p, ctx):
    """motion 高於 high 持續 ≥ min_spin_s 後，落到 low 以下並持續 ≥ min_settle_s → 事件在第一個 settled 幀。"""
    from ._adaptive import settle_thresholds
    high, low = settle_thresholds(tl, p)
    min_spin = float(p.get("min_spin_s", 0.5))
    min_settle = float(p.get("min_settle_s", 0.3))
    fps = tl["fps"]
    m, t = tl["motion"], tl["t"]
    n = len(m)
    out = []
    i = 0
    while i < n:
        if m[i] > high:
            j = i
            while j < n and m[j] > low * 1.5:  # spinning 直到明顯下降
                j += 1
            spin_dur = (j - i) / fps
            peak = max(m[i:j]) if j > i else m[i]
            if spin_dur >= min_spin and j < n:
                k = j
                while k < n and m[k] < low:
                    k += 1
                if (k - j) / fps >= min_settle:
                    out.append({"t": t[j], "kind": "settle", "score": peak,
                                "extra": {"spin_s": round(spin_dur, 3), "settle_s": round((k - j) / fps, 3),
                                          "thresholds": [high, low]}})
                i = max(k, j + 1)
                continue
            i = max(j, i + 1)
        else:
            i += 1
    return out
