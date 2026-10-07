def detect(tl, p, ctx):
    every = float(p.get("every_s", 5))
    n, fps = tl["n"], tl["fps"]
    dur = n / fps
    out, t = [], 0.0
    while t < dur:
        out.append({"t": t, "kind": "periodic", "score": 1.0})
        t += every
    return out
