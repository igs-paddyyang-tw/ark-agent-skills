#!/usr/bin/env python3
"""aiqa_macro — 按鍵精靈式腳本：準備期用眼（截圖 / 錄製 / 建座標表），執行期只做確定性的點座標 + 檢查點。

子命令:
  record  --game g [--machine m] --out m.yaml [--duration 60]     用 adb getevent 錄人手的點擊（時間、裝置座標），存成 macro 草稿
  replay  --macro m.yaml [--backend adb|fake] [--out artifacts/macro] [--device SERIAL] [--dry-run]
  lint    --macro m.yaml                                            DSL 守門（步驟合法、目標存在於 pack、解析度宣告）
  explain --macro m.yaml                                            渲染成人讀 SOP 步驟（給測試員照做 / 給 AI 當參考）

macro.yaml:
  macro: panda-enter-spin
  game: ghy            # 座標與 target 解析用的 gamepack
  machine: panda
  resolution: {width: 720, height: 1280}     # 座標唯一基準 = 裝置 wm size；不符拒跑
  vars: {spins: 3}
  steps:
    - tap: "btn:machine_panda"       # 或 tap: [x, y]
    - wait_stable: {timeout: 8}
    - if_screen: {screen: popup_daily, then: [{tap: "btn:close"}, {wait_stable: {timeout: 3}}]}
    - checkpoint: {screen: main_game}          # 模板比對；不符 → FAIL 停
    - loop: {times: "{spins}", steps: [{tap: "btn:spin"}, {wait_stable: {timeout: 12}}, {shot: spin}]}
    - wait_pixel: {xy: [650, 1200], rgb: [60, 180, 90], tol: 30, timeout: 10}
    - assert_pixel: {xy: [650, 1200], rgb: [60, 180, 90], tol: 30}
    - ocr: {roi: "roi:bet", name: bet, digits: true}
    - key: BACK
    - sleep: 1.0
    - shot: after_back
執行期不呼叫 LLM；每個 checkpoint / shot 留圖；結果 summary.json（ok, steps, fails, elapsed, ocr 值）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiqa_common as C  # noqa: E402
import aiqa_device as D  # noqa: E402
import ark_mobile_adb as M  # noqa: E402

STEP_KEYS = {"tap", "swipe", "key", "sleep", "wait_stable", "wait_screen", "wait_pixel", "checkpoint", "assert_pixel", "if_screen", "loop", "shot", "ocr", "note", "restart_app", "net"}


class MacroFail(Exception):
    pass


def load_macro(p: pathlib.Path) -> dict:
    m = C.yaml_load(p)
    if not isinstance(m, dict) or "steps" not in m:
        raise MacroFail("macro 需含 steps")
    return m


# ---------------------------------------------------------------- lint
def lint(m: dict, pack: dict | None) -> list[dict]:
    v = []
    add = lambda sev, rule, msg: v.append({"severity": sev, "rule": rule, "message": msg})  # noqa: E731
    for k in ("macro", "game", "resolution", "steps"):
        if k not in m:
            add("error", "MC-FIELDS", f"缺 {k}")
    res = m.get("resolution") or {}
    if not (res.get("width") and res.get("height")):
        add("error", "MC-RES", "resolution 需 width/height（座標唯一基準）")
    if pack and res and (res.get("width"), res.get("height")) != ((pack.get("resolution") or {}).get("width"), (pack.get("resolution") or {}).get("height")):
        add("error", "MC-RES", f"macro 解析度 {res} ≠ pack {pack.get('resolution')}")

    def walk(steps, path):
        if not isinstance(steps, list):
            add("error", "MC-STEPS", f"{path} 需為 list"); return
        for i, st in enumerate(steps):
            if not isinstance(st, dict) or len(st) != 1:
                add("error", "MC-STEP", f"{path}[{i}] 每步一個 key"); continue
            k, val = next(iter(st.items()))
            if k not in STEP_KEYS:
                add("error", "MC-STEP", f"{path}[{i}] 未知步驟 {k}")
            if k == "tap":
                if isinstance(val, str):
                    if pack:
                        try:
                            C.pack_target(pack, val)
                        except C.PackError as e:
                            add("error", "MC-TARGET", f"{path}[{i}] {e}")
                    elif not val.startswith("btn:"):
                        add("error", "MC-TARGET", f"{path}[{i}] tap 字串需 btn:<name>")
                elif not (isinstance(val, list) and len(val) == 2):
                    add("error", "MC-TARGET", f"{path}[{i}] tap 需 btn:<name> 或 [x,y]")
                else:
                    if res and (val[0] > res["width"] or val[1] > res["height"]):
                        add("error", "MC-COORD", f"{path}[{i}] 座標 {val} 超出 resolution（拿縮圖座標來點？）")
            if k in ("checkpoint", "wait_screen") and pack and val.get("screen") not in (pack.get("screens") or {}):
                add("error" if pack.get("calibrated") else "warn", "MC-SCREEN", f"{path}[{i}] screen {val.get('screen')} 未在 pack 定義")
            if k == "if_screen":
                walk(val.get("then", []), f"{path}[{i}].then"); walk(val.get("else", []), f"{path}[{i}].else")
            if k == "loop":
                walk(val.get("steps", []), f"{path}[{i}].steps")
            if k == "ocr" and pack and str(val.get("roi", "")).replace("roi:", "") not in (pack.get("rois") or {}):
                add("error" if pack.get("calibrated") else "warn", "MC-ROI", f"{path}[{i}] roi {val.get('roi')} 未定義")
    walk(m.get("steps", []), "steps")
    if m.get("steps") and not any(next(iter(s)) in ("checkpoint", "assert_pixel", "wait_screen", "ocr") for s in _flat(m["steps"])):
        add("warn", "MC-BLIND", "整支腳本沒有任何檢查點 → 全盲點；至少在關鍵節點放 checkpoint / assert_pixel")
    return v


def _flat(steps):
    for s in steps:
        yield s
        k, v = next(iter(s.items()))
        if k == "loop":
            yield from _flat(v.get("steps", []))
        if k == "if_screen":
            yield from _flat(v.get("then", [])); yield from _flat(v.get("else", []))


# ---------------------------------------------------------------- replay
class Player:
    def __init__(self, dev, pack: dict | None, out: pathlib.Path, vars_: dict, dry: bool):
        self.dev, self.pack, self.out, self.vars, self.dry = dev, pack, out, vars_, dry
        self.n = 0; self.fails: list[dict] = []; self.values: dict = {}; self.log: list[dict] = []
        out.mkdir(parents=True, exist_ok=True)

    def _v(self, x):
        if isinstance(x, str) and x.startswith("{") and x.endswith("}"):
            return self.vars[x[1:-1]]
        return x

    def shot(self, tag) -> pathlib.Path:
        self.n += 1
        p = self.out / f"{self.n:03d}-{re.sub(r'[^A-Za-z0-9_-]+', '_', str(tag))[:24]}.png"
        return self.dev.screenshot(p)

    def xy(self, target):
        if isinstance(target, list):
            return int(target[0]), int(target[1]), "xy"
        if not self.pack:
            raise MacroFail(f"tap {target} 需要 gamepack 解析")
        loc = D.locate(self.pack, target, self.shot("locate"))
        return loc["x"], loc["y"], loc["by"]

    def run(self, steps):
        for st in steps:
            k, val = next(iter(st.items()))
            t0 = time.time()
            try:
                getattr(self, "s_" + k)(val)
                self.log.append({"step": k, "arg": val, "ok": True, "ms": round((time.time() - t0) * 1000)})
            except MacroFail as e:
                self.fails.append({"step": k, "arg": val, "error": str(e)}); self.log.append({"step": k, "arg": val, "ok": False, "error": str(e)})
                raise

    def s_note(self, v): pass
    def s_tap(self, v):
        x, y, by = self.xy(v)
        if not self.dry:
            self.dev.tap(x, y); self.dev.tick(0.3)
        self.log.append({"tap": [x, y], "by": by})
    def s_swipe(self, v):
        if not self.dry:
            self.dev.swipe(*v.get("from"), *v.get("to"), int(v.get("ms", 300)))
    def s_key(self, v):
        if not self.dry:
            self.dev.key(str(v)); self.dev.tick(0.3)
    def s_sleep(self, v): self.dev.sleep(float(self._v(v)))
    def s_wait_stable(self, v):
        r = self.dev.wait_stable(self.out / "_stable", float(v.get("timeout", 10)), float(v.get("threshold", 0.004)))
        if not r["stable"] and v.get("strict"):
            raise MacroFail("畫面未穩定")
    def s_wait_screen(self, v):
        t0 = self.dev.now()
        while self.dev.now() - t0 <= float(v.get("timeout", 10)):
            if D.detect_screen(self.pack, self.shot("wait"))["screen"] == v["screen"]:
                return
            self.dev.tick(0.5)
        raise MacroFail(f"等 screen:{v['screen']} 超時")
    def s_checkpoint(self, v):
        img = self.shot(f"cp_{v.get('screen', 'x')}")
        got = D.detect_screen(self.pack, img)
        if got["screen"] != v["screen"]:
            raise MacroFail(f"checkpoint 期望 {v['screen']}，實際 {got['screen']}（{img.name}）")
    def s_if_screen(self, v):
        got = D.detect_screen(self.pack, self.shot("if"))["screen"]
        self.run(v.get("then", []) if got == v["screen"] else v.get("else", []))
    def s_loop(self, v):
        for _ in range(int(self._v(v.get("times", 1)))):
            self.run(v.get("steps", []))
    def s_shot(self, v): self.shot(v)
    def s_wait_pixel(self, v):
        t0 = self.dev.now()
        while self.dev.now() - t0 <= float(v.get("timeout", 10)):
            if M.color_close(M.pixel_at(self.shot("px"), *v["xy"]), v["rgb"], int(v.get("tol", 30))):
                return
            self.dev.tick(float(v.get("interval", 0.3)))
        raise MacroFail(f"wait_pixel {v['xy']} 未變成 {v['rgb']}")
    def s_assert_pixel(self, v):
        got = M.pixel_at(self.shot("assert"), *v["xy"])
        if not M.color_close(got, v["rgb"], int(v.get("tol", 30))):
            raise MacroFail(f"assert_pixel {v['xy']} 期望 {v['rgb']} 實際 {got}")
    def s_ocr(self, v):
        roi = str(v["roi"]).replace("roi:", "")
        engine = v.get("engine") or ("fake" if self.dev.kind == "fake" else "tesseract")
        r = D.read_roi(self.dev, self.pack, roi, self.shot(f"ocr_{roi}"), self.out, engine, "ocr_number" if v.get("digits", True) else "text")
        self.values[v.get("name", roi)] = r["value"]
        if "expect" in v and r["value"] != v["expect"]:
            raise MacroFail(f"ocr {roi} 期望 {v['expect']} 讀到 {r['value']}")
    def s_restart_app(self, v):
        if not self.dry:
            self.dev.restart_app(); self.dev.tick(2)
    def s_net(self, v):
        if not self.dry:
            self.dev.net(str(v) == "restore")


def replay(m: dict, backend: str, device: str | None, out: pathlib.Path, dry: bool) -> dict:
    pack = C.load_pack(m["game"], m.get("machine")) if m.get("game") else None
    trace = D.Trace(out / "trace.jsonl")
    if backend == "fake":
        dev = D.make_device("fake", trace)
    else:
        dev = D.make_device("adb", trace, device, (pack or {}).get("package"))
        w, h = dev.wm_size(); res = m["resolution"]
        if (w, h) != (res["width"], res["height"]):
            raise MacroFail(f"裝置 {w}x{h} ≠ macro resolution {res}（座標基準不符，拒跑）")
    pl = Player(dev, pack, out, dict(m.get("vars") or {}), dry)
    t0 = time.time(); ok = True
    try:
        pl.run(m["steps"])
    except MacroFail:
        ok = False
    summary = {"macro": m.get("macro"), "ok": ok, "steps": len(pl.log), "fails": pl.fails, "values": pl.values, "shots": pl.n,
               "elapsed_s": round(time.time() - t0, 2), "backend": backend, "device": dev.serial, "out": str(out), "dry_run": dry}
    C.atomic_write(out / "summary.json", json.dumps(summary, ensure_ascii=False, indent=1, default=str))
    C.atomic_write(out / "log.json", json.dumps(pl.log, ensure_ascii=False, indent=1, default=str))
    return summary


# ---------------------------------------------------------------- record（getevent → taps）
def parse_getevent(text: str, abs_max: tuple[int, int], device_wh: tuple[int, int]) -> list[dict]:
    """解析 `getevent -lt` 輸出成 tap 列表（裝置座標）。ABS_MT_POSITION_X/Y 原始值以 abs_max 換算到 wm size。"""
    taps, cur = [], {}
    for line in text.splitlines():
        m = re.match(r"\[\s*([\d.]+)\]\s+\S+:\s+(\S+)\s+(\S+)\s+(\S+)", line.strip())
        if not m:
            continue
        ts, typ, code, val = m.groups()
        if code == "ABS_MT_POSITION_X":
            cur["x"] = int(val, 16)
        elif code == "ABS_MT_POSITION_Y":
            cur["y"] = int(val, 16)
        elif code == "BTN_TOUCH" and val == "DOWN":
            cur["t0"] = float(ts)
        elif (code == "BTN_TOUCH" and val == "UP") or (code == "ABS_MT_TRACKING_ID" and val == "ffffffff"):
            if "x" in cur and "y" in cur:
                x = round(cur["x"] * device_wh[0] / max(1, abs_max[0])); y = round(cur["y"] * device_wh[1] / max(1, abs_max[1]))
                taps.append({"t": cur.get("t0", float(ts)), "x": x, "y": y, "hold_ms": round((float(ts) - cur.get("t0", float(ts))) * 1000)})
            cur = {}
    return taps


def taps_to_macro(taps: list[dict], name: str, game: str, machine: str | None, wh: tuple[int, int]) -> dict:
    steps, prev = [], None
    for t in taps:
        if prev is not None:
            gap = round(t["t"] - prev, 1)
            if gap >= 0.8:
                steps.append({"wait_stable": {"timeout": min(15, max(2, round(gap + 2)))}})
        steps.append({"tap": [t["x"], t["y"]]}); prev = t["t"]
    steps.append({"shot": "end"})
    return {"macro": name, "game": game, "machine": machine, "resolution": {"width": wh[0], "height": wh[1]}, "recorded_at": C.now(),
            "note": "錄製草稿：把 [x,y] 換成 btn:<name>、在關鍵節點加 checkpoint / assert_pixel / ocr，再 lint",
            "steps": steps}


def record(game: str, machine: str | None, device: str | None, duration: float) -> dict:
    serial = M.resolve_device(device)
    wh = M.device_size(serial)
    p = M.adb(["shell", "getevent", "-p"], serial).stdout
    mx = re.search(r"0035.*?max (\d+)", p); my = re.search(r"0036.*?max (\d+)", p)
    abs_max = (int(mx.group(1)) if mx else wh[0], int(my.group(1)) if my else wh[1])
    try:
        cp = subprocess.run([M.adb_path(), "-s", serial, "shell", "getevent", "-lt"], capture_output=True, text=True, timeout=duration)
        raw = cp.stdout
    except subprocess.TimeoutExpired as e:
        raw = (e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else e.stdout) or ""
    taps = parse_getevent(raw, abs_max, wh)
    return {"serial": serial, "device_size": wh, "abs_max": abs_max, "taps": taps}


# ---------------------------------------------------------------- explain
def explain(m: dict) -> str:
    L = [f"# SOP：{m.get('macro')}（{m.get('game')}/{m.get('machine') or '-'}，{m.get('resolution', {}).get('width')}x{m.get('resolution', {}).get('height')}）", ""]
    n = [0]

    def walk(steps, indent=""):
        for st in steps:
            k, v = next(iter(st.items())); n[0] += 1
            txt = {"tap": lambda: f"點 {v}", "key": lambda: f"按 {v}", "sleep": lambda: f"等 {v} 秒", "wait_stable": lambda: f"等畫面靜止（≤{v.get('timeout', 10)}s）",
                   "wait_screen": lambda: f"等到畫面 {v.get('screen')}", "checkpoint": lambda: f"✅ 檢查點：畫面應為 {v.get('screen')}",
                   "assert_pixel": lambda: f"✅ 檢查點：像素 {v.get('xy')} 應為 {v.get('rgb')}", "wait_pixel": lambda: f"等像素 {v.get('xy')} 變 {v.get('rgb')}",
                   "shot": lambda: f"📷 截圖 {v}", "ocr": lambda: f"讀 {v.get('roi')} → {v.get('name', '')}" + (f"（應為 {v['expect']}）" if 'expect' in v else ""),
                   "if_screen": lambda: f"若畫面是 {v.get('screen')}：", "loop": lambda: f"重複 {v.get('times')} 次：", "note": lambda: f"📝 {v}",
                   "restart_app": lambda: "重啟 app", "net": lambda: f"網路 {v}", "swipe": lambda: f"滑 {v.get('from')}→{v.get('to')}"}.get(k, lambda: f"{k} {v}")()
            L.append(f"{indent}{n[0]}. {txt}")
            if k == "if_screen":
                walk(v.get("then", []), indent + "    ")
                if v.get("else"):
                    L.append(f"{indent}   否則："); walk(v["else"], indent + "    ")
            if k == "loop":
                walk(v.get("steps", []), indent + "    ")
    walk(m.get("steps", []))
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="按鍵精靈式 macro")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("record"); s.add_argument("--game", required=True); s.add_argument("--machine"); s.add_argument("--out", required=True)
    s.add_argument("--duration", type=float, default=60); s.add_argument("--device"); s.add_argument("--name", default="recorded")
    s = sub.add_parser("replay"); s.add_argument("--macro", required=True); s.add_argument("--backend", default="adb", choices=["adb", "fake"])
    s.add_argument("--device"); s.add_argument("--out", default="artifacts/macro"); s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("lint"); s.add_argument("--macro", required=True)
    s = sub.add_parser("explain"); s.add_argument("--macro", required=True); s.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "record":
        try:
            r = record(a.game, a.machine, a.device, a.duration)
        except M.ArkMobileError as e:
            C.fail(e.code, str(e), e.hint)
        m = taps_to_macro(r["taps"], a.name, a.game, a.machine, r["device_size"])
        C.atomic_write(pathlib.Path(a.out), C.yaml_dump(m))
        C.emit({"out": a.out, "taps": len(r["taps"]), "device_size": r["device_size"], "next": f"python aiqa_macro.py lint --macro {a.out}"})
    m = load_macro(pathlib.Path(a.macro))
    pack = None
    if m.get("game"):
        try:
            pack = C.load_pack(m["game"], m.get("machine"))
        except C.PackError as e:
            C.fail("BAD_INPUT", str(e), "")
    if a.cmd == "lint":
        v = lint(m, pack); errs = [x for x in v if x["severity"] == "error"]
        data = {"macro": m.get("macro"), "errors": errs, "warnings": [x for x in v if x["severity"] == "warn"]}
        if errs:
            C.fail("GATE_BLOCKED", f"{len(errs)} 個 error", "修 macro 後重跑", data=data)
        C.emit(data)
    if a.cmd == "explain":
        txt = explain(m)
        if a.out:
            C.atomic_write(pathlib.Path(a.out), txt)
        C.emit({"sop": txt, "out": a.out})
    if a.cmd == "replay":
        errs = [x for x in lint(m, pack) if x["severity"] == "error"]
        if errs:
            C.fail("GATE_BLOCKED", "macro lint 未過", "", data={"errors": errs})
        out = pathlib.Path(a.out) / f"{m.get('macro')}-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            with C.Timer() as t:
                r = replay(m, a.backend, a.device, out, a.dry_run)
        except (MacroFail, M.ArkMobileError, C.PackError) as e:
            C.fail("BAD_INPUT" if isinstance(e, (MacroFail, C.PackError)) else getattr(e, "code", "QUERY_FAILED"), str(e), "")
        if r["ok"]:
            C.emit(r, {"elapsed_ms": t.elapsed_ms})
        C.fail("QUERY_FAILED", f"macro 失敗：{r['fails'][0]['error'] if r['fails'] else '?'}", f"看 {out}/summary.json 與截圖", data=r)


if __name__ == "__main__":
    main()
