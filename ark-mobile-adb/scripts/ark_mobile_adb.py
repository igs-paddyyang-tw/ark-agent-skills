#!/usr/bin/env python3
"""
ark-mobile-adb: Android / BlueStacks 裝置層 CLI（adb 包裝）。

    Agent -> this CLI -> adb -> Android / BlueStacks

Python 3.10+，核心只用標準庫；Pillow / numpy / opencv / tesseract 為選配（crop / wait-stable / locate / ocr）。
--json 時 stdout 為單一 envelope：{"success", "contract": "1", "data", "error"{code,message,hint}}
exit：0 ok · 2 BAD_INPUT · 3 GATE_BLOCKED · 5 CONN_FAILED（無裝置 / offline）· 7 TIMEOUT · 8 DRIVER_MISSING（adb / 選配套件）
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence


CONTRACT = "1"
SKILL_VERSION = "2.1.0"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "CONN_FAILED": 5, "QUERY_FAILED": 6, "TIMEOUT": 7, "DRIVER_MISSING": 8}


class ArkMobileError(RuntimeError):
    def __init__(self, message: str, code: str = "QUERY_FAILED", hint: str = ""):
        super().__init__(message)
        self.code, self.hint = code, hint


def emit(data, json_mode: bool = False):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if json_mode:
        print(json.dumps({"success": True, "contract": CONTRACT, "data": data, "meta": {"skill_version": SKILL_VERSION}},
                         ensure_ascii=False))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def project_config() -> Path:
    return Path.cwd() / ".ark-mobile.json"


def load_config() -> dict:
    p = project_config()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ArkMobileError(f"Invalid {p}: {e}")


def find_adb() -> str | None:
    candidates: list[Path] = []

    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(var)
        if value:
            candidates.append(Path(value) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))

    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Android" / "sdk" / "platform-tools" / "adb")

    for p in candidates:
        if p.exists():
            return str(p)
    return shutil.which("adb")


def run_cmd(args: Sequence[str], timeout: float = 30, capture=True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            list(args),
            text=True,
            capture_output=capture,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:
        raise ArkMobileError(f"Command not found: {args[0]}", "DRIVER_MISSING") from e
    except subprocess.TimeoutExpired as e:
        raise ArkMobileError(f"Command timed out after {timeout}s: {' '.join(args)}", "TIMEOUT") from e


def adb_path() -> str:
    path = find_adb()
    if not path:
        raise ArkMobileError("adb not found", "DRIVER_MISSING",
                             "安裝 Android Platform Tools；設 ANDROID_HOME=<sdk 根目錄>（platform-tools 的上一層）或加入 PATH 後開新終端機")
    return path


_RECONNECTED = {"n": 0}


def try_reconnect(device: str | None) -> bool:
    """BlueStacks 待機後 adbd 常 offline：對 host:port 型 serial 自動 `adb connect` 一次（R5 連線不穩）。"""
    target = device if (device and re.match(r"^[\w.]+:\d+$", device)) else load_config().get("connect")
    if not target or _RECONNECTED["n"] >= 3:
        return False
    _RECONNECTED["n"] += 1
    run_cmd([adb_path(), "disconnect", target], timeout=10)
    cp = run_cmd([adb_path(), "connect", target], timeout=15)
    time.sleep(1.0)
    return "connected" in (cp.stdout or "").lower()


def adb(args: Sequence[str], device: str | None = None, timeout: float = 30, _retry: bool = True) -> subprocess.CompletedProcess:
    cmd = [adb_path()]
    if device:
        cmd += ["-s", device]
    cmd += list(args)
    cp = run_cmd(cmd, timeout=timeout)
    if cp.returncode != 0:
        stderr = (cp.stderr or "").strip()
        stdout = (cp.stdout or "").strip()
        detail = stderr or stdout or f"exit code {cp.returncode}"
        if _retry and re.search(r"offline|not found|closed|no devices", detail, re.I) and try_reconnect(device):
            return adb(args, device, timeout, _retry=False)
        code = "CONN_FAILED" if re.search(r"offline|not found|closed|no devices", detail, re.I) else "QUERY_FAILED"
        raise ArkMobileError(f"adb failed: {' '.join(cmd)}\n{detail}", code, "connect 127.0.0.1:<port> 後 doctor；或在 .ark-mobile.json 加 \"connect\" 讓 CLI 自動重連")
    return cp


def shell_chain(device: str, commands: Sequence[str], timeout: float = 60) -> str:
    """一次 adb shell 串多個指令（R1：5 次獨立 shell 3.39s → 1 次 0.76s）。以 '; ' 串接，回合併 stdout。"""
    return adb(["shell", " ; ".join(commands)], device, timeout).stdout


def parse_devices(output: str) -> list[dict]:
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        serial_state = parts[0].split("\t")
        serial = serial_state[0]
        state = serial_state[1] if len(serial_state) > 1 else (parts[1] if len(parts) > 1 else "unknown")
        attrs = {}
        for item in parts[2:]:
            if ":" in item:
                k, v = item.split(":", 1)
                attrs[k] = v
        rows.append({"serial": serial, "state": state, **attrs})
    return rows


def list_devices() -> list[dict]:
    return parse_devices(adb(["devices", "-l"]).stdout)


def resolve_device(explicit: str | None) -> str:
    cfg = load_config()
    configured = cfg.get("device")
    requested = explicit or os.environ.get("ARK_MOBILE_DEVICE") or configured

    devices = [d for d in list_devices() if d["state"] == "device"]

    if requested:
        if any(d["serial"] == requested for d in devices):
            return requested
        raise ArkMobileError(f"Requested device '{requested}' is not in device state. Available: {[d['serial'] for d in devices]}",
                             "CONN_FAILED", "adb connect 127.0.0.1:<BlueStacks 顯示的埠>；offline 時 adb kill-server && adb start-server")

    if len(devices) == 1:
        return devices[0]["serial"]

    if not devices:
        raise ArkMobileError("No Android device in 'device' state", "CONN_FAILED", "connect 127.0.0.1:<port> 後跑 doctor")
    raise ArkMobileError("Multiple Android devices found. Specify one with --device SERIAL: " + ", ".join(d["serial"] for d in devices),
                         "BAD_INPUT", "同一台常有兩個 serial；用 `use SERIAL` 固定，之後全程同一個")


def require_positive_int(value: str, name: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{name} must be an integer")
    if n < 0:
        raise argparse.ArgumentTypeError(f"{name} must be >= 0")
    return n


def cmd_doctor(args):
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "adb": None,
        "adb_version": None,
        "devices": [],
        "selected_device": None,
        "screen_size": None,
        "status": "error",
    }
    path = find_adb()
    if not path:
        report["error"] = "adb not found"
        emit(report, args.json)
        return 1
    report["adb"] = path

    try:
        ver = run_cmd([path, "version"])
        report["adb_version"] = (ver.stdout or ver.stderr).strip().splitlines()[0]
        report["devices"] = list_devices()
        connected = [d for d in report["devices"] if d["state"] == "device"]
        if len(connected) == 1:
            serial = connected[0]["serial"]
            report["selected_device"] = serial
            size = adb(["shell", "wm", "size"], serial).stdout.strip()
            report["screen_size"] = size
        elif len(connected) > 1:
            report["device_selection"] = "multiple devices; specify --device"
        else:
            report["device_selection"] = "no device in device state"
        report["status"] = "ok"
    except Exception as e:
        report["error"] = str(e)
    emit(report, args.json)
    return 0 if report["status"] == "ok" else 1


def cmd_devices(args):
    emit(list_devices(), args.json)
    return 0


def cmd_connect(args):
    cp = adb(["connect", args.target], timeout=15)
    result = {"target": args.target, "output": cp.stdout.strip()}
    emit(result, args.json)
    return 0


def cmd_disconnect(args):
    cp = adb(["disconnect", args.target], timeout=15)
    result = {"target": args.target, "output": cp.stdout.strip()}
    emit(result, args.json)
    return 0


def cmd_screenshot(args):
    device = resolve_device(args.device)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    screenshot_to(device, out)
    if getattr(args, "crop", None):
        rect = [int(v) for v in args.crop.split(",")]
        crop_zoom(out, rect, args.zoom or 1, out.with_name(out.stem + "-crop" + out.suffix))

    size = None
    try:
        from PIL import Image  # optional, never required
        with Image.open(out) as im:
            size = list(im.size)
    except Exception:
        pass

    emit({"device": device, "path": str(out.resolve()), "size": size}, args.json)
    return 0


def cmd_tap(args):
    device = resolve_device(args.device)
    if getattr(args, "basis", None):
        bw, bh = (int(v) for v in args.basis.lower().split("x"))
        args.x, args.y = to_device_xy(args.x, args.y, (bw, bh), device_size(device))
    adb(["shell", "input", "tap", str(args.x), str(args.y)], device)
    emit({"device": device, "action": "tap", "x": args.x, "y": args.y}, args.json)
    return 0


def cmd_swipe(args):
    device = resolve_device(args.device)
    adb(["shell", "input", "swipe", str(args.x1), str(args.y1), str(args.x2), str(args.y2), str(args.duration)], device)
    emit({"device": device, "action": "swipe", "from": [args.x1, args.y1], "to": [args.x2, args.y2], "duration_ms": args.duration}, args.json)
    return 0


def cmd_long_press(args):
    device = resolve_device(args.device)
    adb(["shell", "input", "swipe", str(args.x), str(args.y), str(args.x), str(args.y), str(args.duration)], device)
    emit({"device": device, "action": "long-press", "x": args.x, "y": args.y, "duration_ms": args.duration}, args.json)
    return 0


def cmd_text(args):
    device = resolve_device(args.device)
    # adb shell input text uses %s for spaces.
    value = args.value.replace("%", "%25").replace(" ", "%s")
    adb(["shell", "input", "text", value], device)
    emit({"device": device, "action": "text", "length": len(args.value)}, args.json)
    return 0


def cmd_keyevent(args):
    device = resolve_device(args.device)
    key = args.key.upper()
    if not key.startswith("KEYCODE_"):
        key = "KEYCODE_" + key
    adb(["shell", "input", "keyevent", key], device)
    emit({"device": device, "action": "keyevent", "key": key}, args.json)
    return 0


def cmd_simple_key(args, key):
    args.key = key
    return cmd_keyevent(args)


def cmd_launch(args):
    device = resolve_device(args.device)
    # monkey is broadly available and avoids requiring activity name.
    adb(["shell", "monkey", "-p", args.package, "1"], device, timeout=30)
    emit({"device": device, "action": "launch", "package": args.package}, args.json)
    return 0


def cmd_stop(args):
    device = resolve_device(args.device)
    adb(["shell", "am", "force-stop", args.package], device)
    emit({"device": device, "action": "stop", "package": args.package}, args.json)
    return 0


def cmd_clear_data(args):
    device = resolve_device(args.device)
    out = adb(["shell", "pm", "clear", args.package], device).stdout.strip()
    emit({"device": device, "action": "clear-data", "package": args.package, "output": out}, args.json)
    return 0


def cmd_packages(args):
    device = resolve_device(args.device)
    cmd = ["shell", "pm", "list", "packages"]
    if args.third_party:
        cmd.append("-3")
    out = adb(cmd, device).stdout
    packages = [x.strip() for x in out.splitlines() if x.strip()]
    emit({"device": device, "packages": packages}, args.json)
    return 0


def cmd_install(args):
    device = resolve_device(args.device)
    apk = str(Path(args.apk).resolve())
    if not Path(apk).exists():
        raise ArkMobileError(f"APK not found: {apk}")
    out = adb(["install", "-r", apk], device, timeout=args.timeout).stdout.strip()
    emit({"device": device, "apk": apk, "output": out}, args.json)
    return 0


def cmd_foreground(args):
    device = resolve_device(args.device)
    out = adb(["shell", "dumpsys", "window"], device).stdout
    matches = re.findall(r"mCurrentFocus=Window\{[^}]*\s([^/]+)/", out)
    focus = matches[-1] if matches else None
    if not focus:
        # Newer Android variants often expose mFocusedApp instead.
        m = re.search(r"mFocusedApp=.*?\s([A-Za-z0-9._$]+/[A-Za-z0-9._$]+)", out)
        focus = m.group(1) if m else None
    emit({"device": device, "foreground": focus, "raw": out if args.raw else None}, args.json)
    return 0


def cmd_ui_dump(args):
    device = resolve_device(args.device)
    remote = "/sdcard/window_dump.xml"
    adb(["shell", "uiautomator", "dump", remote], device, timeout=30)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pull = run_cmd([adb_path(), "-s", device, "pull", remote, str(out)], timeout=30)
    if pull.returncode != 0:
        raise ArkMobileError(pull.stderr.strip() or "adb pull failed")
    text = out.read_text(encoding="utf-8", errors="replace")
    emit({"device": device, "path": str(out.resolve()), "bytes": len(text.encode("utf-8")), "nodes": text.count("<node")}, args.json)
    return 0


def cmd_shell(args):
    device = resolve_device(args.device)
    cp = adb(["shell", *args.command], device, timeout=args.timeout)
    emit({"device": device, "stdout": cp.stdout, "stderr": cp.stderr}, args.json)
    return 0


def cmd_wait(args):
    time.sleep(args.seconds)
    emit({"waited_seconds": args.seconds}, args.json)
    return 0


# ---------------------------------------------------------------- v2 視覺輔助（選配套件）
def _pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        raise ArkMobileError("缺 Pillow", "DRIVER_MISSING", "pip install Pillow")


def _np():
    try:
        import numpy as np
        return np
    except ImportError:
        raise ArkMobileError("缺 numpy", "DRIVER_MISSING", "pip install numpy")


def screenshot_to(device: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    remote = "/sdcard/ark_mobile_adb_capture.png"
    adb(["shell", "screencap", "-p", remote], device)
    pull = run_cmd([adb_path(), "-s", device, "pull", remote, str(out)], timeout=30)
    if pull.returncode != 0:
        raise ArkMobileError(pull.stderr.strip() or "adb pull failed")
    return out


def crop_zoom(src: Path, rect: Sequence[int], zoom: float, out: Path) -> dict:
    Image = _pil()
    x, y, w, h = (int(v) for v in rect)
    with Image.open(src) as im:
        c = im.crop((x, y, x + w, y + h))
        if zoom and zoom != 1:
            c = c.resize((int(c.width * zoom), int(c.height * zoom)), Image.LANCZOS)
        out.parent.mkdir(parents=True, exist_ok=True)
        c.save(out)
        return {"path": str(out.resolve()), "size": [c.width, c.height], "rect": [x, y, w, h], "zoom": zoom}


def frame_diff(a: Path, b: Path, width: int = 160) -> float:
    Image = _pil(); np = _np()
    def load(p):
        with Image.open(p) as im:
            im = im.convert("L")
            im = im.resize((width, max(1, int(im.height * width / im.width))))
            return np.asarray(im, dtype=np.float32) / 255.0
    x, y = load(a), load(b)
    if x.shape != y.shape:
        return 1.0
    return float(np.abs(x - y).mean())


def wait_stable(device: str, out_dir: Path, timeout: float = 12.0, interval: float = 0.5, threshold: float = 0.004, stable_n: int = 3) -> dict:
    """連續 stable_n 張截圖差異 < threshold → 穩定。回最後一張路徑與耗時；超時回 stable=False（不 raise，讓呼叫端決定）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time(); prev = None; streak = 0; n = 0; last = None
    while time.time() - t0 < timeout:
        n += 1
        cur = screenshot_to(device, out_dir / f"_stable_{n:02d}.png")
        if prev is not None:
            d = frame_diff(prev, cur)
            streak = streak + 1 if d < threshold else 0
            if streak >= stable_n - 1:
                return {"stable": True, "elapsed_s": round(time.time() - t0, 2), "frames": n, "last": str(cur), "diff": round(d, 5)}
        prev, last = cur, cur
        time.sleep(interval)
    return {"stable": False, "elapsed_s": round(time.time() - t0, 2), "frames": n, "last": str(last) if last else None}


def locate_template(screen: Path, template: Path, threshold: float = 0.85) -> dict:
    """模板比對：優先 opencv；否則 numpy 正規化相關（較慢，限縮小圖）。回 {found, x, y, w, h, score, center}。"""
    Image = _pil(); np = _np()
    with Image.open(screen) as a, Image.open(template) as b:
        S = np.asarray(a.convert("L"), dtype=np.float32); T = np.asarray(b.convert("L"), dtype=np.float32)
    th, tw = T.shape
    try:
        import cv2
        res = cv2.matchTemplate(S, T, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        x, y = int(loc[0]), int(loc[1])
    except ImportError:
        # numpy 滑窗 NCC（步長 2，適合 ≤ 1600x900）
        step = 2
        Tn = (T - T.mean()) / (T.std() + 1e-6)
        best = (-1.0, 0, 0)
        for yy in range(0, S.shape[0] - th + 1, step):
            for xx in range(0, S.shape[1] - tw + 1, step):
                W = S[yy:yy + th, xx:xx + tw]
                sc = float((((W - W.mean()) / (W.std() + 1e-6)) * Tn).mean())
                if sc > best[0]:
                    best = (sc, xx, yy)
        score, x, y = best
    found = float(score) >= threshold
    return {"found": found, "score": round(float(score), 4), "x": x, "y": y, "w": int(tw), "h": int(th),
            "center": [x + tw // 2, y + th // 2] if found else None, "threshold": threshold}


def ocr_image(path: Path, digits: bool = False, lang: str = "eng") -> dict:
    """tesseract（系統指令）OCR；缺 tesseract → DRIVER_MISSING。digits=True 只認 0-9.,x"""
    exe = shutil.which("tesseract")
    if not exe:
        raise ArkMobileError("缺 tesseract", "DRIVER_MISSING", "安裝 tesseract-ocr（Windows: UB-Mannheim 版）並加入 PATH；或改用 llm reader")
    cmd = [exe, str(path), "stdout", "-l", lang, "--psm", "7" if digits else "6"]
    if digits:
        cmd += ["-c", "tessedit_char_whitelist=0123456789.,xX"]
    cp = run_cmd(cmd, timeout=30)
    text = (cp.stdout or "").strip()
    num = None
    m = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", text.replace(" ", ""))
    if m:
        try:
            num = float(m.group(0).replace(",", ""))
        except ValueError:
            num = None
    return {"text": text, "number": num, "engine": "tesseract"}


def logcat_scan(device: str, since: str | None = None, lines: int = 2000) -> dict:
    args = ["logcat", "-d", "-t", str(lines)] if not since else ["logcat", "-d", "-T", since]
    cp = adb(args, device, timeout=30)
    text = cp.stdout or ""
    fatal = [l for l in text.splitlines() if " F " in l[:40] or "FATAL EXCEPTION" in l or "ANR in" in l]
    return {"lines": len(text.splitlines()), "fatal": fatal[:20], "fatal_count": len(fatal), "crash": bool(fatal)}


def cmd_use(args):
    device = resolve_device(args.serial)
    project_config().write_text(json.dumps({"device": device}, ensure_ascii=False, indent=2), encoding="utf-8")
    emit({"device": device, "config": str(project_config())}, args.json)
    return 0


def cmd_screen_size(args):
    device = resolve_device(args.device)
    out = adb(["shell", "wm", "size"], device).stdout.strip()
    m = re.search(r"(\d+)x(\d+)", out)
    emit({"device": device, "raw": out, "width": int(m.group(1)) if m else None, "height": int(m.group(2)) if m else None}, args.json)
    return 0


def cmd_crop(args):
    rect = [int(v) for v in args.rect.split(",")]
    if len(rect) != 4:
        raise ArkMobileError("--rect 需 x,y,w,h", "BAD_INPUT")
    emit(crop_zoom(Path(args.src), rect, args.zoom, Path(args.out)), args.json)
    return 0


def cmd_wait_stable(args):
    device = resolve_device(args.device)
    r = wait_stable(device, Path(args.out_dir), args.timeout, args.interval, args.threshold)
    emit({"device": device, **r}, args.json)
    return 0 if r["stable"] else EXIT["TIMEOUT"]


def cmd_locate(args):
    r = locate_template(Path(args.screen), Path(args.template), args.threshold)
    emit(r, args.json)
    return 0 if r["found"] else EXIT["QUERY_FAILED"]


def cmd_ocr(args):
    emit(ocr_image(Path(args.image), args.digits, args.lang), args.json)
    return 0


def cmd_logcat(args):
    device = resolve_device(args.device)
    if args.clear:
        adb(["logcat", "-c"], device)
        emit({"device": device, "cleared": True}, args.json)
        return 0
    emit({"device": device, **logcat_scan(device, args.since, args.lines)}, args.json)
    return 0


def cmd_restart_app(args):
    device = resolve_device(args.device)
    adb(["shell", "am", "force-stop", args.package], device)
    time.sleep(args.gap)
    adb(["shell", "monkey", "-p", args.package, "-c", "android.intent.category.LAUNCHER", "1"], device)
    emit({"device": device, "package": args.package, "action": "restart"}, args.json)
    return 0


def cmd_net(args):
    device = resolve_device(args.device)
    on = args.state == "restore"
    adb(["shell", "svc", "wifi", "enable" if on else "disable"], device)
    adb(["shell", "svc", "data", "enable" if on else "disable"], device)
    emit({"device": device, "network": "restored" if on else "disconnected"}, args.json)
    return 0



# ---------------------------------------------------------------- v2.1 座標基準 / 縮圖 / 像素 / 批次
def device_size(device: str) -> tuple[int, int]:
    m = re.search(r"(\d+)x(\d+)", adb(["shell", "wm", "size"], device).stdout)
    if not m:
        raise ArkMobileError("讀不到 wm size", "QUERY_FAILED")
    return int(m.group(1)), int(m.group(2))


def to_device_xy(x: float, y: float, basis: tuple[int, int], device_wh: tuple[int, int]) -> tuple[int, int]:
    """任何非裝置座標（縮圖 / 設計稿）→ 裝置座標。座標唯一基準是 wm size（R3）。"""
    sx, sy = device_wh[0] / basis[0], device_wh[1] / basis[1]
    return int(round(x * sx)), int(round(y * sy))


def make_thumb(src: Path, width: int, out: Path, device_wh: tuple[int, int] | None = None) -> dict:
    """縮圖只給人 / AI 看；旁邊寫 .meta.json 記 scale，任何人拿縮圖座標去點之前必須換算。"""
    Image = _pil()
    with Image.open(src) as im:
        w, h = im.size
        th = max(1, int(h * width / w))
        im.resize((width, th), Image.LANCZOS).save(out)
    meta = {"source": str(src), "source_size": [w, h], "thumb_size": [width, th], "scale": round(w / width, 4),
            "device_size": list(device_wh) if device_wh else [w, h], "warning": "thumb 座標 × scale 才是裝置座標；不要直接拿來 tap"}
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def pixel_at(img: Path, x: int, y: int) -> list[int]:
    Image = _pil()
    with Image.open(img) as im:
        return list(im.convert("RGB").getpixel((x, y)))


def color_close(a: Sequence[int], b: Sequence[int], tol: int) -> bool:
    return all(abs(int(p) - int(q)) <= tol for p, q in zip(a, b))


def wait_pixel(device: str, xy: tuple[int, int], rgb: Sequence[int], tol: int, timeout: float, interval: float, out_dir: Path) -> dict:
    """輪詢到指定像素變成期望顏色（按鍵精靈的「找色」）。比 wait-stable 快，適合按鈕亮起 / 彈窗出現。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time(); n = 0
    while time.time() - t0 < timeout:
        n += 1
        shot = screenshot_to(device, out_dir / "_px.png")
        got = pixel_at(shot, *xy)
        if color_close(got, rgb, tol):
            return {"found": True, "elapsed_s": round(time.time() - t0, 2), "polls": n, "rgb": got}
        time.sleep(interval)
    return {"found": False, "elapsed_s": round(time.time() - t0, 2), "polls": n, "rgb": got if n else None}


def cmd_thumb(args):
    device_wh = None
    if not args.no_device:
        try:
            device_wh = device_size(resolve_device(args.device))
        except ArkMobileError:
            device_wh = None
    emit(make_thumb(Path(args.src), args.width, Path(args.out), device_wh), args.json)
    return 0


def cmd_to_device(args):
    device = resolve_device(args.device)
    bw, bh = (int(v) for v in args.basis.lower().split("x"))
    dx, dy = to_device_xy(args.x, args.y, (bw, bh), device_size(device))
    emit({"device": device, "basis": [bw, bh], "input": [args.x, args.y], "device_xy": [dx, dy]}, args.json)
    return 0


def cmd_pixel(args):
    x, y = (int(v) for v in args.xy.split(","))
    if args.src:
        rgb = pixel_at(Path(args.src), x, y); device = None
    else:
        device = resolve_device(args.device)
        rgb = pixel_at(screenshot_to(device, Path("artifacts/_px.png")), x, y)
    emit({"device": device, "xy": [x, y], "rgb": rgb, "hex": "#%02x%02x%02x" % tuple(rgb)}, args.json)
    return 0


def cmd_wait_pixel(args):
    device = resolve_device(args.device)
    xy = tuple(int(v) for v in args.xy.split(",")); rgb = [int(v) for v in args.rgb.split(",")]
    r = wait_pixel(device, xy, rgb, args.tol, args.timeout, args.interval, Path(args.out_dir))
    emit({"device": device, **r}, args.json)
    return 0 if r["found"] else EXIT["TIMEOUT"]


def cmd_batch(args):
    """單一 Python 進程跑多行子命令（R1 冷啟稅只付一次）。每行一個子命令，# 開頭為註解；--stop-on-error 預設開。"""
    src = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    parser = build_parser()
    results = []
    t0 = time.time()
    for ln, line in enumerate(src.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        import shlex
        argv = shlex.split(line)
        pre = ["--json"] + (["--device", args.device] if args.device and "--device" not in argv else [])
        sub = parser.parse_args(pre + argv)
        import io, contextlib
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = sub.func(sub)
            out = buf.getvalue().strip()
            data = json.loads(out.splitlines()[-1]) if out else None
            results.append({"line": ln, "cmd": line, "rc": rc, "data": data.get("data") if isinstance(data, dict) else data})
            if rc not in (0, None) and not args.keep_going:
                break
        except ArkMobileError as e:
            results.append({"line": ln, "cmd": line, "rc": EXIT.get(e.code, 2), "error": {"code": e.code, "message": str(e)}})
            if not args.keep_going:
                break
        except (SystemExit, Exception) as e:  # noqa: BLE001  子命令的 argparse 錯誤 / IO 錯誤都收斂成一行結果
            results.append({"line": ln, "cmd": line, "rc": 2, "error": {"code": "BAD_INPUT", "message": f"{type(e).__name__}: {e}"}})
            if not args.keep_going:
                break
    ok = all(r["rc"] in (0, None) for r in results)
    emit({"steps": len(results), "ok": ok, "elapsed_s": round(time.time() - t0, 2), "results": results}, args.json)
    return 0 if ok else EXIT["QUERY_FAILED"]


def cmd_shell_chain(args):
    device = resolve_device(args.device)
    emit({"device": device, "output": shell_chain(device, args.commands)}, args.json)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="ark-mobile-adb", description="ArkAgent Python CLI for Android/BlueStacks via adb")
    p.add_argument("--device", help="ADB serial, e.g. 127.0.0.1:5555")
    p.add_argument("--json", action="store_true", help="machine-readable JSON output")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("doctor")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("devices")
    s.set_defaults(func=cmd_devices)

    s = sub.add_parser("connect")
    s.add_argument("target")
    s.set_defaults(func=cmd_connect)

    s = sub.add_parser("disconnect")
    s.add_argument("target")
    s.set_defaults(func=cmd_disconnect)

    s = sub.add_parser("use", help="固定 serial 寫入 .ark-mobile.json（之後所有指令用同一台）")
    s.add_argument("serial", nargs="?")
    s.set_defaults(func=cmd_use)

    s = sub.add_parser("screen-size")
    s.set_defaults(func=cmd_screen_size)

    s = sub.add_parser("crop", help="裁切放大截圖（讀小字前必做）")
    s.add_argument("--src", required=True); s.add_argument("--rect", required=True, help="x,y,w,h")
    s.add_argument("--zoom", type=float, default=3.0); s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_crop)

    s = sub.add_parser("wait-stable", help="連拍到畫面靜止（動畫結束）")
    s.add_argument("--out-dir", default="artifacts/stable"); s.add_argument("--timeout", type=float, default=12)
    s.add_argument("--interval", type=float, default=0.5); s.add_argument("--threshold", type=float, default=0.004)
    s.set_defaults(func=cmd_wait_stable)

    s = sub.add_parser("locate", help="模板比對找按鈕/畫面錨點")
    s.add_argument("--screen", required=True); s.add_argument("--template", required=True)
    s.add_argument("--threshold", type=float, default=0.85)
    s.set_defaults(func=cmd_locate)

    s = sub.add_parser("ocr", help="tesseract 讀圖（先 crop --zoom 3）")
    s.add_argument("--image", required=True); s.add_argument("--digits", action="store_true"); s.add_argument("--lang", default="eng")
    s.set_defaults(func=cmd_ocr)

    s = sub.add_parser("logcat", help="掃 FATAL / ANR")
    s.add_argument("--since"); s.add_argument("--lines", type=int, default=2000); s.add_argument("--clear", action="store_true")
    s.set_defaults(func=cmd_logcat)

    s = sub.add_parser("restart-app")
    s.add_argument("package"); s.add_argument("--gap", type=float, default=1.0)
    s.set_defaults(func=cmd_restart_app)

    s = sub.add_parser("net", help="斷網 / 恢復（wifi + data）")
    s.add_argument("state", choices=["disconnect", "restore"])
    s.set_defaults(func=cmd_net)

    s = sub.add_parser("thumb", help="縮圖給人/AI 看（寫 .meta.json 記 scale；縮圖座標不可直接 tap）")
    s.add_argument("--src", required=True); s.add_argument("--width", type=int, default=540); s.add_argument("--out", required=True)
    s.add_argument("--no-device", action="store_true")
    s.set_defaults(func=cmd_thumb)

    s = sub.add_parser("to-device", help="把縮圖/設計稿座標換算成裝置座標")
    s.add_argument("x", type=float); s.add_argument("y", type=float); s.add_argument("--basis", required=True, help="來源尺寸，如 540x960")
    s.set_defaults(func=cmd_to_device)

    s = sub.add_parser("pixel", help="讀像素顏色（找色用）")
    s.add_argument("--xy", required=True); s.add_argument("--src")
    s.set_defaults(func=cmd_pixel)

    s = sub.add_parser("wait-pixel", help="輪詢到指定像素變成期望顏色")
    s.add_argument("--xy", required=True); s.add_argument("--rgb", required=True); s.add_argument("--tol", type=int, default=30)
    s.add_argument("--timeout", type=float, default=10); s.add_argument("--interval", type=float, default=0.3); s.add_argument("--out-dir", default="artifacts/stable")
    s.set_defaults(func=cmd_wait_pixel)

    s = sub.add_parser("batch", help="單進程跑多行子命令（檔案或 - 讀 stdin）")
    s.add_argument("--file", required=True); s.add_argument("--keep-going", action="store_true")
    s.set_defaults(func=cmd_batch)

    s = sub.add_parser("shell-chain", help="一次 adb shell 串多個指令")
    s.add_argument("commands", nargs="+")
    s.set_defaults(func=cmd_shell_chain)

    s = sub.add_parser("screenshot")
    s.add_argument("--out", default="artifacts/screen.png")
    s.add_argument("--crop", help="x,y,w,h 另存 -crop 檔"); s.add_argument("--zoom", type=float, default=3.0)
    s.set_defaults(func=cmd_screenshot)

    s = sub.add_parser("tap")
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)
    s.add_argument("--basis", help="座標來源尺寸（如 540x960）；給了就自動換算成裝置座標")
    s.set_defaults(func=cmd_tap)

    s = sub.add_parser("swipe")
    s.add_argument("x1", type=int)
    s.add_argument("y1", type=int)
    s.add_argument("x2", type=int)
    s.add_argument("y2", type=int)
    s.add_argument("--duration", type=int, default=300)
    s.set_defaults(func=cmd_swipe)

    s = sub.add_parser("long-press")
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)
    s.add_argument("--duration", type=int, default=800)
    s.set_defaults(func=cmd_long_press)

    s = sub.add_parser("text")
    s.add_argument("value")
    s.set_defaults(func=cmd_text)

    s = sub.add_parser("keyevent")
    s.add_argument("key")
    s.set_defaults(func=cmd_keyevent)

    for name, key in [("home", "HOME"), ("back", "BACK"), ("recent", "APP_SWITCH")]:
        s = sub.add_parser(name)
        s.set_defaults(func=lambda args, k=key: cmd_simple_key(args, k))

    s = sub.add_parser("launch")
    s.add_argument("package")
    s.set_defaults(func=cmd_launch)

    s = sub.add_parser("stop")
    s.add_argument("package")
    s.set_defaults(func=cmd_stop)

    s = sub.add_parser("clear-data")
    s.add_argument("package")
    s.set_defaults(func=cmd_clear_data)

    s = sub.add_parser("packages")
    s.add_argument("--third-party", action="store_true")
    s.set_defaults(func=cmd_packages)

    s = sub.add_parser("install")
    s.add_argument("apk")
    s.add_argument("--timeout", type=float, default=120)
    s.set_defaults(func=cmd_install)

    s = sub.add_parser("foreground")
    s.add_argument("--raw", action="store_true")
    s.set_defaults(func=cmd_foreground)

    s = sub.add_parser("ui-dump")
    s.add_argument("--out", default="artifacts/ui.xml")
    s.set_defaults(func=cmd_ui_dump)

    s = sub.add_parser("shell")
    s.add_argument("--timeout", type=float, default=30)
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_shell)

    s = sub.add_parser("wait")
    s.add_argument("seconds", type=float)
    s.set_defaults(func=cmd_wait)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ArkMobileError as e:
        if getattr(args, "json", False):
            print(json.dumps({"success": False, "contract": CONTRACT, "error": {"code": e.code, "message": str(e), "hint": e.hint}}, ensure_ascii=False))
        else:
            print(f"[{e.code}] {e}" + (f"\n  hint: {e.hint}" if e.hint else ""), file=sys.stderr)
        return EXIT.get(e.code, 2)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
