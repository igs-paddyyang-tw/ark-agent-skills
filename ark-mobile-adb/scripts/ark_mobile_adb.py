#!/usr/bin/env python3
"""
ark-mobile-adb: Python CLI wrapper around Android Debug Bridge.

Designed for ArkAgent Skills:
    Agent -> this CLI -> adb -> Android/BlueStacks

Python 3.10+; standard library only.
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


class ArkMobileError(RuntimeError):
    pass


def emit(data, json_mode: bool = False):
    if json_mode:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if isinstance(data, str):
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

    which = shutil.which("adb")
    if which:
        return which

    for p in candidates:
        if p.exists():
            return str(p)

    return None


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
        raise ArkMobileError(f"Command not found: {args[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise ArkMobileError(f"Command timed out after {timeout}s: {' '.join(args)}") from e


def adb_path() -> str:
    path = find_adb()
    if not path:
        raise ArkMobileError(
            "adb not found. Install Android Platform Tools and configure "
            "ANDROID_HOME/ANDROID_SDK_ROOT or PATH."
        )
    return path


def adb(args: Sequence[str], device: str | None = None, timeout: float = 30) -> subprocess.CompletedProcess:
    cmd = [adb_path()]
    if device:
        cmd += ["-s", device]
    cmd += list(args)
    cp = run_cmd(cmd, timeout=timeout)
    if cp.returncode != 0:
        stderr = (cp.stderr or "").strip()
        stdout = (cp.stdout or "").strip()
        detail = stderr or stdout or f"exit code {cp.returncode}"
        raise ArkMobileError(f"adb failed: {' '.join(cmd)}\n{detail}")
    return cp


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
        raise ArkMobileError(
            f"Requested device '{requested}' is not in device state. "
            f"Available: {[d['serial'] for d in devices]}"
        )

    if len(devices) == 1:
        return devices[0]["serial"]

    if not devices:
        raise ArkMobileError("No Android device in 'device' state. Run `devices` or `doctor`.")
    raise ArkMobileError(
        "Multiple Android devices found. Specify one with --device SERIAL: "
        + ", ".join(d["serial"] for d in devices)
    )


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

    # Binary-safe path: screencap to device then adb pull.
    remote = "/sdcard/ark_mobile_adb_capture.png"
    adb(["shell", "screencap", "-p", remote], device)
    pull = run_cmd([adb_path(), "-s", device, "pull", remote, str(out)], timeout=30)
    if pull.returncode != 0:
        raise ArkMobileError(pull.stderr.strip() or "adb pull failed")

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

    s = sub.add_parser("screenshot")
    s.add_argument("--out", default="artifacts/screen.png")
    s.set_defaults(func=cmd_screenshot)

    s = sub.add_parser("tap")
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)
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
        error = {"status": "error", "error": str(e)}
        emit(error, getattr(args, "json", False))
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
