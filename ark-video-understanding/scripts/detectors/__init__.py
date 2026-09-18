"""偵測器註冊表：每個偵測器是純函數 detect(tl, params) -> list[event]，deterministic。

event = {"t": float, "kind": str, "score": float, "detector": str, "extra": {...}}
新增偵測器 = 在此註冊 + 在 pack_lint.DETECTORS 登記（唯一合法的「為 domain 改引擎」路徑）。
"""
from __future__ import annotations

from . import audio_peak, flash, motion_burst, motion_settle, periodic, roi_change, scene_change, still_hold

REGISTRY = {
    "periodic": periodic.detect,
    "scene_change": scene_change.detect,
    "motion_settle": motion_settle.detect,
    "motion_burst": motion_burst.detect,
    "still_hold": still_hold.detect,
    "roi_change": roi_change.detect,
    "flash": flash.detect,
    "audio_peak": audio_peak.detect,
}


def run(tl: dict, spec: dict, ctx: dict | None = None) -> list[dict]:
    fn = REGISTRY.get(spec.get("use"))
    if fn is None:
        raise KeyError(spec.get("use"))
    events = fn(tl, spec, ctx or {})
    for e in events:
        e["detector"] = spec["use"]
        e["label"] = spec.get("label", spec["use"])
        e["t"] = round(float(e["t"]), 3)
        e["score"] = round(float(e.get("score", 1.0)), 4)
    return events
