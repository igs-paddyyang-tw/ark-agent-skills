def detect(tl, p, ctx):
    """靜止 ≥ min_s 的區段：事件在起點與終點，extra 帶 duration（= 回合 phase 秒數，deterministic）。"""
    from ._adaptive import percentile
    thr = float(p.get("threshold", 0.01))
    if p.get("adaptive", True):
        thr = max(min(thr, 0.3 * percentile(tl["motion"], 50) + 1e-4), 0.002)
    min_s = float(p.get("min_s", 2.0))
    fps = tl["fps"]
    m, t = tl["motion"], tl["t"]
    out, i, n = [], 0, len(m)
    while i < n:
        if m[i] < thr:
            j = i
            while j < n and m[j] < thr:
                j += 1
            dur = (j - i) / fps
            if dur >= min_s:
                out.append({"t": t[i], "kind": "hold_start", "score": dur, "extra": {"duration_s": round(dur, 3), "end_t": t[min(j, n - 1)]}})
                out.append({"t": t[min(j, n - 1)], "kind": "hold_end", "score": dur, "extra": {"duration_s": round(dur, 3), "start_t": t[i]}})
            i = j
        else:
            i += 1
    return out
