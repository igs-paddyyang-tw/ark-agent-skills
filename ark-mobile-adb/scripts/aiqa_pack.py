#!/usr/bin/env python3
"""aiqa_pack — gamepack 工具：lint / new / calibrate-demo / resolve / draft / verify / promote。

用法:
  python aiqa_pack.py lint --game ghy [--machine aztec2]        # error → exit 3
  python aiqa_pack.py new --game mahjong --display-name 麻將
  python aiqa_pack.py calibrate-demo                              # 由合成遊戲產 demo-slot 的 screens/buttons 模板圖
  python aiqa_pack.py resolve --game demo-slot [--machine x] [--out r.json]
  python aiqa_pack.py draft --game ghy --machine aztec2                       # 標 status: draft
  python aiqa_pack.py verify --game ghy --machine aztec2 --spins spins.json   # autobox 核帳 → 回「可升」（不改檔）
  python aiqa_pack.py promote --game ghy --machine aztec2                     # 人確認後 status draft→verified
校準真遊戲：在 BlueStacks 截圖 → 用 ark_mobile_adb.py crop 裁錨點 → 填 screens/buttons/rois → lint 綠 → calibrated: true。
autobox：不另花押注試轉——用正常連轉讀數經 aiqa_ledger 核帳，通過門檻才由人 promote 升 verified。
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

STATUS_VALUES = ("draft", "verified")


def lint_pack(game: str, machine: str | None, root=None) -> list[dict]:
    v = []
    add = lambda sev, rule, msg: v.append({"severity": sev, "rule": rule, "message": msg})  # noqa: E731
    try:
        pack = C.load_pack(game, machine, root=root)
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


# ---------------------------------------------------------------- autobox：draft → verify → promote
def _machine_yaml_path(game: str, machine: str, root=None) -> pathlib.Path:
    """machines/<machine>/machine.yaml 的實體路徑（寫 status 用，非 merged pack）。"""
    root = root or C.GAMEPACKS_DIR
    return root / game / "machines" / machine / "machine.yaml"


def _read_status(mp: pathlib.Path) -> str:
    return str((C.yaml_load(mp) or {}).get("status") or "draft") if mp.exists() else "draft"


def _write_status(mp: pathlib.Path, status: str) -> None:
    """只改 machine.yaml 的 status 欄，其餘保持原樣（含欄位順序，status 置頂）。"""
    doc = C.yaml_load(mp) or {}
    new = {"status": status}
    for k, v in doc.items():
        if k != "status":
            new[k] = v
    C.atomic_write(mp, C.yaml_dump(new))


def draft_machine(game: str, machine: str, root=None) -> dict:
    """把機台檔標為 draft（待核帳驗證）。machine.yaml 不存在 → 報錯提示先建。"""
    mp = _machine_yaml_path(game, machine, root)
    if not mp.exists():
        C.fail("BAD_INPUT", f"machine.yaml 不存在：{mp}", "先建機台檔（screens/rois/navigation），再 draft")
    _write_status(mp, "draft")
    pending = []
    doc = C.yaml_load(mp) or {}
    if not doc.get("rois"):
        pending.append("rois（贏分/押注/credit 框）")
    if not doc.get("screens"):
        pending.append("screens（錨點模板）")
    return {"game": game, "machine": machine, "status": "draft", "machine_yaml": str(mp),
            "pending": pending,
            "next": f"正常連轉收 spins.json → python aiqa_pack.py verify --game {game} --machine {machine} --spins spins.json"}


def verify_machine(game: str, machine: str, spins_path: str, *, min_clean: int, require_win: bool, tol: float, root=None) -> dict:
    """對連轉讀數做核帳驗證（autobox）；只回「可升 verified」，不改檔。"""
    import aiqa_gamepack_autobox as AB
    mp = _machine_yaml_path(game, machine, root)
    if not mp.exists():
        C.fail("BAD_INPUT", f"machine.yaml 不存在：{mp}", "先 aiqa_pack.py draft")
    sp = pathlib.Path(spins_path)
    if not sp.exists():
        C.fail("BAD_INPUT", f"spins JSON 不存在：{sp}", "連轉逐手讀 credit_before/bet/win/credit_after 存成 list")
    r = AB.verify_profile(AB._load_spins(sp), min_clean=min_clean, require_win=require_win, tol=tol)
    return {"game": game, "machine": machine, "current_status": _read_status(mp),
            "can_promote": r.verified, "reason": r.reason,
            "clean_pairs": r.clean_pairs, "wins": r.wins, "fails": r.fails,
            "next": (f"人確認後 → python aiqa_pack.py promote --game {game} --machine {machine}"
                     if r.verified else "修框選/roi 後重收 spins 再 verify")}


def promote_machine(game: str, machine: str, root=None) -> dict:
    """人確認後把 machine.yaml status draft → verified（本命令即「人下」的動作）。"""
    mp = _machine_yaml_path(game, machine, root)
    if not mp.exists():
        C.fail("BAD_INPUT", f"machine.yaml 不存在：{mp}", "先 aiqa_pack.py draft")
    prev = _read_status(mp)
    _write_status(mp, "verified")
    return {"game": game, "machine": machine, "status": "verified", "previous": prev, "machine_yaml": str(mp)}


def main() -> None:
    ap = argparse.ArgumentParser(description="gamepack tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lint"); s.add_argument("--game", required=True); s.add_argument("--machine")
    s.add_argument("--pack-dir", help="gamepack 根目錄（校準 DATA 放 skill 外時指入）")
    s = sub.add_parser("new"); s.add_argument("--game", required=True); s.add_argument("--display-name", required=True)
    sub.add_parser("calibrate-demo")
    s = sub.add_parser("resolve"); s.add_argument("--game", required=True); s.add_argument("--machine"); s.add_argument("--out")
    s = sub.add_parser("list")
    s = sub.add_parser("draft", help="把機台檔標為 draft（待核帳驗證）")
    s.add_argument("--game", required=True); s.add_argument("--machine", required=True)
    s.add_argument("--pack-dir", help="gamepack 根目錄")
    s = sub.add_parser("verify", help="autobox：對連轉讀數核帳，回「可升 verified」（不改檔）")
    s.add_argument("--game", required=True); s.add_argument("--machine", required=True)
    s.add_argument("--spins", required=True, help="spins JSON：list of {credit_before,bet,win,credit_after,action?}")
    s.add_argument("--min-clean", type=int, default=3); s.add_argument("--no-require-win", action="store_true")
    s.add_argument("--tol", type=float, default=1.0); s.add_argument("--pack-dir", help="gamepack 根目錄")
    s = sub.add_parser("promote", help="人確認後把 status draft→verified")
    s.add_argument("--game", required=True); s.add_argument("--machine", required=True)
    s.add_argument("--pack-dir", help="gamepack 根目錄")
    a = ap.parse_args()
    if a.cmd == "list":
        C.emit({"games": C.list_games(), "dir": str(C.GAMEPACKS_DIR)})
    if a.cmd == "lint":
        v = lint_pack(a.game, a.machine, root=C.resolve_pack_root(getattr(a, "pack_dir", None)))
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
    if a.cmd == "draft":
        root = C.resolve_pack_root(getattr(a, "pack_dir", None))
        C.emit(draft_machine(a.game, a.machine, root=root))
    if a.cmd == "verify":
        root = C.resolve_pack_root(getattr(a, "pack_dir", None))
        data = verify_machine(a.game, a.machine, a.spins, min_clean=a.min_clean,
                              require_win=not a.no_require_win, tol=a.tol, root=root)
        if not data["can_promote"]:
            C.fail("GATE_BLOCKED", data["reason"], data["next"], data=data)
        C.emit(data)
    if a.cmd == "promote":
        root = C.resolve_pack_root(getattr(a, "pack_dir", None))
        C.emit(promote_machine(a.game, a.machine, root=root))


if __name__ == "__main__":
    main()
