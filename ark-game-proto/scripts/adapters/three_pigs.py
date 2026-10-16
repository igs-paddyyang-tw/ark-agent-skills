"""adapter：吉屋出豬 three-pigs（md 模式）— 3×5 All Ways、雙神秘圖騰主遊戲、SC/BS 雙觸發線、FG 房子三階升級收集。

FG 模型 = "house-collect"（slot-core MODELS['house-collect']）：
  進 FG 前抽強度（WEAK/NORMAL/SUPER/ULTRA）→ 每手抽 FG 輪帶組生盤 → 雙神秘替換 → Ways 線獎 →
  SC 落格把框升級（1 草→2 木→3 磚），滿級溢出依「2>1>0」優先轉移，全盤皆滿給 extra_Multi →
  結算逐格依框等級抽草屋/木屋/磚屋獎（stone_count≥15 換磚屋大獎池）。
  SC 觸發 = Free 變體（空初始框）；BS≥3 進大轉盤分流 mega_hat / buzz_saw / mansions 三變體（各給不同初始框）。

來源分工（誠實標記，見 GAPS）：
  - MG board / paytable / strips / reelsets（62 組）：§4 表 + 「## 輪帶 Strip（附錄）」+ configB.json（FG/輪帶細節規格書未展開）。
  - FG 引擎參數（free_reels 6 條、51 組合 ×16 權重欄、強度、神秘、房子三池、extra、stone15）：直接讀 configB.json。
    規格書 §4 只有「每手 SC 期望」摘要（表 F-1），無法反推完整 FG 輪帶 → 這些是 code-sourced（G-TP-ENGINE）。
  - §2 快測目標（Total/Main/Free/Bonus RTP、三變體、強度均倍、房子均棟）：§2 表 + rtp-report.json（targets_extra）。

⚠️ RNG 落差：three-pigs 快測引擎是 Python Mersenne Twister（three_pigs_12X.py），非 Go math/rand。
   proto 的 go_parity（Go 同 seed 逐局對照）對本款不適用 → 不提供 go_rules（標 G-TP-PARITY），只做 L1 精算 + L2 模擬對 §2。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from proto_common import M, num, walk_tables  # noqa: E402,F401

MODEL = "house-collect"
ENGINE = "data/slot/three-pigs/quicktest/engine"
CONFIG_B = pathlib.Path(ENGINE) / "configB.json"

# configB icon id → proto 符號碼（與 strip 附錄一致）
ID2SYM = {1: "H1", 2: "H2", 3: "H3", 4: "M1", 5: "M2", 6: "L1", 7: "L2", 8: "L3", 9: "L4", 10: "L5", 11: "L6",
          12: "WILD", 13: "SC", 14: "BS", 15: "MY1", 16: "MY2"}
VARIANTS = ["Free", "mansions", "mega_hat", "buzz_saw"]           # type 0 = Free（SC 觸發）；1..3 = 大轉盤三變體


def _load_config_b() -> dict:
    if not CONFIG_B.exists():
        sys.exit(f"找不到快測引擎參數 {CONFIG_B}（FG 引擎細節需從 configB.json 讀）")
    return json.loads(CONFIG_B.read_text(encoding="utf-8"))


def _ids2syms(seq) -> list[str]:
    return [ID2SYM.get(int(v), f"?{v}") for v in seq]


def _mg_strips(doc: dict) -> list[list[list[str]]]:
    """從 prob-spec「## 輪帶 Strip（附錄）」讀 12 條主遊戲帶（組 0..11），回 sets[strip][reel] = [sym...]。"""
    fences = {}
    for f in M.strip_fences(doc):
        m = re.search(r"組\s*(\d+)", f["name"] or "")
        if m and "主遊戲" in (f["name"] or ""):
            fences[int(m.group(1))] = f["reels"]
    if not fences:
        sys.exit("prob-spec.md 缺「## 輪帶 Strip（附錄）」主遊戲帶：請先補 strip 重產（見 docs 可行性報告 G-TP-1）")
    return [fences[i] for i in sorted(fences)]


def _reelsets_from_config(cfg_b: dict) -> list[dict]:
    """configB main_reels_weight（key = 組合字串 ' [ a,b,c,d,e ]'）→ reelsets[{idx, use, w}]。use = 1-based? 否：直接是 strip 索引（0-based）。"""
    out = []
    for i, (k, w) in enumerate(cfg_b["main_reels_weight"].items()):
        combo = [int(x) for x in re.findall(r"\d+", k)]
        out.append({"idx": i, "use": combo, "w": int(w), "src": "configB.main_reels_weight"})
    return out


def build(doc: dict, g: dict) -> dict:
    """§4 + strip 附錄 + configB.json → board / paytable / strips / reelsets / mg / fg(house-collect) + gaps。"""
    cfg_b = _load_config_b()
    pay_b = cfg_b["payTable"]
    icon = cfg_b["icon"]
    # paytable：用 configB payTable（符號碼與 strip 一致）；odds[3],[4],[5]
    paytable, tiers, symbols = {}, {}, []
    for code, arr in pay_b.items():
        paytable[code] = {"3": arr[3], "4": arr[4], "5": arr[5]}
        tiers[code] = "high" if code[0] == "H" else "low"
        symbols.append(code)
    symbols += ["WILD", "SC", "BS", "MY1", "MY2"]

    sets = _mg_strips(doc)
    reelsets = _reelsets_from_config(cfg_b)
    bet = int(cfg_b.get("totalBet") or 50)

    # ── FG 引擎參數（code-sourced from configB） ──
    free_reels = cfg_b["free_reels"]
    # free_reels key "0".."5"（跳過 "sever"）；每個是 {"1".."5":[ids]}
    fg_strips = {}
    for k in free_reels:
        if not k.isdigit():
            continue
        fr = free_reels[k]
        fg_strips[k] = [_ids2syms(fr[str(a)]) for a in range(1, 6)]
    fri = cfg_b["free_reels_Index"]
    reel_combos = fri["Result"]                                    # 51 組 5 軸索引（1-based 對 free_reels key）
    reel_weights = {kk: fri[kk] for kk in fri if kk != "Result"}   # "{變體}_{強度}" → 51 權重
    strength = {v: cfg_b["free_reels_strength"][v] for v in VARIANTS}
    fms = cfg_b["Free_Mystery_Symbol"]
    mystery = {"result": fms["Result"], "mystery1": fms["mystery1"], "mystery2": fms["mystery2"]}
    houses = {k: cfg_b["frame_scoreMult"][k] for k in cfg_b["frame_scoreMult"]}
    houses["selector"] = cfg_b["frame_scoreMult"]["stone_4plus_selector"]
    houses.pop("stone_4plus_selector", None)
    jackpot = cfg_b.get("jackpot", {})

    # 大轉盤分流：configB bonusWheeList + bonusWheeIDList → 三 FG 變體權重（JP 格權重 0 已拔）
    wheel_list = cfg_b["bonusWheeList"]
    wheel_id = cfg_b["bonusWheeIDList"]
    var_w = {"mega_hat": 0, "buzz_saw": 0, "mansions": 0}
    for i, name in enumerate(wheel_list, 1):
        w = int(wheel_id.get(str(i), 0))
        if name in var_w:
            var_w[name] += w
    wheel = [{"variant": v, "w": var_w[v]} for v in ("mega_hat", "buzz_saw", "mansions") if var_w[v] > 0]

    cfg = {
        "board": {"rows": 3, "reels": 5, "slot_type": "WAYS", "bet": bet, "wild": "WILD",
                  "src": "§1 基本規格（3×5 All Ways）；押注 = 快測 TotalBet 50（configB，§9-1 收費 50/75 以 50 計 G-TP-5）"},
        "symbols": symbols, "paytable": paytable, "tiers": tiers,
        "strips": {"sets": sets, "fake": sets[0]},
        "reelsets": reelsets,
        "mg": {"src": "MG 停輪 + All Ways + 雙神秘圖騰替換（MY1→歸零→MY2，全盤替換；大圖騰組合的主力贏分來自此替換，表 M-1）",
               "mystery": {"result": cfg_b["Mystery_Symbol"]["Result"],
                           "mystery1": cfg_b["Mystery_Symbol"]["mystery1"], "mystery2": cfg_b["Mystery_Symbol"]["mystery2"]}},
        "fg": {
            "model": MODEL,
            "trigger": {"model": "house", "sc": "SC", "bs": "BS", "gate_sc": 6, "gate_bs": 3,
                        "wheel": wheel, "src": "§4 觸發與上限（SC≥6 進 FG、BS≥3 進大轉盤）；大轉盤分流 = configB bonusWheeList/IDList（表 F-3）"},
            "groups": VARIANTS,
            "init_spins": 6,
            "fg_strips": fg_strips,
            "reel_combos": reel_combos,
            "reel_weights": reel_weights,
            "strength": strength,
            "mystery": mystery,
            "houses": houses,
            "jackpot": jackpot,
            "extra_multi": int(cfg_b.get("extra_Multi", 10)),
            "stone15_threshold": 15,
            "src": "FG 引擎參數 = configB.json（free_reels / free_reels_Index 51 組 ×16 權重欄 / 強度 F-0 / 神秘 F-2 / frame_scoreMult 房子三池 / extra_Multi）；規格書 §4 只有摘要（G-TP-ENGINE）",
        },
        "gaps": GAPS,
    }
    return cfg


def targets_extra(doc: dict) -> dict:
    """§2 大轉盤三變體 + 強度均倍 + 房子均棟（優先讀 rtp-report.json，退回 §2 表）。"""
    out = {}
    rp = pathlib.Path("data/slot/three-pigs/quicktest/qt-report/rtp-report.json")
    if rp.exists():
        r = json.loads(rp.read_text(encoding="utf-8"))
        gm = r.get("games", {})
        out["bonus"] = {
            "mega_hat": {"rtp": _pc(gm.get("Bonus_MegaHat", {}).get("rtp")), "multi": gm.get("Bonus_MegaHat", {}).get("multi"), "freq": gm.get("Bonus_MegaHat", {}).get("freq")},
            "buzz_saw": {"rtp": _pc(gm.get("Bonus_BuzzSaw", {}).get("rtp")), "multi": gm.get("Bonus_BuzzSaw", {}).get("multi"), "freq": gm.get("Bonus_BuzzSaw", {}).get("freq")},
            "mansions": {"rtp": _pc(gm.get("Bonus_Mansions", {}).get("rtp")), "multi": gm.get("Bonus_Mansions", {}).get("multi"), "freq": gm.get("Bonus_Mansions", {}).get("freq")},
            "Free": {"rtp": _pc(gm.get("Free", {}).get("rtp")), "multi": gm.get("Free", {}).get("multi"), "freq": gm.get("Free", {}).get("freq")},
            "BonusTotal": {"rtp": _pc(gm.get("BonusTotal", {}).get("rtp")), "multi": gm.get("BonusTotal", {}).get("multi"), "freq": gm.get("BonusTotal", {}).get("freq")},
        }
        out["strength_avg_multi"] = r.get("feature_strength_avg_multi", {})
        out["house_avg"] = r.get("feature_house_avg", {})
        out["rtp_breakdown"] = {"total": _pc(r.get("rtp_total")), "main": _pc(r.get("rtp_main")), "free": _pc(r.get("rtp_free")), "bonus": _pc(r.get("rtp_bonus"))}
        out["src"] = "rtp-report.json（Python 快測 1,000 萬局）"
    return out


def _pc(x):
    return round(x * 100, 4) if isinstance(x, (int, float)) else None


GAPS = [
    {"id": "G-TP-ENGINE", "what": "FG 引擎輪帶 / 組合 / 權重 / 房子表細節", "spec": "§4 只有摘要（表 F-1 每手 SC 期望、表 F-4 房子期望）", "assume": "直接讀 configB.json（free_reels 6 條、51 組合 ×16 權重欄、frame_scoreMult 三池、強度 / 神秘）",
     "check": "L1 精算 FG RTP vs §2 18.95% / 大轉盤 37.76%", "go": f"{ENGINE}/three_pigs_12X.py FreeGame；{ENGINE}/configB.json"},
    {"id": "G-TP-PARITY", "what": "逐局 Go 對照層", "spec": "proto go_parity 為 Go math/rand 設計", "assume": "放棄逐局對照（本款快測是 Python Mersenne Twister，非 Go）",
     "check": "改用 L1 精算 + L2 模擬對 §2；逐局標 known gap", "go": f"{ENGINE}/three_pigs_12X.py:L18 random（M-001）"},
    {"id": "G-TP-1", "what": "prob-spec 無 strip 附錄", "spec": "原 md 缺 ```strip", "assume": "從 configB main_reels（12 條）補附錄 → 符號碼 1=H1…16=MY2",
     "check": "strip 顆數對得上 reelsets 組合", "go": f"{ENGINE}/configB.json main_reels"},
    {"id": "G-TP-2", "what": "溢出轉移優先序", "spec": "§6 隱性規則只說「隨機」", "assume": "照程式 2>1>0 優先、同級 random.choice（豪宅直設 3）",
     "check": "FG 房子平均棟數（草 / 木 / 磚）vs §2 total 5.531/2.856/2.904", "go": f"{ENGINE}/three_pigs_12X.py:L483-521（M-NEW-03）"},
    {"id": "G-TP-3", "what": "全盤磚屋換池門檻", "spec": "GAME_FLOW 寫 ≥4（過時）", "assume": "stone_count≥15（程式常數）",
     "check": "stone15 eligible 次數 vs §2 702/1,000 萬", "go": f"{ENGINE}/three_pigs_12X.py:L523（M-NEW-04）"},
    {"id": "G-TP-4", "what": "大帽子初始盤抽法", "spec": "§3 未寫抽法", "assume": "從 FG 帶 0 取 randint(0,(len-3)//3)*3，5 軸同起點，SC 標 1",
     "check": "大帽子均倍 vs §2 101.03", "go": f"{ENGINE}/three_pigs_12X.py:L218-241（M-NEW-02）"},
    {"id": "G-TP-5", "what": "收費 50/75 不一致", "spec": "§1 基本收費 75 / 快測 TotalBet 50", "assume": "用 bet=50（與快測一致）",
     "check": "總 RTP vs §2 99.98%", "go": f"{ENGINE}/configB.json totalBet=50（§9-1）"},
    {"id": "G-TP-6", "what": "M-1 BONUS 組權重 547/548", "spec": "機率表 548 / configB 547", "assume": "用 configB 547（與快測一致）",
     "check": "Total RTP 約 −0.07pp", "go": f"{ENGINE}/configB.json main_reels_weight（prob.md §9-2）"},
]
