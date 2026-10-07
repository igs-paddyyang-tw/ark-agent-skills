def detect(tl, p, ctx):
    thr = float(p.get("threshold", 0.5))
    min_gap = float(p.get("min_gap_s", 0.5))
    out, last = [], -1e9
    for t, d in zip(tl["t"], tl["hist_dist"]):
        if d > thr and t - last >= min_gap:
            out.append({"t": t, "kind": "scene_change", "score": d})
            last = t
    return out
