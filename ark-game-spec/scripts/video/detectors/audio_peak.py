def detect(tl, p, ctx):
    """音量 RMS 尖峰；需 ctx['audio_rms']（vu_events 在 has_audio 時計算）。"""
    rms = ctx.get("audio_rms")
    if not rms:
        return []
    thr = float(p.get("threshold", 2.0))  # 相對於中位數的倍數
    min_gap = float(p.get("min_gap_s", 1.0))
    vals, hop = rms["rms"], rms["hop_s"]
    srt = sorted(vals)
    med = srt[len(srt) // 2] or 1e-6
    out, last = [], -1e9
    for i, v in enumerate(vals):
        t = i * hop
        if v > med * thr and t - last >= min_gap:
            out.append({"t": t, "kind": "audio_peak", "score": v / med})
            last = t
    return out
