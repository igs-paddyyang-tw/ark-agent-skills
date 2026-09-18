def detect(tl, p, ctx):
    """指定 ROI 的像素差尖峰（OCR 未啟用時的 deterministic 替代）。"""
    roi = p.get("roi", {})
    name = roi.get("name") or roi.get("auto") or "roi"
    series = tl.get("roi", {}).get(name)
    if not series:
        return []
    thr = float(p.get("pixel_delta", 0.04))
    min_gap = float(p.get("min_gap_s", 0.25))
    d, t = series["diff"], tl["t"]
    out, last = [], -1e9
    for i in range(1, len(d)):
        if d[i] > thr and t[i] - last >= min_gap:
            out.append({"t": t[i], "kind": "roi_change", "score": d[i], "extra": {"roi": name}})
            last = t[i]
    return out
