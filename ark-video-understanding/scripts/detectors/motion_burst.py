def detect(tl, p, ctx):
    from ._adaptive import percentile
    thr = float(p.get("threshold", 0.3))
    if p.get("adaptive", True):
        thr = max(percentile(tl["motion"], 97), float(p.get("min_threshold", 0.05)))
    min_gap = float(p.get("min_gap_s", 0.5))
    m, t = tl["motion"], tl["t"]
    out, last = [], -1e9
    for i in range(1, len(m) - 1):
        if m[i] > thr and m[i] >= m[i - 1] and m[i] >= m[i + 1] and t[i] - last >= min_gap:
            out.append({"t": t[i], "kind": "burst", "score": m[i]})
            last = t[i]
    return out
