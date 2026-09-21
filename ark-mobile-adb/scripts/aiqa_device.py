"""aiqa_device — 裝置抽象：AdbDevice（真 BlueStacks，透過 ark_mobile_adb 模組）與 FakeDevice（合成遊戲，dry-run / 測試）。

共同介面：screenshot(path) / tap / key / swipe / wait_stable / restart_app / net / logcat_crash / wm_size / tick
感知：read_roi(pack, roi, engine) → {value, text, engine, confidence}；visual(question, image) → {answer, confidence}
定位：detect_screen(pack, image) / locate(pack, 'btn:x', image)
所有動作寫入 trace（時間、指令、截圖 sha）→ 可反渲染成重現步驟。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time

import aiqa_common as C
import ark_mobile_adb as M


class Trace:
    def __init__(self, path: pathlib.Path):
        self.path = path; self.n = 0
        path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, kind: str, **kw):
        self.n += 1
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"n": self.n, "t": C.now(), "kind": kind, **kw}, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------------- 後端
class AdbDevice:
    kind = "adb"

    def __init__(self, serial: str | None, package: str | None, trace: Trace):
        self.serial = M.resolve_device(serial)
        self.package = package
        self.trace = trace
        self.clock0 = time.time()

    def now(self) -> float:
        return time.time() - self.clock0

    def wm_size(self) -> tuple[int, int]:
        out = M.adb(["shell", "wm", "size"], self.serial).stdout
        m = re.search(r"(\d+)x(\d+)", out)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    def screenshot(self, path: pathlib.Path) -> pathlib.Path:
        M.screenshot_to(self.serial, pathlib.Path(path))
        self.trace.add("screenshot", path=str(path), sha=C.sha_file(path)[:12])
        return pathlib.Path(path)

    def tap(self, x: int, y: int):
        M.adb(["shell", "input", "tap", str(x), str(y)], self.serial); self.trace.add("tap", x=x, y=y)

    def swipe(self, x1, y1, x2, y2, ms=300):
        M.adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms)], self.serial); self.trace.add("swipe", x1=x1, y1=y1, x2=x2, y2=y2)

    def key(self, name: str):
        M.adb(["shell", "input", "keyevent", f"KEYCODE_{name}"], self.serial); self.trace.add("key", name=name)

    def sleep(self, s: float):
        time.sleep(s); self.trace.add("sleep", s=s)

    def tick(self, dt: float = 0.5):
        time.sleep(dt)

    def wait_stable(self, out_dir: pathlib.Path, timeout=12.0, threshold=0.004) -> dict:
        r = M.wait_stable(self.serial, pathlib.Path(out_dir), timeout, 0.5, threshold)
        self.trace.add("wait_stable", **{k: v for k, v in r.items() if k != "last"}); return r

    def restart_app(self):
        if not self.package:
            raise C.PackError("pack 未宣告 package，無法 restart_app")
        M.adb(["shell", "am", "force-stop", self.package], self.serial); time.sleep(1.0)
        M.adb(["shell", "monkey", "-p", self.package, "-c", "android.intent.category.LAUNCHER", "1"], self.serial)
        self.trace.add("restart_app", package=self.package)

    def net(self, on: bool):
        M.adb(["shell", "svc", "wifi", "enable" if on else "disable"], self.serial)
        M.adb(["shell", "svc", "data", "enable" if on else "disable"], self.serial)
        self.trace.add("net", on=on)

    def logcat_crash(self) -> dict:
        return M.logcat_scan(self.serial, None, 3000)

    def foreground_ok(self) -> bool:
        if not self.package:
            return True
        out = M.adb(["shell", "dumpsys", "window"], self.serial).stdout
        m = re.search(r"mCurrentFocus=.*?\s(\S+)/", out)
        return bool(m and self.package in m.group(1))

    # fake 專用介面在 adb 上不存在
    truth = None
    fake_visual = None


class FakeDevice:
    kind = "fake"

    def __init__(self, trace: Trace, seed: int = 7, bugs: dict | None = None):
        from aiqa_fake_game import FakeGame, LAYOUT
        self.game = FakeGame(seed, bugs); self.layout = LAYOUT
        self.serial = "fake-0001"; self.package = "com.ark.demoslot"; self.trace = trace

    def now(self) -> float:
        return self.game.t

    def wm_size(self):
        return (1600, 900)

    def screenshot(self, path):
        path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        self.game.render(path); self.game.tick(0.5)
        self.trace.add("screenshot", path=str(path), t=self.game.t)
        return path

    def tap(self, x, y):
        self.game.tap(x, y); self.trace.add("tap", x=x, y=y)

    def swipe(self, *a, **k):
        self.trace.add("swipe")

    def key(self, name):
        self.game.key(name); self.trace.add("key", name=name)

    def sleep(self, s: float):
        self.game.tick(s); self.trace.add("sleep", s=s)

    def tick(self, dt=0.5):
        self.game.tick(dt)

    def wait_stable(self, out_dir, timeout=12.0, threshold=0.004) -> dict:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        t0 = self.game.t; n = 0; prev = None; streak = 0; last = None
        while self.game.t - t0 < timeout:
            n += 1
            cur = self.screenshot(out_dir / f"_stable_{n:02d}.png")
            if prev is not None:
                d = M.frame_diff(prev, cur)
                streak = streak + 1 if d < threshold else 0
                if streak >= 2:
                    self.trace.add("wait_stable", stable=True, frames=n)
                    return {"stable": True, "elapsed_s": round(self.game.t - t0, 2), "frames": n, "last": str(cur)}
            prev = last = cur
        self.trace.add("wait_stable", stable=False, frames=n)
        return {"stable": False, "elapsed_s": round(self.game.t - t0, 2), "frames": n, "last": str(last) if last else None}

    def restart_app(self):
        self.game.restart_app(); self.trace.add("restart_app")

    def net(self, on: bool):
        self.game.set_net(on); self.trace.add("net", on=on)

    def logcat_crash(self) -> dict:
        return {"crash": False, "fatal": [], "fatal_count": 0}

    def foreground_ok(self) -> bool:
        return self.game.foreground

    def truth(self, roi: str):
        return self.game.truth(roi)

    def fake_visual(self, q: str) -> dict:
        return self.game.visual(q)


def make_device(backend: str, trace: Trace, serial: str | None = None, package: str | None = None, seed: int = 7, bugs: dict | None = None):
    if backend == "fake":
        return FakeDevice(trace, seed, bugs)
    if backend == "adb":
        return AdbDevice(serial, package, trace)
    raise C.PackError(f"未知 backend {backend}")


# ---------------------------------------------------------------- 定位 / 畫面偵測
def locate(pack: dict, ref: str, screen_img: pathlib.Path | None) -> dict:
    """btn:x → {x, y, by}。模板命中優先，其次 pack 固定座標。"""
    t = C.pack_target(pack, ref)
    tpl = t.get("template")
    if tpl and screen_img and pathlib.Path(tpl).exists():
        r = M.locate_template(screen_img, pathlib.Path(tpl), float(t.get("threshold", 0.85)))
        if r["found"]:
            return {"x": r["center"][0], "y": r["center"][1], "by": "template", "score": r["score"]}
    if t.get("xy"):
        return {"x": int(t["xy"][0]), "y": int(t["xy"][1]), "by": "xy", "score": None}
    raise C.PackError(f"{ref} 無法定位（模板未命中且無 xy）")


def detect_screen(pack: dict, screen_img: pathlib.Path) -> dict:
    """依 screens[*].template 比對；命中者以 priority（彈窗/錯誤畫面設高）再 score 排序；都未命中 → unknown。"""
    hits, best_any = [], {"screen": "unknown", "score": 0.0}
    for name, s in (pack.get("screens") or {}).items():
        tpl = s.get("template")
        if not tpl or not pathlib.Path(tpl).exists():
            continue
        r = M.locate_template(screen_img, pathlib.Path(tpl), float(s.get("threshold", 0.85)))
        if r["score"] > best_any["score"]:
            best_any = {"screen": "unknown", "score": r["score"], "candidate": name}
        if r["found"]:
            hits.append((int(s.get("priority", 0)), r["score"], name))
    if hits:
        pr, sc, name = sorted(hits, reverse=True)[0]
        return {"screen": name, "score": sc, "priority": pr, "hits": [h[2] for h in hits]}
    return best_any


# ---------------------------------------------------------------- 讀值
def read_roi(dev, pack: dict, roi_name: str, screen_img: pathlib.Path, out_dir: pathlib.Path, engine: str, oracle: str, llm=None) -> dict:
    """engine: fake（裝置 ground truth）| tesseract | llm。輸出 {value, text, engine, confidence, crop}。"""
    rect = C.pack_target(pack, f"roi:{roi_name}")["rect"]
    crop = M.crop_zoom(screen_img, rect, 3.0, out_dir / f"roi-{roi_name}-{int(dev.now() * 10):06d}.png")
    if engine == "fake":
        if dev.truth is None:
            raise C.PackError("fake reader 只能配 fake backend")
        v = dev.truth(roi_name)
        return {"value": v, "text": str(v), "engine": "fake", "confidence": 1.0, "crop": crop["path"]}
    if engine == "tesseract":
        r = M.ocr_image(pathlib.Path(crop["path"]), digits=(oracle == "ocr_number"))
        val = r["number"] if oracle == "ocr_number" else r["text"]
        return {"value": val, "text": r["text"], "engine": "tesseract", "confidence": 0.9 if val not in (None, "") else 0.0, "crop": crop["path"]}
    if engine == "llm":
        if llm is None:
            raise C.PackError("llm reader 需要 adapter")
        res = llm.read(pathlib.Path(crop["path"]), roi_name, oracle)
        return {**res, "engine": "llm", "crop": crop["path"]}
    if engine == "dual":  # tesseract + llm 雙讀，不一致 → None（→ NEEDS_HUMAN），寧可不判
        t = read_roi(dev, pack, roi_name, screen_img, out_dir, "tesseract", oracle, llm)
        l = read_roi(dev, pack, roi_name, screen_img, out_dir, "llm", oracle, llm)
        agree = (t["value"] == l["value"]) if oracle != "ocr_number" else (t["value"] is not None and l["value"] is not None and abs(float(t["value"]) - float(l["value"])) < 1e-6)
        return {"value": t["value"] if agree else None, "text": f"tesseract={t['text']} llm={l['text']}", "engine": "dual",
                "confidence": 0.95 if agree else 0.0, "crop": crop["path"]}
    raise C.PackError(f"未知 reader engine {engine}")


def visual(dev, question: str, screen_img: pathlib.Path, engine: str, llm=None) -> dict:
    if engine == "fake":
        return dev.fake_visual(question)
    if engine == "llm" and llm is not None:
        return llm.visual(screen_img, question)
    return {"answer": None, "confidence": 0.0, "detail": f"visual engine {engine} unavailable"}
