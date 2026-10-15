"""adapter：Tiger and Dragon（競品反解設計局，qt 模式）— 5×3 / 243 Ways、銅鑼變倍數 WILD、虎龍觸發三種金幣鎖格 Bonus。

FG 模型 = "coin-lock"：每手每個未鎖格依停入率落金幣 → 落下即鎖（可重置次數）→ 結束時橫向相鄰 ≥2 顆成組、
每顆翻值（箭頭 / 兩位數 / 一位數）由左至右連讀成一個數；Tiger & Dragon 另有解鎖列與 JACKPOT。
規則來源：prob-spec.md §4（odds / 觸發參數 / 輪帶組 / 客製 tiger_dragon 參數）；規格書沒寫的規則（G-*）已對 Go 引擎核對。
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from proto_common import M, num, walk_tables  # noqa: E402,F401

MODEL = "coin-lock"
GO = "data/slot/tiger-and-dragon/quicktest/engine"
BONUS = ["Tiger", "Dragon", "Tiger&Dragon"]


def _kv(tabs, cap=None, h3=None) -> dict:
    out = {}
    for x in tabs:
        t = x["t"]
        if t["cls"] != "kv" or (cap and x["cap"] != cap) or (h3 and h3 not in x["h3"]):
            continue
        for r in t["rows"]:
            out[r[0]] = (r[1], r[t["head"].index("來源")] if "來源" in t["head"] else "")
    return out


def _find(kv: dict, *keys):
    for k, v in kv.items():
        if any(s in k for s in keys):
            return v
    return (None, "")


def _ints(s) -> list[int]:
    return [int(x) for x in re.findall(r"-?\d+", str(s))]


def build(doc: dict, g: dict) -> dict:
    """§4 → board / paytable / strips / reelsets / mg（倍數 WILD）/ fg（金幣鎖格）+ gaps。"""
    P = walk_tables(doc, "params")
    odds = next(x["t"] for x in P if x["t"]["cls"] == "odds")
    H = odds["head"]
    paytable, tiers, symbols, special = {}, {}, [], []
    for r in odds["rows"]:
        code, grp = r[0], r[H.index("組")]
        if grp == "normal":
            paytable[code] = {k[1:]: num(r[H.index(k)]) or 0 for k in ("x3", "x4", "x5")}
            tiers[code] = "high" if code.startswith("M") else "low"
            symbols.append(code)
        else:
            special.append(code)
    symbols += special
    base = _kv(P, h3="基本資訊")
    trig = _kv(P, h3="觸發與上限")
    td = {k: v[0] for k, v in _kv(P, cap="tiger_dragon").items()}
    reels, rows = (_ints(_find(base, "盤面")[0]) + [5, 3])[:2]
    human = "\n".join(b.get("text", "") for s in doc["sections"] for b in s["blocks"] if b["kind"] == "human")
    m = re.search(r"基礎押注\s*(\d+)", human)
    bet = int(m.group(1)) if m else 75
    mw, mw_src = _find(trig, "MaxWin", "最大贏分倍數")
    strips = sorted(((int(re.search(r"組\s*(\d+)", f["name"]).group(1)), f["reels"]) for f in M.strip_fences(doc) if "主遊戲" in f["name"]))
    rs_tab = next(x for x in P if x["t"]["cls"] == "reelsets" and x["cap"] == "主遊戲")["t"]
    RH = rs_tab["head"]
    reelsets = [{"idx": int(num(r[0])), "use": [int(num(r[RH.index(f"R{i} 用組")])) for i in range(1, reels + 1)],
                 "w": int(num(r[RH.index("權重")])), "src": r[RH.index("來源")] if "來源" in RH else ""} for r in rs_tab["rows"]]
    gate, gate_src = _find(trig, "進免費遊戲門檻")
    rate, rate_src = _find(trig, "額外押注倍率", "Extra Bet")
    wild_name = next((r[H.index("名稱")] for r in odds["rows"] if r[0] == "WILD"), "")
    lo, hi = (_ints(wild_name) + [2, 10])[:2]
    cfg = {
        "board": {"rows": rows, "reels": reels, "slot_type": "WAYS", "bet": bet, "wild": "WILD",
                  "src": "§4 基本資訊；押注 = §1 機率人員簡述「基礎押注」（G-TD-1）",
                  "max_win": num(mw), "max_win_src": mw_src},
        "symbols": symbols, "paytable": paytable, "tiers": tiers,
        "strips": {"sets": [s for _, s in strips], "fake": strips[-1][1]},
        "reelsets": reelsets,
        "mg": {"wild_mult": {"from": "MY", "to": "WILD", "min": lo, "max": hi, "dist": "uniform",
                             "src": "§4 Odds 表 WILD 名稱「x2～x10」；分佈 G-TD-2"}},
        "fg": {
            "model": MODEL,
            "trigger": {"model": "tiger-dragon", "tiger": "SC_T", "dragon": "SC_D", "gate": int(num(gate) or 3), "mixed": 5,
                        "rate": int(num(rate) or 0), "src": f"{gate_src}；{rate_src}；混合 ≥5 優先 = G-TD-3"},
            "groups": BONUS,
            "bonus": [{"name": BONUS[i], "reels": _ints(td["bonus_reels"])[i], "rows": _ints(td["bonus_rows"])[i],
                       "spins": _ints(td["bonus_spins"])[i], "reset": _ints(td["bonus_reset"])[i], "coin_rate": _ints(td["coin_rate"])[i]}
                      for i in range(3)],
            "flip": {"arrow_w": int(num(td["flip_arrow_weight"])), "two_w": int(num(td["flip_two_weight"])), "one_w": int(num(td["flip_one_weight"])),
                     "one_dist": _ints(td["flip_one_dist"]), "two_min": int(num(td["flip_two_min"])), "two_max": int(num(td["flip_two_max"])),
                     "arrow_add_min": int(num(td["flip_arrow_add_min"])), "arrow_add_max": int(num(td["flip_arrow_add_max"]))},
            "unlock": {"base_rows": 3, "thresholds": _ints(td["unlock_thresholds"]), "bonus": 2},
            "jackpot": {"threshold": int(num(td["jackpot_threshold"])), "multiple": int(num(td["jackpot_multiple_td"])), "bonus": 2},
            "src": "§4 客製玩法參數 tiger_dragon（D-TD-11）",
        },
        "gaps": GAPS,
    }
    return cfg


def targets_extra(doc: dict) -> dict:
    """§2 BASE INFO 的 Ultra / Strong / Normal 列 → 依 recorder index 0/1/2 對應三種 Bonus（G-TD-7）。"""
    out = {}
    for x in walk_tables(doc, "data"):
        t = x["t"]
        if t["cls"] != "base":
            continue
        H = t["head"]
        for r in t["rows"]:
            k = {"Ultra": "Tiger", "Strong": "Dragon", "Normal": "Tiger&Dragon"}.get(r[0])
            if k:
                out[k] = {"rtp": num(r[H.index("RTP")]), "rate": num(r[H.index("觸發率")]), "freq": num(r[H.index("平均觸發局數")]),
                          "avg_win": num(r[H.index("平均倍率")]), "max": num(r[H.index("最大倍率")]), "spins": num(r[H.index("平均局數")])}
    return {"bonus": out}


GAPS = [
    {"id": "G-TD-1", "what": "基礎押注（分母）", "spec": "§4 無押注欄；只在 §1 人工區文字寫「基礎押注 75 credits」", "assume": "bet = 75",
     "check": "MG RTP 精算 vs §2", "auto": "mg_rtp", "go": f"{GO}/odds/odds_1.0.0.go:16 ConstBetCost = 75（硬編，不在 odds.json）"},
    {"id": "G-TD-2", "what": "倍數 WILD 的倍數分佈", "spec": "Odds 表名稱寫 x2～x10；參數備註（規格書附錄 E）假設權重 46/24/11/7/4/3/2/1/1", "assume": "均勻 2～10（與 Go 相同）",
     "check": "MG RTP 精算 vs §2 70.29%", "auto": "mg_rtp", "go": f"{GO}/game/game_process.go:170 WildMultMin + Intn(WildMultMax-WildMultMin+1) → 均勻；與附錄 E 假設不一致，需決議"},
    {"id": "G-TD-3", "what": "三種 Bonus 觸發優先序與隨機觸發", "spec": "§4 只有「進免費遊戲門檻 3 顆」與「額外押注倍率 6」", "assume": "虎+龍 ≥5 → T&D；虎 ≥3 → Tiger；龍 ≥3 → Dragon；否則各以 6/10000 × 顆數 隨機觸發",
     "check": "L1 精算三種觸發率 vs §2", "auto": "trig_split", "go": f"{GO}/check/check.go:46-91 specialGameCheck（extra_rate 被複用為萬分率，欄名「額外押注倍率」誤導）"},
    {"id": "G-TD-4", "what": "金幣鎖格流程", "spec": "tiger_dragon 參數只有數值；流程只在規格書文字", "assume": "每手逐格擲停入率；落下即鎖；有落下且 reset=1 → 次數重置；滿盤提前結束",
     "check": "L2 各 Bonus 平均局數 vs §2", "auto": "bonus_split", "go": f"{GO}/game/game_process.go:193-307 freeGameProcess"},
    {"id": "G-TD-5", "what": "結算：成組 / 翻值 / 連讀 / 箭頭", "spec": "flip_* 參數有值；「最左不可箭頭」「箭頭加到最左位」「兩位數佔兩位」沒寫", "assume": "依 Go settleGroup",
     "check": "L2 各 Bonus 均倍 vs §2", "auto": "bonus_split", "go": f"{GO}/game/game_process.go:328-373 settleGroup / flipKind"},
    {"id": "G-TD-6", "what": "T&D 解鎖列起始 3 列（由底算）與 JACKPOT", "spec": "unlock_thresholds 6/9/14/19/25、jackpot 32 / 1200 倍有值；起始列數沒寫", "assume": "底 3 列先開，達門檻當手多開一列；32 顆得 1200 × 押注",
     "check": "L2 T&D 均倍 vs §2", "auto": "bonus_split", "go": f"{GO}/game/game_process.go:209 unlockedRows = 3"},
    {"id": "G-TD-7", "what": "§2 Ultra / Strong / Normal 列的意義", "spec": "人工區說「範本殘留、勿誤讀」", "assume": "其實就是 Bonus index 0/1/2 = Tiger / Dragon / Tiger&Dragon",
     "check": "L2 各 Bonus 觸發率 / 均倍 / 平均局數 vs 那三列", "auto": "bonus_split", "go": f"{GO}/game/game_process.go:298 SpecialGameAddRecordWin(bonusType, …)；人工區註記應更正"},
    {"id": "G-TD-8", "what": "MaxWin 封頂範圍", "spec": "MaxWin 20000 倍", "assume": "對（MG + 該次 Bonus）合計封頂，扣在 Bonus", "check": "逐局對照",
     "go": f"{GO}/game/game_process.go:288 cap - mainResult.TotalWin"},
]


# ───────── Go 設定檔對照（--go-config <odds_1.0.0.json>）─────────
GO_SYM = {11: "M1", 12: "M2", 13: "M3", 14: "M4", 15: "M5", 16: "M6", 21: "A", 22: "K", 23: "Q", 24: "J", 1: "WILD", 2: "SC_T", 3: "SC_D", 4: "MY", 7: "COIN", 8: "ARROW"}


def go_rules(cfg: dict, go: dict) -> list[dict]:
    """規格書（game-config）⇄ Go odds.json 逐鍵對照。"""
    e, fg, R = go["extra_odds"], cfg["fg"], []

    def rule(key, spec, gov):
        R.append({"key": key, "ok": None if spec is None else spec == gov, "spec": spec if len(str(spec)) < 160 else str(spec)[:157] + "…",
                  "go": gov if len(str(gov)) < 160 else str(gov)[:157] + "…"})
    for sid, code in GO_SYM.items():
        if code in cfg["paytable"]:
            p = cfg["paytable"][code]
            rule(f"odds[{sid}] {code}", [0, 0, p["3"], p["4"], p["5"]], e["odds"][str(sid)])
    ok = all([GO_SYM.get(x, "?") for x in reel] == cfg["strips"]["sets"][k][i] for k, s in enumerate(go["main_game_reel_data"]) for i, reel in enumerate(s))
    rule("main_game_reel_data（附錄 Strip）", "%d 組 × %d 軸" % (len(cfg["strips"]["sets"]), cfg["board"]["reels"]), ("%d 組 × %d 軸" % (len(go["main_game_reel_data"]), cfg["board"]["reels"])) if ok else "不一致")
    rule("main_game_reel_index_set / weight", [[r["use"] for r in cfg["reelsets"]], [r["w"] for r in cfg["reelsets"]]], [e["main_game_reel_index_set"], e["main_game_reel_set_weight"]])
    rule("enter_free_game_gate", fg["trigger"]["gate"], e["enter_free_game_gate"])
    rule("extra_rate（隨機觸發萬分率）", fg["trigger"]["rate"], e["extra_rate"])
    rule("max_win", cfg["board"].get("max_win"), e["max_win"])
    td = e["tiger_dragon"]
    for k in ("bonus_reels", "bonus_rows", "bonus_spins", "bonus_reset", "coin_rate"):
        rule(f"tiger_dragon.{k}", [b[k.replace("bonus_", "")] if k != "coin_rate" else b["coin_rate"] for b in fg["bonus"]], td[k])
    F = fg["flip"]
    for a, b in (("arrow_w", "flip_arrow_weight"), ("two_w", "flip_two_weight"), ("one_w", "flip_one_weight"), ("one_dist", "flip_one_dist"),
                 ("two_min", "flip_two_min"), ("two_max", "flip_two_max"), ("arrow_add_min", "flip_arrow_add_min"), ("arrow_add_max", "flip_arrow_add_max")):
        rule(f"tiger_dragon.{b}", F[a], td[b])
    rule("tiger_dragon.unlock_thresholds", fg["unlock"]["thresholds"], td["unlock_thresholds"])
    rule("tiger_dragon.jackpot_threshold / multiple_td", [fg["jackpot"]["threshold"], fg["jackpot"]["multiple"]], [td["jackpot_threshold"], td["jackpot_multiple_td"]])
    rule("bet（Go 硬編 ConstBetCost，不在 odds.json）", cfg["board"]["bet"], 75)
    rule("倍數 WILD 範圍（Go 硬編 WildMultMin/Max）", [cfg["mg"]["wild_mult"]["min"], cfg["mg"]["wild_mult"]["max"]], [2, 10])
    return R
