#!/usr/bin/env python3
"""engine_trace_batch — 依 slot 總目錄，對每款 Go 世代遊戲挑一個快測引擎跑 engine_trace → 引擎回放試玩（⑦-lite）。

挑引擎：該款 slot_math_squad 資料夾下含 go.mod＋main.go 的目錄；排除「參考資料／簡易試算／觀察」；優先非道具卡／Buy Bonus／play bonus 版，
再依目錄名的版本號與日期取最新。挑選理由寫進 README（人可改 --pick 覆寫）。
用法：python engine_trace_batch.py --catalog data/slot/_catalog/catalog.yaml --msq <slot_math_squad> --repo <aidev 根> [--only 176,211] [--skip magic-lamp]
產出：data/slot/<slug>/game/replay/{trace.json, engine-trace.meta.json, stage.yaml, README.md}；output/slot/<slug>/game/replay/single/index.html
"""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, sys
import yaml

HERE = pathlib.Path(__file__).resolve().parent
SKIP_DIR = re.compile(r"參考資料|簡易試算|觀察|__MACOSX")
SIDE = re.compile(r"道具卡|buy ?bonus|play ?bonus|BB", re.I)
RTP_LO, RTP_HI = 80.0, 110.0  # 20 萬局樣本的合理區間；外面多半是押注單位錯或調參版
VER = re.compile(r"[Vv](\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)版|(20\d{6})|(\d{4})")


def vkey(p: str):
    nums = [float(next(g for g in m.groups() if g)) for m in VER.finditer(p)]
    return (not SIDE.search(p), max(nums) if nums else -1, p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalog", required=True); ap.add_argument("--msq", required=True); ap.add_argument("--repo", required=True)
    ap.add_argument("--only"); ap.add_argument("--skip", default="magic-lamp"); ap.add_argument("--n", type=int, default=2000); ap.add_argument("--sim", type=int, default=200000)
    ap.add_argument("--report")
    a = ap.parse_args()
    cat = yaml.safe_load(pathlib.Path(a.catalog).read_text(encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    skip = set(a.skip.split(",")) if a.skip else set()
    msq = pathlib.Path(a.msq) / "SLOT"
    repo = pathlib.Path(a.repo)
    reps = []
    for g in cat["games"]:
        if g["era"] != "go" or g["slug"] in skip or (only and str(g["game_id"]) not in only):
            continue
        engines = []
        for m in g["msq"]:
            base = msq / m["dir"]
            if not base.is_dir():
                continue
            for gm in base.rglob("go.mod"):
                d = gm.parent
                rel = d.relative_to(msq).as_posix()
                if (d / "main.go").is_file() and not SKIP_DIR.search(rel):
                    engines.append(rel)
        r = {"game_id": g["game_id"], "slug": g["slug"], "name": g.get("name_zh") or g.get("name_en"), "engines": engines}
        if not engines:
            r["error"] = "沒有含 main.go 的 Go 快測引擎"; reps.append(r); print(json.dumps(r, ensure_ascii=False)); continue
        tried, fallback = [], None
        for pick in sorted(engines, key=vkey, reverse=True):
            out = repo / "data/slot" / g["slug"] / "game/replay"
            p = subprocess.run([sys.executable, str(HERE / "engine_trace.py"), "--engine", str(msq / pick), "--n", str(a.n), "--sim", str(a.sim), "--out", str(out),
                                "--name", r["name"] or g["slug"], "--engine-label", f"slot_math_squad/SLOT/{pick}"], capture_output=True, text=True)
            try:
                res = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception:  # noqa: BLE001
                res = {"success": False, "error": p.stderr[-400:]}
            ok_rtp = bool(res.get("success")) and RTP_LO <= res["sim"]["rtp"] <= RTP_HI
            tried.append({"engine": pick, "ok": res.get("success"), "rtp_ok": ok_rtp, "error": (res.get("error") or "")[:300], "sim": res.get("sim")})
            if res.get("success") and not ok_rtp:
                tried[-1]["error"] = f"RTP {res['sim']['rtp']}% 不在 {RTP_LO}～{RTP_HI}%（押注單位或調參版可疑）"
                fallback = fallback or (pick, res)
                continue
            if res.get("success"):
                r.update(pick=pick, sim=res["sim"], tuned=res.get("tuned"), bet=res["bet"], grid_ok=res["grid_ok"], symbols=len(res["symbols"]))
                (out / "engine-trace.jsonl").unlink(missing_ok=True)
                (out / "stage.yaml").write_text(
                    "# 引擎回放試玩（⑦-lite）建置設定 —— python .kiro/skills/ark-game-proto/scripts/stage/stage_build.py "
                    f"--game .kiro/skills/ark-game-proto/scripts/stage/replay/game.js --odds data/slot/{g['slug']}/game/replay/trace.json "
                    f"--out output/slot/{g['slug']}/game/replay/single --single\n"
                    "game: ../../../../../.kiro/skills/ark-game-proto/scripts/stage/replay/game.js\nodds: trace.json\nassets_base: []\n", encoding="utf-8")
                b = subprocess.run([sys.executable, str(HERE / "stage/stage_build.py"), "--game", str(HERE / "stage/replay/game.js"), "--odds", str(out / "trace.json"),
                                    "--out", str(repo / "output/slot" / g["slug"] / "game/replay/single"), "--single"], capture_output=True, text=True)
                r["build"] = json.loads(b.stdout.strip().splitlines()[-1]).get("success") if b.stdout.strip() else False
                write_readme(out, g, r, tried)
                break
        r["tried"] = tried
        if not r.get("pick"):
            r["error"] = ("RTP 可疑：" + tried[-1]["error"]) if fallback else "所有引擎都失敗"
            if fallback:  # 不出試玩，只留 meta 供人工確認
                r["suspect"] = {"engine": fallback[0], "sim": fallback[1]["sim"], "bet": fallback[1]["bet"]}
                for f in ("trace.json", "engine-trace.jsonl", "stage.yaml", "README.md"):
                    (repo / "data/slot" / g["slug"] / "game/replay" / f).unlink(missing_ok=True)
        reps.append(r)
        print(json.dumps({k: r.get(k) for k in ("game_id", "slug", "pick", "sim", "build", "error")}, ensure_ascii=False), flush=True)
    if a.report:
        pathlib.Path(a.report).write_text(json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8")


def write_readme(out, g, r, tried):
    s = r["sim"]
    t = "\n".join(f"| `{x['engine']}` | {'✅' if x['ok'] else '❌ ' + x['error'][:120].replace('|', '／').replace(chr(10), ' ')} |" for x in tried)
    out.joinpath("README.md").write_text(f"""# {r['name']}｜引擎回放試玩（⑦-lite）

> ark-game-proto 1.5.0 `engine_trace.py`：把 slot_math_squad 的 Go 快測引擎原樣跑 {s['spins']:,} 局，錄前 {r.get('grid_ok', 0):,} 局的主遊戲盤面與贏分，
> 由通用回放遊戲包（`scripts/stage/replay/game.js`）循環播放。**數學 = 快測引擎，不是規格書**；特色遊戲只顯示贏分摘要。
> 正式 ⑦（規格書 → ⑥ 玩法模型 → Stage 演出）尚未做。

| 項目 | 值 |
|---|---|
| 引擎 | `slot_math_squad/SLOT/{r['pick']}` |
| 試玩關掉的開關 | {json.dumps(r.get('tuned') or {}, ensure_ascii=False)}（道具卡／Buy Bonus／保底等，改走一般模式）|
| 20 萬局樣本 | 總 RTP {s['rtp']}%、主遊戲 {s['rtp_main']}%、特色觸發 {s['feature_rate']}% |
| 押注（Bet_Cost × Line_bet）| {r['bet']} |

⚠️ 引擎目錄可能是當時的調參版，不一定等於線上；線上對帳看 `../../ref/README.md`（R-1）。

## 挑引擎紀錄

| 引擎目錄 | 結果 |
|---|---|
{t}

## 重跑

```bash
python .kiro/skills/ark-game-proto/scripts/engine_trace.py --engine "<slot_math_squad>/SLOT/{r['pick']}" --n 2000 --out data/slot/{g['slug']}/game/replay --name "{r['name']}"
python .kiro/skills/ark-game-proto/scripts/stage/stage_build.py --game .kiro/skills/ark-game-proto/scripts/stage/replay/game.js --odds data/slot/{g['slug']}/game/replay/trace.json --out output/slot/{g['slug']}/game/replay/single --single
```
""", encoding="utf-8")


if __name__ == "__main__":
    main()
