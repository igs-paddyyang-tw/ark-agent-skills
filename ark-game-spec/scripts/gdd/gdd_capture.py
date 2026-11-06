#!/usr/bin/env python3
"""gdd_capture —— 實機取素材 → 競品分析素材包（2.10.0；原 aiqa scripts/aiqa_asset_pack.py 技能化）。

輸入是「取素材閉環」④ Register 的素材目錄（實機截圖、裁圖，內部參考 L3）：

  <capture>/asset-map.yaml   每個碼對哪張圖（symbols）、畫面截圖（screens，只收 *_masked）、各玩法規則（features.rules）
  <capture>/analysis.md      （選用）競品分析；有就合成單檔 HTML

流程（只組裝 ark-game-spec 既有零件，不重造）：
  ① asset-map → gdd-pack（契約 v1）；賠率取自機率設定檔 --odds-json（預設 <repo>/data/slot/<slug>/quicktest/config/live.json，
     契約：odds[符號][連線數−1]，列序＝display_codes）→ symbols.odds = [5 連, 4 連, 3 連]
  ② gdd_run --pack --export → 素材總覽.html＋企劃交付夾（symbols／illustrations／spec-reference-images）
  ③ 有 analysis.md → gs_bundle → 「分析＋素材總覽」單檔 HTML（圖內嵌）
  ④ 交付夾＋單檔＋analysis.md → zip

用法：
  python scripts/gdd/gdd_capture.py --capture <dir> [--repo <aidev 根>] [--odds-json <live.json>] [--out <pack>] [--no-zip]
  python scripts/gs_run.py --stage capture --capture <dir> …（同義）
--out 預設 <repo>/data/gdd/<slug>（該路徑應 gitignore —— 截圖屬內部參考，不進 git）。

守門（exit 2 BAD_INPUT）：
  - 截圖檔名必須含 `_masked`（未遮蔽玩家資訊的圖不收）
  - symbols 的 code 必須存在於 odds-json 的 display_codes（WW／SS／SF／M1…／A K Q J 10）
  - 同一個 code 只能一筆 role=symbol，其餘外觀標 performance
下游失敗（gdd lint、交付夾斷鏈、bundle 預算）→ 原樣回傳該 runner 的錯誤碼。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from _lib import run_common as C  # noqa: E402

LOW = ["A", "K", "Q", "J", "10", "9", "8", "7"]


def code_of(display: int) -> str:
    """回放顯示碼 → 符號碼（與 ark-game-proto replay 命名一致：1 WW、2 SS、3 SF、11～ M1～、21～ A K Q J 10…）。"""
    if display == 1:
        return "WW"
    if display == 2:
        return "SS"
    if display == 3:
        return "SF"
    if 11 <= display <= 19:
        return f"M{display - 10}"
    if 21 <= display <= 28:
        return LOW[display - 21]
    return f"S{display}"


def load_odds(path: pathlib.Path) -> tuple[dict[str, list[int]], dict[str, int]]:
    """機率設定檔 → {code: [5 連, 4 連, 3 連]}（只收有 3～5 連賠率的符號）與 {code: 顯示碼}。"""
    if not path.is_file():
        C.fail("BAD_INPUT", f"找不到機率設定檔 {path}", "給 --odds-json，或確認 <repo>/data/slot/<slug>/quicktest/config/live.json 存在")
    d = json.loads(path.read_text(encoding="utf-8"))
    codes, odds = d.get("display_codes") or [], d.get("odds") or []
    if not codes or len(codes) != len(odds):
        C.fail("BAD_INPUT", "機率設定檔的 display_codes 與 odds 列數不一致（或缺）", "", {"codes": len(codes), "odds": len(odds)})
    by_code, disp = {}, {}
    for dc, row in zip(codes, odds):
        c = code_of(int(dc))
        disp[c] = int(dc)
        if len(row) >= 5 and any(row[2:5]):
            by_code[c] = [int(row[4]), int(row[3]), int(row[2])]
    return by_code, disp


def build_pack(cap: pathlib.Path, amap: dict, out: pathlib.Path, odds: dict, disp: dict, odds_label: str) -> dict:
    """asset-map → gdd-pack（gdd.yaml／symbols.yaml／screens.yaml／info.yaml／rules／assets 三夾）。"""
    slug, game = amap["slug"], amap["game"]
    assets = out / "assets"
    if assets.exists():
        shutil.rmtree(assets)                                   # 只重建本工具產的資產夾
    for d in ("symbols", "illustrations", "spec-reference-images"):
        (assets / d).mkdir(parents=True, exist_ok=True)
    (out / "rules").mkdir(parents=True, exist_ok=True)

    missing, unmasked, unknown, symbols, seen = [], [], [], [], set()
    for s in amap.get("symbols", []) or []:
        src = cap / s["file"]
        if not src.is_file():
            missing.append(s["file"])
            continue
        code, role, group = str(s["code"]), s.get("role", "symbol"), s.get("group", "normal")
        if code not in disp:
            unknown.append(code)
        if role == "symbol":
            if code in seen:
                C.fail("BAD_INPUT", f"code {code} 有兩筆 role=symbol", "同一個碼的其他外觀請標 role: performance")
            seen.add(code)
        shutil.copy2(src, assets / "symbols" / src.name)
        desc = "；".join(x for x in (s.get("desc"), f"依據：{s['evidence']}" if s.get("evidence") else None) if x)
        symbols.append({"code": code, "group": group, "sym_id": disp.get(code) if role == "symbol" else None,
                        "name": s["name"], "file": src.name, "soft": False, "role": role,
                        "odds": odds.get(code) if group == "normal" else None, "scene": s.get("scene", "主遊戲"),
                        **({"flag": s["flag"]} if s.get("flag") else {}), **({"desc": desc} if desc else {})})

    screens = []
    for sc in amap.get("screens", []) or []:
        src = cap / sc["file"]
        if "_masked" not in src.stem:
            unmasked.append(sc["file"])
            continue
        if not src.is_file():
            missing.append(sc["file"])
            continue
        shutil.copy2(src, assets / "illustrations" / src.name)
        screens.append({"feature": sc["feature"], "step": str(sc["step"]), "title": sc["title"],
                        "file": src.name, "desc": sc.get("desc", sc["title"])})
    if missing or unmasked or unknown:
        C.fail("BAD_INPUT", "素材檢查不通過", "缺圖補齊、截圖先遮蔽（*_masked）、code 對齊機率設定檔 display_codes",
               {"missing": missing, "unmasked": unmasked, "unknown_codes": unknown})

    features = []
    for f in amap.get("features", []) or []:
        rp = f"rules/{f['id']}.md"
        (out / rp).write_text((f.get("rules") or "").strip() + "\n", encoding="utf-8")
        features.append({"id": f["id"], "title": f["title"], "rules": rp})

    lv = amap.get("unlock_level")
    spec = [
        {"k": "遊戲", "v": f"{game}（{amap.get('title_en', '')}）"},
        {"k": "GameID／server_id", "v": f"{amap.get('game_id', '—')}／{amap.get('server_id', '—')}"},
        {"k": "平台", "v": amap.get("platform", "—")},
        {"k": "解鎖等級", "v": f"Lv{lv}" if lv else "—", **({"short": f"Lv{lv}", "short_k": "解鎖"} if lv else {})},
        {"k": "素材取得", "v": f"{amap.get('captured', '—')}・{amap.get('captured_by', '—')}"},
    ] + list(amap.get("spec_extra") or [])
    gdd = {
        "contract": "1", "slug": slug, "title": f"{game} 競品分析素材總覽", "short_title": game,
        "subtitle": f"實機取素材 → gdd-pack（ark-game-spec gdd_capture）；賠率取自 {odds_label}。內部文件：截圖已遮蔽玩家資訊，素材僅供內部參考，不得進正式成品。",
        "domain": amap.get("domain", "slot-game"), "status": "draft", "distribution": "internal",
        "assets": {"root": "assets", "symbols": "symbols", "screens": "illustrations", "reference": "spec-reference-images"},
        "spec": spec, "spec_note": f"來源：asset-map.yaml；取素材紀錄見 {amap.get('capture_log', '—')}",
        "symbol_groups": [{"id": "normal", "title": "一般符號"}, {"id": "special", "title": "特殊符號"}],
        "symbols_note": "賠率欄為 [5 連, 4 連, 3 連] × 線注；flag 標記的對應為推定或排除法。",
        "odds_order": [s["code"] for s in symbols if s["group"] == "normal" and s["role"] == "symbol"],
        "features": features, "build": {"output": "素材總覽.html", "bundle_html": f"{game}_素材總覽.html"},
    }
    info = {"contract": "1", "langs": [{"id": "tw", "label": "繁中"}], "default_lang": "tw", "placeholders": {},
            "blocks": [{"t": "h", "tw": "賠率表", "en": "ODDS TABLE", "widget": "odds_grid"},
                       {"t": "p", "id": "info-odds", "tw": "賠率 × 線注；WILD 替代除 SCATTER 外的符號。"}]}
    for name, obj in (("gdd.yaml", gdd), ("symbols.yaml", {"contract": "1", "symbols": symbols}),
                      ("screens.yaml", {"contract": "1", "screens": screens}), ("info.yaml", info)):
        (out / name).write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"symbols": len(symbols), "screens": len(screens), "features": len(features)}


def step(script: pathlib.Path, args: list[str]) -> dict:
    """跑 ark-game-spec 內的下游 runner；失敗就把它的錯誤原樣往上拋。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    p = subprocess.run([sys.executable, "-X", "utf8", str(script), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    line = next((ln for ln in reversed((p.stdout or "").strip().splitlines()) if ln.startswith("{")), "")
    try:
        envl = json.loads(line) if line else {}
    except json.JSONDecodeError:
        envl = {}
    if p.returncode != 0:
        err = envl.get("error") or {}
        C.fail(err.get("code", "QUERY_FAILED"), f"{script.name} 失敗（rc={p.returncode}）：{err.get('message', '')}",
               err.get("hint") or (p.stderr or "")[-600:], {"envelope": envl})
    return envl.get("data") or {}


def main() -> None:
    ap = argparse.ArgumentParser(description="ark-game-spec gdd_capture：實機取素材 → 競品分析素材包", allow_abbrev=False)
    ap.add_argument("--capture", required=True, help="素材目錄（含 asset-map.yaml）")
    ap.add_argument("--repo", help="aidev 根（找 data/slot/<slug>/quicktest/config/live.json 與預設輸出）；預設 ARK_GAME_ROOT 或目前目錄")
    ap.add_argument("--odds-json", help="機率設定檔（display_codes＋odds）；優先於 --repo 推導")
    ap.add_argument("--out", help="gdd-pack 位置（預設 <repo>/data/gdd/<slug>）")
    ap.add_argument("--analysis", help="分析 md（預設 <capture>/analysis.md，存在才合成單檔 HTML）")
    ap.add_argument("--no-zip", action="store_true")
    a = ap.parse_args()

    cap = pathlib.Path(a.capture).resolve()
    amap_p = cap / "asset-map.yaml"
    if not amap_p.is_file():
        C.fail("BAD_INPUT", f"找不到 {amap_p}", "取素材閉環 ④ Register 要先寫 asset-map.yaml")
    amap = yaml.safe_load(amap_p.read_text(encoding="utf-8")) or {}
    for k in ("slug", "game"):
        if not amap.get(k):
            C.fail("BAD_INPUT", f"asset-map.yaml 缺 {k}")
    slug, game = amap["slug"], amap["game"]
    repo = pathlib.Path(a.repo or os.environ.get("ARK_GAME_ROOT") or ".").resolve()
    odds_path = pathlib.Path(a.odds_json).resolve() if a.odds_json else repo / "data" / "slot" / slug / "quicktest" / "config" / "live.json"
    out = pathlib.Path(a.out).resolve() if a.out else repo / "data" / "gdd" / slug
    out.mkdir(parents=True, exist_ok=True)
    try:
        odds_label = odds_path.relative_to(repo).as_posix()
    except ValueError:
        odds_label = odds_path.name

    odds, disp = load_odds(odds_path)
    counts = build_pack(cap, amap, out, odds, disp, odds_label)
    gdd = step(HERE / "gdd_run.py", ["--pack", str(out), "--export"])

    bundle_html = None
    analysis = pathlib.Path(a.analysis) if a.analysis else cap / "analysis.md"
    if analysis.is_file():
        shutil.copy2(analysis, out / "analysis.md")
        bundle_html = f"{game}_競品分析素材.html"
        (out / "bundle.yaml").write_text(yaml.safe_dump({
            "bundle": "1", "title": f"{game} 競品分析素材", "out": bundle_html, "quality": "standard", "budget_mb": 8,
            "parts": [{"kind": "md", "id": "analysis", "label": "競品分析", "path": "analysis.md"},
                      {"kind": "gdd", "id": "gdd", "label": "素材總覽", "pack": "."}]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        step(HERE.parent / "bundle" / "gs_bundle.py", ["--bundle", str(out / "bundle.yaml")])

    zip_path = None
    if not a.no_zip:
        zip_path = out / f"{slug}_競品分析素材包_{dt.date.today():%Y%m%d}.zip"
        root = f"{slug}_競品分析素材包"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            exp = out / "export"
            for f in sorted(exp.rglob("*")) if exp.is_dir() else []:
                if f.is_file():
                    z.write(f, f"{root}/素材總覽/{f.relative_to(exp).as_posix()}")
            for name in (bundle_html, "analysis.md"):
                if name and (out / name).is_file():
                    z.write(out / name, f"{root}/{name}")
            z.writestr(f"{root}/README.txt",
                       f"{game}（{slug}）競品分析素材包｜內部文件，勿外流\n"
                       f"- {bundle_html or '（無單檔版）'}：分析＋素材總覽單檔（圖已內嵌）\n"
                       "- 素材總覽/：企劃樣板交付夾（HTML＋symbols／illustrations／spec-reference-images）\n"
                       "- analysis.md：分析原文（給 AI／知識庫）\n"
                       "截圖已遮蔽玩家資訊；素材為內部參考，不得放進正式成品。\n")

    C.emit({"out": str(out), "counts": counts, "lint": gdd.get("lint", {}).get("status") if isinstance(gdd.get("lint"), dict) else None,
            "bundle_html": bundle_html, "zip": str(zip_path) if zip_path else None,
            "zip_mb": round(zip_path.stat().st_size / 1e6, 2) if zip_path else None}, {"stage": "capture"})


if __name__ == "__main__":
    main()
