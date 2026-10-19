#!/usr/bin/env python3
"""proto_build — 機率規格書（prob-spec.md）→ game-config.json → 單檔 H5 老虎機驗證雛型（PixiJS 8）。

  python proto_build.py --md data/slot/<slug>/prob/prob-spec.md --adapter milefo --out output/slot-proto/<slug>
  python proto_build.py --md ... --go-config data/slot/<slug>/quicktest/config/a-standard.json   # 規格書 ⇄ Go 設定檔逐鍵對照
  python proto_build.py --md ... --go-parity parity.json      # 內嵌 tests/go_parity.js 的逐局對照結果到驗證台
  python proto_build.py --md ... --config-only                # 只產 game-config.json
  python proto_build.py --md ... --inline-pixi                # 內嵌 PixiJS（離線單檔，約 +650 KB）

原則：prob-spec.md 是唯一來源（ark-game-prob 1.4 md-first）；本腳本只搬表格、不發明數字；每個參數帶 src；
規格書沒寫清楚的規則記在 config.gaps（含推定、回驗方式、Go 證據）；Go 設定檔只用來「對照」與「補規格書缺的值」（標來源）。
stdout 為 JSON envelope：{"success": bool, "data"|"error": ...}；exit 2 = 輸入錯、3 = Go 對照不一致（--strict）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import proto_common as P  # noqa: E402

ADAPTERS = sorted(p.stem for p in (HERE / "adapters").glob("*.py") if not p.stem.startswith("_"))


def fail(code: int, msg: str, hint: str = "") -> None:
    print(json.dumps({"success": False, "error": {"message": msg, "hint": hint}}, ensure_ascii=False))
    sys.exit(code)


def spec_max_win(doc: dict):
    """§4 任一 kv 表有「最大贏分倍數 / MaxWin」列就取值（md 模式範本有這列）。"""
    for x in P.walk_tables(doc, "params"):
        t = x["t"]
        if t["cls"] != "kv":
            continue
        for r in t["rows"]:
            if "MaxWin" in r[0] or "最大贏分倍數" in r[0]:
                v = P.num(r[1])
                if v:
                    return v, P.src_of(r, t["head"]) or "§4 " + x["h3"]
    return None, None


def build_config(md_p: pathlib.Path, adapter: str) -> dict:
    """md → game-config.json（通用段 + adapter 玩法段 + §2 目標 + 缺口）。"""
    text = md_p.read_text(encoding="utf-8")
    doc = P.M.parse_md(text)
    doc["md_path"] = str(md_p.resolve())                # adapter 可據此找規格書旁的快測報表（不依賴 CWD）
    g = P.generic(doc)
    cfg = {"schema": "slot-proto-config/1", "game": doc["fm"].get("game"), "slug": doc["fm"].get("slug"),
           "source": {"md": md_p.name, "sha16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                      "mode": doc["fm"].get("mode"), "verdict": doc["fm"].get("verdict"), "date": str(doc["fm"].get("date"))},
           "board": g["board"], "paytable": g["paytable"], "tiers": g["tiers"]}
    mw, mw_src = spec_max_win(doc)
    if mw:
        cfg["board"]["max_win"], cfg["board"]["max_win_src"] = mw, mw_src
    mod = importlib.import_module(f"adapters.{adapter}")
    ad = mod.build(doc, g)
    if "board" in ad:                                   # adapter 自帶盤面時，保留 §4 MaxWin 的讀值
        ad["board"] = {**cfg["board"], **ad["board"]} if not ad["board"].get("max_win") else ad["board"]
    cfg.update(ad)
    cfg.setdefault("art", adapter)                      # 美術套 = adapter 名（src/art.js SETS）
    cfg["targets"] = P.targets(doc)
    if hasattr(mod, "targets_extra"):
        cfg["targets"].update(mod.targets_extra(doc))
    return cfg


def go_check(cfg: dict, adapter: str, go_p: pathlib.Path) -> dict:
    """規格書 ⇄ Go 設定檔：逐鍵對照（adapter.go_rules），再補規格書缺的值（adapter.go_fill）。"""
    mod = importlib.import_module(f"adapters.{adapter}")
    if not hasattr(mod, "go_rules"):
        fail(2, f"adapter {adapter} 沒有 go_rules()", "此玩法尚未定義 Go 設定檔對照")
    raw = go_p.read_bytes()
    go = json.loads(raw.decode("utf-8"))
    rules = mod.go_rules(cfg, go)
    filled = mod.go_fill(cfg, go) if hasattr(mod, "go_fill") else []
    return {"path": go_p.name, "sha16": hashlib.sha256(raw).hexdigest()[:16], "rules": rules, "filled": filled,
            "match": sum(r["ok"] is True for r in rules), "mismatch": sum(r["ok"] is False for r in rules),
            "gap": sum(r["ok"] is None for r in rules)}


def build_html(cfg: dict, out: pathlib.Path, inline_pixi: bool) -> int:
    """template.html + src/*.js + config → 單檔 index.html；回位元組數。"""
    src = HERE / "src"
    tpl = (src / "template.html").read_text(encoding="utf-8")
    parts = {n: (src / f"{n}.js").read_text(encoding="utf-8") for n in ("slot-core", "art", "app")}
    pm = next((p for p in (HERE / "vendor/pixi.min.js", HERE / "node_modules/pixi.js/dist/pixi.min.js") if p.exists()), None)
    tag = ('<script src="https://cdn.jsdelivr.net/npm/pixi.js@8.6.6/dist/pixi.min.js"></script>\n'
           '<script>window.PIXI||document.write(\'<script src="vendor/pixi.min.js"><\\/script>\')</script>')
    if inline_pixi:
        if not pm:
            fail(2, "--inline-pixi 需要 scripts/vendor/pixi.min.js")
        tag = f"<script>{pm.read_text(encoding='utf-8')}</script>"
    elif pm:
        (out / "vendor").mkdir(exist_ok=True)
        (out / "vendor" / "pixi.min.js").write_bytes(pm.read_bytes())
    html = (tpl.replace("<!--PIXI-->", tag)
               .replace("/*CONFIG*/", "window.GAME_CONFIG=" + json.dumps(cfg, ensure_ascii=False) + ";")
               .replace("/*CORE*/", parts["slot-core"]).replace("/*ART*/", parts["art"]).replace("/*APP*/", parts["app"])
               .replace("__TITLE__", f"{cfg['game']} 機率驗證雛型"))
    (out / "index.html").write_text(html, encoding="utf-8")
    return len(html.encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--md", required=True, help="prob-spec.md（ark-game-prob 1.4+ 格式）")
    ap.add_argument("--adapter", default="milefo", help="玩法 adapter：" + " / ".join(ADAPTERS))
    ap.add_argument("--out", default="output/slot-proto/game")
    ap.add_argument("--go-config", help="Go 快測設定檔 JSON：逐鍵對照 + 補規格書缺的值")
    ap.add_argument("--go-parity", help="tests/go_parity.js 輸出的 JSON（可多次）", action="append")
    ap.add_argument("--strict", action="store_true", help="Go 對照有 mismatch 時 exit 3")
    ap.add_argument("--config-only", action="store_true")
    ap.add_argument("--inline-pixi", action="store_true")
    a = ap.parse_args()
    md_p = pathlib.Path(a.md)
    if not md_p.exists():
        fail(2, f"找不到 {md_p}")
    if a.adapter not in ADAPTERS:
        fail(2, f"未知 adapter：{a.adapter}", "可用：" + ", ".join(ADAPTERS))
    cfg = build_config(md_p, a.adapter)
    res = {"adapter": a.adapter, "sha16": cfg["source"]["sha16"], "gaps": len(cfg.get("gaps", []))}
    if a.go_config:
        cfg["go_check"] = go_check(cfg, a.adapter, pathlib.Path(a.go_config))
        gc = cfg["go_check"]
        res["go_check"] = {k: gc[k] for k in ("match", "mismatch", "gap", "filled")}
    if a.go_parity:
        cfg["go_parity"] = [json.loads(pathlib.Path(p).read_text(encoding="utf-8")) for p in a.go_parity]
        res["go_parity"] = [{k: x.get(k) for k in ("seed", "spins", "fg", "capped", "mismatch")} for x in cfg["go_parity"]]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "game-config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    res["config"] = str(out / "game-config.json")
    if not a.config_only:
        res["html"], res["bytes"] = str(out / "index.html"), build_html(cfg, out, a.inline_pixi)
    gc = cfg.get("go_check")
    res["delivery"] = (f"proto_build {a.adapter}｜{cfg['game']}｜缺口 {res['gaps']}"
                       + (f"｜Go 設定檔 一致 {gc['match']} / 不一致 {gc['mismatch']} / 規格書缺 {gc['gap']}" if gc else ""))
    print(json.dumps({"success": True, "data": res}, ensure_ascii=False))
    if a.strict and gc and gc["mismatch"]:
        sys.exit(3)


if __name__ == "__main__":
    main()
