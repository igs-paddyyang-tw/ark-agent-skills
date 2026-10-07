def detect(tl, p, ctx):
    thr = float(p.get("threshold", 0.35))
    min_gap = float(p.get("min_gap_s", 1.0))
    b, t = tl["brightness"], tl["t"]
    out, last = [], -1e9
    for i in range(1, len(b)):
        jump = (b[i] - b[i - 1]) / max(b[i - 1], 0.05)
        if jump > thr and t[i] - last >= min_gap:
            out.append({"t": t[i], "kind": "flash", "score": jump})
            last = t[i]
    return out
