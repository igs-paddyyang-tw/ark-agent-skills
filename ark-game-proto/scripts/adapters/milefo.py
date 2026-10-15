"""adapter：彌勒佛（milefo）— 3×5 All Ways、M-1 換帶輪帶組、SC/SS 進 FG、金幣 / 鯉魚 / 金龍 / 彩龍 FG。

FG 模型 = "collect-mult"：FG 贏分 = (基底 + Σ加分物件) × (1 + Σ乘倍物件)。
規則來源：prob-spec.md 參數表（M-1～F-5）；規格書沒寫的三條（G-1～G-3）已對 Go 快測 game_process.go 核對。
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from proto_common import M, num, walk_tables, by_tid, src_of, _dual, _yesno, _weights, _matrix  # noqa: E402,F401

MODEL = "collect-mult"


def build(doc: dict, g: dict) -> dict:
    """彌勒佛玩法 adapter：M-1～M-5、F-1～F-5 → config.mg / config.fg。"""
    P = walk_tables(doc, "params")
    S = g["strips_raw"]
    strips = {"set0": S["main_strip / Reels_0"], "set1": S["main_strip / Reels_1"],
              "fake": S.get("fake_strip / 假轉") or S.get("main_strip / 假轉")}
    m1 = by_tid(P, "M-1")[0]["t"]
    H = m1["head"]
    reelsets = []
    for r in m1["rows"]:
        if num(r[0]) is None:
            continue
        reelsets.append({"idx": int(num(r[0])), "flags": [int(num(r[H.index(f"R{i}")])) for i in range(1, 6)],
                         "w": int(num(r[H.index("權重")])), "note": r[H.index("組合說明")] if "組合說明" in H else "",
                         "spec_total": num(r[H.index("TOTAL RTP")]), "spec_fg": num(r[H.index("FG RTP")]), "src": src_of(r, H)})
    groups = [k for k in _weights(by_tid(P, "F-1")[0]["t"]) if k != "src"]
    f2 = {x["cap"]: _matrix(x["t"]) for x in by_tid(P, "F-2")}

    def f2get(key):
        return next(v for k, v in f2.items() if k.startswith(key))
    f3 = by_tid(P, "F-3-1")[0]["t"]
    order = {r[0]: {h: int(num(r[i])) for i, h in enumerate(f3["head"]) if h in ("金幣", "鯉魚", "金龍", "彩龍")} for r in f3["rows"]}
    f43 = by_tid(P, "F-4-3")
    keep = {}
    for x in f43:
        t = x["t"]
        keep["gold" if "金龍" in t["head"][0] else "color"] = [int(num(c) or 0) for c in t["rows"][0][1:-1]]
    kv1 = lambda tid: num(by_tid(P, tid)[0]["t"]["rows"][0][1])  # noqa: E731
    return {
        "strips": strips,
        "reelsets": reelsets,
        "mg": {"fake_scores": _dual(by_tid(P, "M-2")[0]["t"]) | {"tid": "M-2"},
               "tease": _weights(by_tid(P, "M-4")[0]["t"]) | {"tid": "M-4", "rule": "R1–R4 SC ≥ 6 且 R5 SS ≥ 1"}},
        "fg": {
            "trigger": {"symbols": ["SC", "SS"], "min": 6, "src": "推定 G-1（§2 觸發面 6–14 顆；見 gaps）"},
            "groups": groups,
            "group_w": _weights(by_tid(P, "F-1")[0]["t"]) | {"tid": "F-1"},
            "preview": _yesno(by_tid(P, "M-3-1")[0]["t"]) | {"tid": "M-3-1"},
            "all888": _yesno(by_tid(P, "M-3-2")[0]["t"]) | {"tid": "M-3-2"},
            "entry_scores": _dual(by_tid(P, "M-5")[0]["t"]) | {"tid": "M-5"},
            "items": {
                "coin": {"count": f2get("金幣・出現"), "odds": f2get("金幣・分數"), "mult": 0},
                "carp": {"count": f2get("鯉魚・出現"), "odds": f2get("鯉魚・分數"), "mult": 0},
                "gold": {"count": f2get("金龍"), "mult": 1},
                "color": {"count": f2get("彩龍"), "mult": 2},
            },
            "order": {"first2": order.get("前兩次抽取"), "later": order.get("第三次以後"), "tid": "F-3-1"},
            "revive": {"threshold": kv1("F-4-1"), "chance": _weights(by_tid(P, "F-4-2")[0]["t"]), "keep": keep, "tid": "F-4"},
            "big_text": kv1("F-5"),
            "ss_mul_mode": "sc_sum",
            "model": MODEL,
        },
        "gaps": GAPS,
    }


GO = "data/slot/milefo/quicktest/engine/game/game_process.go"
GAPS = [
    {"id": "G-1", "what": "FG 觸發條件", "spec": "§3 只寫「特色觸發條件?」；§2 觸發面列 6–14 顆", "assume": "盤面 SC+SS ≥ 6 觸發",
     "check": "L1 精算觸發率 vs §2 FG 觸發率", "auto": "fg_rate", "go": f"{GO}:204 triggerFG := (scCount + ssCount) >= EnterFreeGameGate[0]（=6）"},
    {"id": "G-2", "what": "SS 的 *2/*3/*4 語意", "spec": "M-5 SS 欄同時有分數與 *k", "assume": "*k 乘到 SC 分數總和，SS 數值另加",
     "check": "L1 平均初始基底 vs §2 15.73、進場 SC 顆數 → 均 FG 倍率", "auto": "fg_base", "go": f"{GO}:342 initialBase = scTotal*totalSSMul + ssValuePart"},
    {"id": "G-3", "what": "FG 贏分公式", "spec": "F-2 只給次數與分數；§2 給 均乘倍 / 均基底", "assume": "(基底 + Σ金幣 + Σ鯉魚) × (1 + 金龍×1 + 彩龍×2)",
     "check": "L1 各組 E[乘倍] vs §2 各組別詳細；L2 各組均贏分", "auto": "fg_groups", "go": f"{GO}:372,382 totalWin = (initialBase + fgAmount) * (1 + gold + color*2)"},
    {"id": "G-4", "what": "M-2 / M-4 / F-3-1 / F-4 是否影響 RTP", "spec": "假轉分數、彩色聽牌、出場順序、復活皆在參數表", "assume": "演出層：結果先決，只用演出 RNG",
     "check": "演出 vs 非演出同 seed 結果一致（core_test）", "go": "Go 設定檔有 FakeSC/RainbowListen/BagOrder/Revive* 參數，但 game_process.go 完全不讀 → 確定不影響 RTP"},
    {"id": "G-5", "what": "§1「規格簡述」分頁", "spec": "xlsx 殘留 5×5 寶箱範本", "assume": "忽略，以參數表 3×5 All Ways 為準", "check": "人工確認（xlsx 待清理）"},
    {"id": "G-6", "what": "MaxWin 封頂值", "spec": "§2 只寫旗標「開MAXWIN」，參數表沒有封頂倍數", "assume": "取 Go 設定檔 MaxWin；MG+FG 合計封頂、FG 分項不封頂",
     "check": "逐局對照含封頂局（4,000 萬手 2 局觸頂）", "go": f"{GO}:152 maxWinCap := MaxWin * Line_bet*Bet_Cost（a-standard.json MaxWin=10000）；規格書應補一列"},
]

# ───────── Go 設定檔對照（proto_build --go-config）─────────
GO_SYM = {1: "WW", 2: "SC", 3: "SS", 11: "M1", 12: "M2", 13: "M3", 14: "M4", 15: "M5", 21: "FA", 22: "FK", 23: "FQ"}


def _rstrip0(xs):
    xs = list(xs)
    while xs and xs[-1] == 0:
        xs.pop()
    return xs


def go_rules(cfg: dict, go: dict) -> list[dict]:
    """規格書（game-config）⇄ Go 設定檔 逐鍵對照；回 [{key, ok, spec, go}]。"""
    fg, G = cfg["fg"], cfg["fg"]["groups"]
    R = []

    def rule(key, spec, gov, norm=lambda x: x):
        R.append({"key": key, "ok": None if spec is None else norm(spec) == norm(gov), "spec": spec if len(str(spec)) < 160 else str(spec)[:157] + "…",
                  "go": gov if len(str(gov)) < 160 else str(gov)[:157] + "…"})
    rule("bet = Line_bet × Bet_Cost", cfg["board"]["bet"], go["Line_bet"] * go["Bet_Cost"])
    for code, sid in [(v, k) for k, v in GO_SYM.items() if v in cfg["paytable"]]:
        p = cfg["paytable"][code]
        rule(f"Odds[{sid}] {code}", [0, 0, p.get("3", 0), p.get("4", 0), p.get("5", 0)], go["Odds"][str(sid)])
    rule("EnterFreeGameGate", fg["trigger"]["min"], go["EnterFreeGameGate"][0])
    rule("MainGameReelSetWeight（M-1）", [r["w"] for r in cfg["reelsets"]], go["MainGameReelSetWeight"])
    ok = True
    for k, rs in enumerate(cfg["reelsets"]):
        gi = go["MainGameReelIndexSet"][k][0]
        for i, f in enumerate(rs["flags"]):
            if cfg["strips"]["set%d" % f][i] != [GO_SYM[x] for x in go["MainGameReelData"][gi][i]]:
                ok = False
    rule("MainGameReelData × 10 組（Strip × M-1 旗標）", "50 軸", "50 軸" if ok else "不一致")
    rule("FreeGameTypeWeight（F-1）", [fg["group_w"][g] for g in G], go["FreeGameTypeWeight"])
    rule("FishAnnouncementWeights（M-3-1）", [fg["preview"][g] for g in G], go["FishAnnouncementWeights"])
    rule("FishAllMaxSCWeights（M-3-2）", [fg["all888"][g] for g in G], go["FishAllMaxSCWeights"])
    es = fg["entry_scores"]
    rule("FGEnterSC（M-5）", [[x["v"] for x in es["sc"]], [x["w"] for x in es["sc"]]], [go["FGEnterSCScores"], go["FGEnterSCWeights"]])
    rule("FGEnterSS（M-5，*k = 負值）", [[-x["mul"] if "mul" in x else x["v"] for x in es["ss"]], [x["w"] for x in es["ss"]]], [go["FGEnterSSScores"], go["FGEnterSSWeights"]])
    fs = cfg["mg"]["fake_scores"]
    rule("FakeSC / FakeSS（M-2）", [[x["v"] for x in fs["sc"]], [x["w"] for x in fs["sc"]], [-x["mul"] if "mul" in x else x["v"] for x in fs["ss"]], [x["w"] for x in fs["ss"]]],
         [go["FakeSCScores"], go["FakeSCWeights"], go["FakeSSScores"], go["FakeSSWeights"]])
    it = fg["items"]
    for name, key in [("coin", "CoinTimesWeights"), ("carp", "FishTimesWeights"), ("gold", "GoldDragonTimesWeights"), ("color", "ColorDragonTimesWeights")]:
        rule(f"{key}（F-2）", [_rstrip0(it[name]["count"][g]) for g in G], [_rstrip0(x) for x in go[key]])
    rule("CoinScores / Weights（F-2）", [it["coin"]["odds"]["values"], [it["coin"]["odds"][g] for g in G]], [go["CoinScores"], go["CoinScoreWeights"]])
    rule("FishScores / Weights（F-2）", [it["carp"]["odds"]["values"], [it["carp"]["odds"][g] for g in G]], [go["FishScores"], go["FishScoreWeights"]])
    o = fg["order"]
    rule("BagOrder（F-3-1，演出）", [[o["first2"][k] for k in ("金幣", "鯉魚", "金龍", "彩龍")], [o["later"][k] for k in ("金幣", "鯉魚", "金龍", "彩龍")]],
         [go["BagOrderFirst2Weights"], go["BagOrderAfter2Weights"]])
    rv = fg["revive"]
    rule("Revive（F-4，演出）", [rv["threshold"], [rv["chance"]["是"], rv["chance"]["否"]], _rstrip0(rv["keep"]["gold"]), _rstrip0(rv["keep"]["color"])],
         [go["ReviveThreshold"], go["ReviveWeights"], _rstrip0(go["ReviveGoldDragonKeepWeights"]), _rstrip0(go["ReviveColorDragonKeepWeights"])])
    rule("RainbowListenWeights（M-4，演出）", [cfg["mg"]["tease"]["是"], cfg["mg"]["tease"]["否"]], go["RainbowListenWeights"])
    rule("MaxWin（G-6）", cfg["board"].get("max_win"), go["MaxWin"])
    return R


def go_fill(cfg: dict, go: dict) -> list[str]:
    """規格書缺、Go 設定檔有的值 → 補進 config（標來源）；回補了哪些鍵。"""
    filled = []
    if not cfg["board"].get("max_win") and go.get("MaxWin"):
        cfg["board"]["max_win"] = go["MaxWin"]
        cfg["board"]["max_win_src"] = "Go 設定檔 MaxWin（規格書缺，G-6）"
        filled.append("max_win")
    return filled
