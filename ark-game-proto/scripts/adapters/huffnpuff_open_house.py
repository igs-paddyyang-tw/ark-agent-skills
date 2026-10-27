"""adapter：Huff N' Puff Open House（huffnpuff-open-house）— 5×3 243 Ways、四建材觸發 House Spin ×4 ＋ ≥6 顆 Open House 四房闖關。

FG 模型 = "huff-house"（slot-core MODELS['huff-house']）：
  主遊戲停輪 → Ways（WILD 從第 2 軸起替代）→ 建材合計 ≥6 → Open House；否則依 GD→BR→SK→ST 每顆各擲觸發率（先中先得）→ House Spin。
  數學流只用 Float64（C.fdraw），抽值順序與 Go internal/engine/huff 一致 → 可同 Go math/rand seed 逐局對照（tests/huff_parity.js）。

來源分工：
  - 盤面 / 賠率 / 輪帶組權重 / huff 參數 P-03～P-12：prob-spec §4 參數表（ark-game-prob 1.4.2+ huff 模式）。
  - 輪帶：prob-spec「## 輪帶 Strip（附錄）」3 組。
  - §2 各玩法目標（頻率 / 均倍 / RTP / 平均手數）：qt-report/rtp-report.json（targets_extra）。
  - 規格書沒寫的（WILD 起始軸）→ go_fill 由 odds.json 補並標來源（G-HF-1）。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from proto_common import M, num, walk_tables  # noqa: E402,F401

MODEL = "huff-house"
DATA = "data/slot/huffnpuff-open-house"
REPORT_REL = "quicktest/qt-report/rtp-report.json"
MATS = [("ST", "SC_STRAW"), ("SK", "SC_STICK"), ("BR", "SC_BRICK"), ("GD", "SC_GOLD")]     # 建材碼 → 規格書符號碼（sym_id 3..6）
GROUPS = ["ST", "SK", "BR", "GD", "OH"]
REPORT_KEY = {"ST": "StrawSpin", "SK": "StickSpin", "BR": "BrickSpin", "GD": "PalaceSpin", "OH": "OpenHouse"}


def _tables(doc: dict) -> list[dict]:
    return walk_tables(doc, "params")


def _huff_kv(tabs) -> dict:
    """「特色玩法參數（huff 引擎）」表 → {參數名: (值字串, 來源)}。"""
    for x in tabs:
        if "huff" in x["h3"]:
            return {r[0]: (r[1], r[2] if len(r) > 2 else "") for r in x["t"]["rows"]}
    sys.exit("prob-spec.md §4 缺「特色玩法參數（huff 引擎）」表：需 ark-game-prob 1.4.2+ 以 huff 模式重產")


def _j(kv: dict, key: str):
    """取 huff 表某列並解析（JSON 字面值或數字）。"""
    hit = next((k for k in kv if k.startswith(key) or key in k), None)
    if hit is None:
        sys.exit(f"prob-spec.md huff 參數表缺「{key}」")
    s = kv[hit][0].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        v = num(s)
        return v if v is not None else s


def build(doc: dict, g: dict) -> dict:
    tabs = _tables(doc)
    # Odds 表：x3..x5 有數字的列 = 線賠符號（WILD / 建材 / 框為「不適用」）
    pt = next(x["t"] for x in tabs if "Odds" in x["h3"])
    H = pt["head"]
    paytable, tiers, sym_id = {}, {}, {}
    for r in pt["rows"]:
        code = r[H.index("符號")]
        sym_id[code] = int(num(r[H.index("sym_id")]))
        if num(r[H.index("x3")]) is None:
            continue
        paytable[code] = {k: int(num(r[H.index("x" + k)])) for k in ("3", "4", "5")}
        tiers[code] = "high" if code.startswith("M") else "low"
    # 輪帶組權重
    rw = next(x["t"] for x in tabs if "輪帶組與權重" in x["h3"])
    weights = [float(num(r[1])) for r in rw["rows"]]
    sets = [g["strips_raw"][k] for k in sorted(g["strips_raw"], key=lambda n: int(n.split("組")[-1]))]
    if len(sets) != len(weights):
        sys.exit(f"輪帶附錄 {len(sets)} 組 ≠ 輪帶組權重 {len(weights)} 列")
    reelsets = [{"idx": i, "use": [i] * 5, "w": w, "src": "§4 輪帶組與權重（K-022）"} for i, w in enumerate(weights)]
    kv = _huff_kv(tabs)
    bet = int(_j(kv, "押注基準"))
    symbols = list(paytable) + ["WILD"] + [s for _, s in MATS]
    rate = {m: float(_j(kv, f"P-03 單顆觸發率 {m}")) for m, _ in MATS}
    values = {m: _j(kv, f"P-06／P-10 房子金額表 {m}") for m, _ in MATS}
    fg = {
        "model": MODEL,
        "trigger": {"model": "huff", "materials": [{"code": m, "sym": s} for m, s in MATS], "open_house_min": int(_j(kv, "Open House 觸發顆數")),
                    "order": _j(kv, "單顆建材觸發判定順序"), "rate": rate,
                    "src": "§4 huff 參數表 P-03（合計 ≥6 → Open House；否則依序每顆各擲觸發率，先中先得）"},
        "groups": GROUPS,
        "house_spin": {"spins": int(_j(kv, "House Spin 重轉次數")), "start": _j(kv, "P-04 House Spin 起始框數"),
                       "hat_groups": _j(kv, "P-05 安全帽率組別"), "cap": _j(kv, "D-21 K-019 漸進封頂"), "max_frames": int(_j(kv, "框數實體上限"))},
        "values": values,
        "open_house": {"spins": int(_j(kv, "Open House 每房次數")), "keys": _j(kv, "Open House 鑰匙需求"), "key_p": _j(kv, "P-07 每房出鑰匙率"),
                       "hat_p": _j(kv, "P-08 每房出安全帽率"), "plus_one_hats": int(_j(kv, "+1 手門檻")), "replay_decay": _j(kv, "P-09 宮殿重玩遞減"),
                       "max_rounds": int(_j(kv, "宮殿重玩防呆輪數"))},
        "pools": _j(kv, "P-11 強盤面獎項池"),
        "jackpot": _j(kv, "P-12 彩金"),
        "max_win_scope": _j(kv, "Max Win 範圍"),
        "src": "prob-spec §4「特色玩法參數（huff 引擎，P-03～P-12）」",
    }
    return {
        "board": {"rows": 3, "reels": 5, "slot_type": "WAYS", "bet": bet, "wild": "WILD", "wild_from_reel": 2,
                  "src": "§4 基本資訊（5×3）＋ huff bet_cost；WILD 起始軸規格書未列 → 取 odds wild_from_reel（G-HF-1）"},
        "symbols": symbols, "paytable": paytable, "tiers": tiers, "sym_id": sym_id,
        "strips": {"sets": sets, "fake": sets[0]},
        "reelsets": reelsets,
        "mg": {"src": "MG 停輪 + 243 Ways（WILD 第 2 軸起替代；建材不連線）"},
        "fg": fg,
        "gaps": GAPS,
    }


def _report(doc: dict) -> pathlib.Path | None:
    """快測報表：規格書同目錄（golden）→ <slug>/quicktest/qt-report/（data 佈局）。不依賴 CWD。"""
    md = pathlib.Path(doc.get("md_path") or ".")
    for p in (md.parent / "rtp-report.json", md.parent.parent / REPORT_REL):
        if p.exists():
            return p
    return None


def targets_extra(doc: dict) -> dict:
    """§2 各玩法：頻率 / 均倍 / RTP / 平均手數（rtp-report.json，2,000 萬局）。"""
    rp = _report(doc)
    if rp is None:
        return {}
    gm = json.loads(rp.read_text(encoding="utf-8")).get("games", {})
    out = {"feature": {}, "src": f"{REPORT_REL}（Go 快測 2,000 萬局）"}
    for g, k in REPORT_KEY.items():
        x = gm.get(k, {})
        out["feature"][g] = {"freq": x.get("freq"), "multi": x.get("multi"), "rtp": round(100 * x["rtp"], 4) if x.get("rtp") is not None else None,
                             "spins": x.get("playtimes"), "max": x.get("maxmulti")}
    return out


def go_rules(cfg: dict, go: dict) -> list[dict]:
    """規格書（game-config）⇄ Go odds.json 逐鍵對照。"""
    e, h, fg, R = go["extra_odds"], go["huff"], cfg["fg"], []
    cc = {int(k): v for k, v in h["client_codes"].items()}

    def rule(key, spec, gov):
        R.append({"key": key, "ok": None if spec is None else spec == gov, "spec": spec if len(str(spec)) < 160 else str(spec)[:157] + "…",
                  "go": gov if len(str(gov)) < 160 else str(gov)[:157] + "…"})
    for code, p in cfg["paytable"].items():
        sid = cfg["sym_id"][code]
        rule(f"odds[{sid}] {code}", [0, 0, p["3"], p["4"], p["5"]], e["odds"].get(str(sid)))
    id2code = {v: k for k, v in cfg["sym_id"].items()}
    ok = all([id2code.get(x, "?") for x in reel] == cfg["strips"]["sets"][k][i] for k, s in enumerate(go["main_game_reel_data"]) for i, reel in enumerate(s))
    rule("main_game_reel_data（附錄 Strip）", "%d 組 × 5 軸" % len(cfg["strips"]["sets"]), ("%d 組 × 5 軸" % len(go["main_game_reel_data"])) if ok else "不一致")
    rule("main_game_reel_set_weight", [r["w"] for r in cfg["reelsets"]], e["main_game_reel_set_weight"])
    rule("max_win", cfg["board"].get("max_win"), e["max_win"])
    rule("huff.bet_cost", cfg["board"]["bet"], h["bet_cost"])
    rule("huff.materials（建材 → sym_id）", [[m["code"], cfg["sym_id"][m["sym"]]] for m in fg["trigger"]["materials"]], [[m["code"], m["sym_id"]] for m in h["materials"]])
    rule("huff.pay_order", sorted(cfg["sym_id"][c] for c in cfg["paytable"]), sorted(h["pay_order"]))
    t = fg["trigger"]
    rule("huff.trigger.open_house_min", t["open_house_min"], h["trigger"]["open_house_min"])
    rule("huff.trigger.order", t["order"], h["trigger"]["order"])
    rule("huff.trigger.rate", t["rate"], h["trigger"]["rate"])
    for k in ("spins", "start", "hat_groups", "cap", "max_frames"):
        rule(f"huff.house_spin.{k}", fg["house_spin"][k], h["house_spin"][k])
    for m in fg["values"]:
        rule(f"huff.values.{m}", fg["values"][m], h["values"][m])
    for k in ("spins", "keys", "key_p", "hat_p", "plus_one_hats", "replay_decay", "max_rounds"):
        rule(f"huff.open_house.{k}", fg["open_house"][k], h["open_house"][k])
    rule("huff.pools", fg["pools"], h["pools"])
    rule("huff.jackpot", fg["jackpot"], h["jackpot"])
    rule("huff.max_win_scope", fg["max_win_scope"], h["max_win_scope"])
    rule("huff.wild_id（WILD 符號）", cfg["sym_id"].get("WILD"), h["wild_id"])
    rule("huff.wild_from_reel（規格書未列，G-HF-1）", None, h["wild_from_reel"])
    rule("client_codes 與規格書符號同序", None, [cc.get(cfg["sym_id"][c]) for c in cfg["paytable"]])
    return R


def go_fill(cfg: dict, go: dict) -> list[str]:
    """規格書缺的值以 Go 設定補（標來源）。"""
    cfg["board"]["wild_from_reel"] = go["huff"]["wild_from_reel"]
    return ["board.wild_from_reel"]


GAPS = [
    {"id": "G-HF-1", "what": "WILD 從第幾軸起替代", "spec": "§4 未列（§1 只寫 WILD 替代一般符號）", "assume": "第 2 軸起（odds huff.wild_from_reel = 2）",
     "check": "L1 主遊戲 RTP vs §2 38.88%", "auto": "mg_rtp", "go": f"{DATA}/game/go-server/internal/engine/huff/engine.go Evaluate（wf := WildFromReel − 1）"},
    {"id": "G-HF-2", "what": "Open House 起始框順序", "spec": "§3 只寫「觸發盤上的建材成為起始框」", "assume": "列優先掃描（格位 idx = 列 × 5 ＋ 軸）；順序決定金額抽值歸屬，不影響期望值",
     "check": "Go 逐局對照 0 不一致", "go": f"{DATA}/game/go-server/internal/engine/huff/engine.go triggerFrames"},
    {"id": "G-HF-3", "what": "安全帽升級目標", "spec": "§6 隱性規則：先升自己 → 已是宮殿則升其他框", "assume": "升「等級最高但未到宮殿」的框，同級取最前；都滿則空位加框（本房等級）",
     "check": "OH 均倍 vs §2 263.31 倍", "go": f"{DATA}/game/go-server/internal/engine/huff/feature.go playOH"},
    {"id": "G-HF-4", "what": "K-019 封頂判定時機", "spec": "D-21：框數達 7/9/11/13 以 10/25/50/100% 全盤停止", "assume": "每手結束後依當下框數取已達最高門檻 p 擲一次；停止後不再出安全帽",
     "check": "House Spin 均框數 / 均倍 vs §2", "go": f"{DATA}/game/go-server/internal/engine/huff/feature.go playHS（stopped）"},
    {"id": "G-HF-5", "what": "MaxWin 範圍", "spec": "D-28：total（主遊戲 ＋ 玩法合計 10,000 倍）", "assume": "封頂扣在玩法；L1 精算不含封頂",
     "check": "L2 封頂局比例", "go": f"{DATA}/game/go-server/internal/engine/huff/engine.go Play（MaxWinScope）"},
]
