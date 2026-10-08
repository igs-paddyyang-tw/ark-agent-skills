#!/usr/bin/env python3
"""gs_restore — 還原模式（已上線遊戲）：ProbSetting JSON → config-spec.yaml（mode: restore-live）。

與 gs_dev（設計鏈：value 一律 null）平行，不改設計鏈語意：
  - 鍵清單 = 設定檔 JSON 的全部頂層鍵（不靠 config-map；還原要「全部」不是「要上表的」）
  - parameters[].value 一律 {$ref: "<相對路徑>#/<JSON Pointer>"}，不抄值；$ref 路徑相對 config-spec.yaml 所在目錄
  - decision 統一 `restore-live: <sha16>`（給 --xlsx 用公版表 sha，否則用設定檔 sha）
自檢（--check 或產出後自動）：mode 須為 restore-live、每鍵 value 是 $ref 且可解析 → 否則 exit 3（GATE_BLOCKED）。

用法:
  python gs_restore.py --config <ProbSetting.json> [--xlsx <公版機率表.xlsx>] [--out output/games/<slug>/spec] [--slug <slug>]
  python gs_restore.py --check <config-spec.yaml>
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # skill root（_lib）
from _lib import run_common as C  # noqa: E402

MODE = "restore-live"


def ptr_escape(key: str) -> str:
    """RFC 6901：~ → ~0、/ → ~1。"""
    return key.replace("~", "~0").replace("/", "~1")


def resolve_ref(ref: str, base: pathlib.Path) -> tuple[bool, str]:
    """解析 `<path>#/<pointer>`（path 相對 base）；回 (可解析, 原因)。"""
    path, _, frag = str(ref).partition("#")
    f = (base / path).resolve()
    if not path or not f.is_file():
        return False, f"檔案不存在：{path}"
    try:
        node = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return False, f"JSON 讀取失敗：{e}"
    if not frag.startswith("/"):
        return False, "缺 JSON Pointer（#/<key>）"
    for tok in frag[1:].split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and tok in node:
            node = node[tok]
        elif isinstance(node, list) and tok.isdigit() and int(tok) < len(node):
            node = node[int(tok)]
        else:
            return False, f"鍵不存在：{tok}"
    return True, ""


def shape(v) -> str:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return "string" if isinstance(v, str) else "null"


def check(cfg: dict, base: pathlib.Path) -> list[dict]:
    errs = []
    if cfg.get("mode") != MODE:
        errs.append({"rule": "SPEC-RESTORE", "param": None, "msg": f"mode 須為 {MODE}（現為 {cfg.get('mode')!r}）"})
    params = cfg.get("parameters") or []
    if not params:
        errs.append({"rule": "SPEC-RESTORE", "param": None, "msg": "parameters 為空"})
    for p in params:
        v = p.get("value")
        ref = v.get("$ref") if isinstance(v, dict) else None
        if not ref:
            errs.append({"rule": "SPEC-RESTORE", "param": p.get("name"), "msg": "還原模式 value 須為 {$ref: ...}（不可裸值／描述字串／null）"})
            continue
        ok, why = resolve_ref(ref, base)
        if not ok:
            errs.append({"rule": "SPEC-RESTORE", "param": p.get("name"), "msg": f"$ref 無法解析 {ref}：{why}"})
        if not str(p.get("decision") or "").startswith(MODE + ":"):
            errs.append({"rule": "SPEC-RESTORE", "param": p.get("name"), "msg": f"decision 須為 '{MODE}: <sha16>'"})
    return errs


def gate(errs: list[dict], data: dict) -> None:
    if errs:
        C.fail("GATE_BLOCKED", f"還原模式 config-spec 自檢 {len(errs)} 個錯誤", "value 一律 $ref 指向設定檔、mode/decision 照契約；見 data.errors",
               {**data, "errors": errs[:20]})


def main() -> None:
    ap = argparse.ArgumentParser(description="還原模式 config-spec（restore-live）")
    ap.add_argument("--config", help="已上線 ProbSetting JSON")
    ap.add_argument("--xlsx", help="公版機率表（選配，sha16 寫進 decision）")
    ap.add_argument("--out", help="輸出目錄（預設 <config 同層>/spec）")
    ap.add_argument("--slug")
    ap.add_argument("--check", help="只自檢既有 config-spec.yaml")
    a = ap.parse_args()

    if a.check:
        p = pathlib.Path(a.check)
        if not p.is_file():
            C.fail("BAD_INPUT", f"找不到 {p}")
        cfg = C.yaml_load(p) or {}
        errs = check(cfg, p.resolve().parent)
        data = {"config_spec": str(p), "params": len(cfg.get("parameters") or [])}
        gate(errs, data)
        C.emit({**data, "verdict": "OK"}, {"stage": "restore-check"})
        return

    if not a.config:
        C.fail("BAD_INPUT", "需要 --config <ProbSetting.json> 或 --check <config-spec.yaml>")
    src = pathlib.Path(a.config).resolve()
    if not src.is_file():
        C.fail("BAD_INPUT", f"找不到 {src}")
    try:
        conf = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        C.fail("BAD_INPUT", f"設定檔非合法 JSON：{e}")
    if not isinstance(conf, dict) or not conf:
        C.fail("BAD_INPUT", "設定檔頂層須為非空物件")
    xlsx = pathlib.Path(a.xlsx).resolve() if a.xlsx else None
    if xlsx and not xlsx.is_file():
        C.fail("BAD_INPUT", f"找不到 {xlsx}")

    out = pathlib.Path(a.out).resolve() if a.out else src.parent / "spec"
    out.mkdir(parents=True, exist_ok=True)
    rel = pathlib.Path(os.path.relpath(src, out)).as_posix()
    sha_cfg = C.sha256_file(src)[:16]
    sha_x = C.sha256_file(xlsx)[:16] if xlsx else None
    decision = f"{MODE}: {sha_x or sha_cfg}"
    cfg = {
        "contract": "1",
        "mode": MODE,
        "slug": a.slug or src.stem,
        "source_config": {"path": rel, "sha256_16": sha_cfg},
        **({"source_xlsx": {"path": xlsx.name, "sha256_16": sha_x}} if xlsx else {}),
        "parameters": [{"name": k, "type": shape(v), "value": {"$ref": f"{rel}#/{ptr_escape(k)}"}, "decision": decision}
                       for k, v in conf.items()],
    }
    errs = check(cfg, out)                                 # 產出即自檢（不信任自己）
    data = {"out": str(out), "config_spec": str(out / "config-spec.yaml"), "params": len(cfg["parameters"]),
            "source_config": rel, "decision": decision}
    gate(errs, data)
    C.atomic_write(out / "config-spec.yaml", C.yaml_dump(cfg))
    C.emit({**data, "next": "ark-game-prob ps_run --dest output/games/<slug>/prob → ark-game-quicktest qt_report --config-spec 本檔"},
           {"stage": "restore"})


if __name__ == "__main__":
    main()
