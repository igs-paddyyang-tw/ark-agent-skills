#!/usr/bin/env python3
"""aiqa_pack — gamepack 工具：lint / new / calibrate-demo / resolve。

用法:
  python aiqa_pack.py lint --game ghy [--machine aztec2]        # error → exit 3
  python aiqa_pack.py new --game mahjong --display-name 麻將
  python aiqa_pack.py calibrate-demo                              # 由合成遊戲產 demo-slot 的 screens/buttons 模板圖
  python aiqa_pack.py resolve --game demo-slot [--machine x] [--out r.json]
校準真遊戲：在 BlueStacks 截圖 → 用 ark_mobile_adb.py crop 裁錨點 → 填 screens/buttons/rois → lint 綠 → calibrated: true。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiqa_common as C  # noqa: E402

ACTIONS = {"macro", "navigate", "tap", "key", "wait", "read", "capture", "ask", "repeat", "restart_app", "net", "harness", "crash_check", "loop_spin", "manual_step", "swipe"}


def lint_pack(game: str, machine: str | None) -> list[dict]:
    v = []
    add = lambda sev, rule, msg: v.append({"severity": sev, "rule": rule, "message": msg})  # noqa: E731
    try:
        pack = C.load_pack(game, machine)
    except C.PackError as e:
        return [{"severity": "error", "rule": "PACK-LOAD", "message": str(e)}]
    for k in ("game", "display_name", "package", "resolution", "calibrated", "taxonomy", "harness", "screens", "buttons", "rois", "navigation", "templates"):
        if k not in pack:
            add("error", "PACK-FIELDS", f"game.yaml 缺 {k}")
    if "__GAME__" in str(pack.get("game")) or "TODO" in str(pack.get("display_name")):
        add("error", "PACK-PLACEHOLDER", "仍有 __GAME__ / TODO 佔位")
    res = pack.get("resolution") or {}
    if not (res.get("width") and res.get("height")):
        add("error", "PACK-RES", "resolution 需 width/height；所有座標以此（= BlueStacks wm size）為唯一基準")
    for mp in sorted(pathlib.Path(pack["_dir"]).glob("macros/*.yaml")) + sorted(pathlib.Path(pack["_dir"]).glob("machines/*/macros/*.yaml")):
        try:
            import aiqa_macro as MC
            for x in MC.lint(MC.load_macro(mp), pack):
                if x["severity"] == "error":
                    add("error", "PACK-MACRO", f"{mp.name}: {x['message']}")
        except Exception as e:  # noqa: BLE001
            add("error", "PACK-MACRO", f"{mp.name}: {e}")
    for h in ("trigger", "gm", "network"):
        if h not in (pack.get("harness") or {}):
            add("error", "PACK-HARNESS", f"harness 缺 {h}（沒有能力請明寫 none）")
    for name, s in (pack.get("screens") or {}).items():
        if not s.get("template") or not pathlib.Path(s["template"]).exists():
            add("error", "PACK-SCREEN", f"screen {name} 模板圖不存在: {s.get('template')}")
        elif s.get("region") and len(s["region"]) != 4:
            add("error", "PACK-SCREEN", f"screen {name} region 需 x,y,w,h")
    for name, b in (pack.get("buttons") or {}).items():
        if not b.get("xy") and not (b.get("template") and pathlib.Path(b["template"]).exists()):
            add("error" if pack.get("calibrated") else "warn", "PACK-BUTTON", f"button {name} 無 xy 也無模板（未校準）")
        if b.get("shared") and (not b.get("opens") or not b.get("close")):
            add("warn", "PACK-BUTTON", f"shared button {name} 缺 opens/close（shared_buttons 模板會略過）")
    for name, r in (pack.get("rois") or {}).items():
        if not (isinstance(r, list) and len(r) == 4):
            add("error", "PACK-ROI", f"roi {name} 需 [x,y,w,h]")
    for path, steps in (pack.get("navigation") or {}).items():
        if not re.match(r"^[\w*]+->\w+$", path):
            add("error", "PACK-NAV", f"navigation key {path!r} 需 <from>-><to>")
        for st in steps or []:
            for k, val in st.items():
                if k == "tap" and not str(val).startswith("btn:"):
                    add("error", "PACK-NAV", f"{path}: tap 需 btn:<name>")
                if k == "tap":
                    try:
                        C.pack_target(pack, val)
                    except C.PackError as e:
                        add("error", "PACK-NAV", f"{path}: {e}")
                if k == "wait_screen" and val not in (pack.get("screens") or {}) and pack.get("calibrated"):
                    add("error", "PACK-NAV", f"{path}: screen {val} 未定義")
    for tname, entries in (pack.get("templates") or {}).items():
        for e in entries or []:
            if "id" not in e or "title" not in e:
                add("error", "PACK-TEMPLATES", f"templates.{tname} 每筆需 id / title")
            for a in e.get("setup", []) or []:
                if a.get("do") not in ACTIONS:
                    add("error", "PACK-TEMPLATES", f"templates.{tname}.{e.get('id')} setup 未知動作 {a.get('do')}")
    for b in pack.get("bindings", []):
        try:
            re.compile(b.get("match", ""))
        except re.error as e:
            add("error", "PACK-BINDINGS", f"binding regex 錯誤 {b.get('match')!r}: {e}")
        for a in b.get("actions", []):
            if a.get("do") not in ACTIONS:
                add("error", "PACK-BINDINGS", f"binding {b.get('match')} 未知動作 {a.get('do')}")
    if not pack.get("calibrated"):
        add("warn", "PACK-CALIBRATED", "calibrated: false — runner 只接受 --backend fake 或 --allow-uncalibrated")
    return v


def calibrate_demo() -> dict:
    """用合成遊戲渲染各畫面，裁 region 成模板圖 → demo-slot/screens、buttons。"""
    from aiqa_fake_game import FakeGame, LAYOUT
    import ark_mobile_adb as M
    root = C.GAMEPACKS_DIR / "demo-slot"
    pack = C.yaml_load(root / "game.yaml")
    tmp = root / ".calib"; tmp.mkdir(exist_ok=True)
    g = FakeGame(1)
    shots = {}
    g.screen = "lobby"; shots["lobby"] = g.render(tmp / "lobby.png")
    g.screen = "main_game"; shots["main_game"] = g.render(tmp / "main_game.png")
    g.screen = "info_page"; shots["info_page"] = g.render(tmp / "info_page.png")
    g.screen = "main_game"; g.popup = "6002"; shots["error_6002"] = g.render(tmp / "error_6002.png"); g.popup = None
    made = []
    for name, s in pack["screens"].items():
        out = root / s["template"]
        M.crop_zoom(shots[name if name != "error_6002" else "error_6002"], s["region"], 1, out); made.append(str(out))
    for name, b in pack["buttons"].items():
        if b.get("template"):
            x, y, w, h = LAYOUT[name]
            M.crop_zoom(shots["main_game"], [x, y, w, h], 1, root / b["template"]); made.append(str(root / b["template"]))
    shutil.rmtree(tmp, ignore_errors=True)
    return {"templates": made}


def main() -> None:
    ap = argparse.ArgumentParser(description="gamepack tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lint"); s.add_argument("--game", required=True); s.add_argument("--machine")
    s = sub.add_parser("new"); s.add_argument("--game", required=True); s.add_argument("--display-name", required=True)
    sub.add_parser("calibrate-demo")
    s = sub.add_parser("resolve"); s.add_argument("--game", required=True); s.add_argument("--machine"); s.add_argument("--out")
    s = sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "list":
        C.emit({"games": C.list_games(), "dir": str(C.GAMEPACKS_DIR)})
    if a.cmd == "lint":
        v = lint_pack(a.game, a.machine)
        errs = [x for x in v if x["severity"] == "error"]
        data = {"game": a.game, "machine": a.machine, "errors": errs, "warnings": [x for x in v if x["severity"] == "warn"]}
        if errs:
            C.fail("GATE_BLOCKED", f"{len(errs)} 個 error", "修 gamepack 後重跑", data=data)
        C.emit(data)
    if a.cmd == "new":
        if not re.match(r"^[a-z][a-z0-9-]{1,40}$", a.game):
            C.fail("BAD_INPUT", "game 需 kebab-case", "")
        dst = C.GAMEPACKS_DIR / a.game
        if dst.exists():
            C.fail("BAD_INPUT", f"{dst} 已存在", "")
        shutil.copytree(C.GAMEPACKS_DIR / "_template", dst)
        for p in dst.rglob("*.yaml"):
            p.write_text(p.read_text(encoding="utf-8").replace("__GAME__", a.game).replace("__DISPLAY_NAME__", a.display_name), encoding="utf-8")
        C.emit({"created": str(dst), "checklist": [f"[{x['severity']}] {x['rule']}: {x['message']}" for x in lint_pack(a.game, None)],
                "next": "在 BlueStacks 截圖 → ark_mobile_adb.py crop 裁錨點 → 填 screens/buttons/rois/navigation → aiqa_pack.py lint"})
    if a.cmd == "calibrate-demo":
        C.emit(calibrate_demo())
    if a.cmd == "resolve":
        try:
            pack = C.load_pack(a.game, a.machine)
        except C.PackError as e:
            C.fail("BAD_INPUT", str(e), "")
        if a.out:
            C.atomic_write(pathlib.Path(a.out), json.dumps(pack, ensure_ascii=False, indent=1, default=str))
        C.emit({"game": pack["game"], "machine": pack.get("machine"), "sha256": pack["_sha256"], "screens": list(pack.get("screens", {})),
                "buttons": list(pack.get("buttons", {})), "rois": list(pack.get("rois", {})), "harness": pack.get("harness"), "calibrated": pack.get("calibrated")})


if __name__ == "__main__":
    main()
