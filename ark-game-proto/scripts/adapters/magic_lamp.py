"""adapter：神燈寶藏（magic-lamp）— 3×5、243 Ways；SC ≥ 6 觸發 FG：SC 落點掛框 → 同格再出 SC 升級（銅→銀→金，金框再中給額外獎）→ 結算依框等級開木／銀／金箱。

FG 模型 = "frame-chest"（slot-core MODELS['frame-chest']）。抽值順序對齊 Go 快測 v6 架構大變（data/slot/magic-lamp/quicktest/engine/game/game_process.go），
數學流用整數權重（Intn）→ goparity/frame-chest_trace.go 可同 seed 逐局對照。

來源分工：
  - 盤面 / 押注 / FG 局數 / 觸發門檻 / 金框額外獎：§1 xlsx「規格簡述」原文（SPEC 行）。
  - 賠率：§1 Pay table（符號碼改用輪帶附錄的代碼 AA/KK/QQ/JJ）。
  - 表 M-1（輪帶組，R1～R5 = main_strip/Reels_k）；權重取 §4 參數備註「表 M-1 線上權重」（R-8 裁定，以線上為準；沒有這張表才退回 M-1 權重欄）。
  - 表 F-1～F-8、J-1：§4 參數表（xlsx 原樣表格，欄位依實際排版讀）。
  - §2 驗證目標：xlsx 數據貼貼分頁為空 → targets_extra 讀 quicktest/qt-report/rtp-report.json 與同一次的 ChanceReport（以 spins + total_win 對上）。
  - 規格書沒寫的（retrigger、MG 全盤事件空抽）→ go_fill 由 Go 設定檔補並標來源（G-ML-2、G-ML-5）。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from proto_common import M, by_tid, num, walk_tables  # noqa: E402,F401

MODEL = "frame-chest"
DATA = "data/slot/magic-lamp"
ENGINE = f"{DATA}/quicktest/engine/game/game_process.go"
REPORT_REL = "quicktest/qt-report/rtp-report.json"
GROUPS = ["ULTRA", "SUPER", "NORMAL", "WEAK"]                 # 表 F-2／F-3 欄序 = Go free_game_type 0..3
GROUP_ZH = {"ULTRA": "超強組", "SUPER": "強組", "NORMAL": "中組", "WEAK": "弱組"}
SYM_MAP = {"A": "AA", "K": "KK", "Q": "QQ", "J": "JJ"}        # Pay table 符號 → 輪帶附錄代碼
GO_SYM = {"M1": 11, "M2": 12, "M3": 13, "M4": 14, "M5": 15, "AA": 21, "KK": 22, "QQ": 23, "JJ": 24, "WW": 1, "SC": 2}


def _n(s):
    v = num(s) if s not in (None, "") else None
    return v


def _ints(row, a, b):
    out = []
    for c in row[a:b]:
        v = _n(c)
        if v is None:
            raise ValueError(f"非數字欄：{row}")
        out.append(int(v))
    return out


def _one(tabs, tid, k=0):
    xs = by_tid(tabs, tid)
    if len(xs) <= k:
        sys.exit(f"prob-spec.md §4 缺表 {tid}")
    return xs[k]["t"]


def _spec_text(doc) -> str:
    return pathlib.Path(doc["md_path"]).read_text(encoding="utf-8")


def _re(text, pat, what):
    m = re.search(pat, text)
    if not m:
        sys.exit(f"prob-spec.md §1 規格簡述找不到「{what}」（{pat}）")
    return int(m.group(1))


def _live_weights(text: str):
    """§4 參數備註（human 區）的「表 M-1 線上權重」表 → [w...]（R-8）。"""
    i = text.find("**表 M-1 線上權重")
    if i < 0:
        return None
    out = []
    for ln in text[i:].splitlines()[1:]:
        m = re.match(r"\|\s*(\d+)\s*\|\s*([\d,]+)\s*\|", ln)
        if m:
            if int(m.group(1)) != len(out):
                sys.exit("表 M-1 線上權重 Index 不連續")
            out.append(int(m.group(2).replace(",", "")))
        elif out and not ln.startswith("|"):
            break
    return out


def build(doc: dict, g: dict) -> dict:
    tabs = walk_tables(doc, "params")
    text = _spec_text(doc)
    bet = _re(text, r"Bet cost\s*(\d+)", "Bet cost")
    gate = _re(text, r"出現\s*(\d+)\s*個或以上的 Scatter", "觸發顆數")
    spins = _re(text, r"Free Game 獲得免費旋轉：\s*(\d+)", "FG 局數")
    over = _re(text, r"獲得\s*(\d+)x 額外獎金", "金框額外獎")
    # 賠率（符號碼換成輪帶代碼）
    paytable = {SYM_MAP.get(k, k): v for k, v in g["paytable"].items()}
    tiers = {SYM_MAP.get(k, k): v for k, v in g["tiers"].items()}
    # 表 M-1：輪帶組（R1～R5 = main_strip/Reels_k）
    m1 = _one(tabs, "M-1")
    live = _live_weights(text)
    rows = [r for r in m1["rows"] if _n(r[0]) is not None]
    if live is not None and len(live) != len(rows):
        sys.exit(f"表 M-1 線上權重 {len(live)} 項 ≠ M-1 {len(rows)} 列")
    reelsets = []
    for i, r in enumerate(rows):
        H = m1["head"]
        use = [int(_n(r[H.index(f"R{k}")])) for k in range(1, 6)]
        w_x = int(_n(r[H.index("權重")]))
        reelsets.append({"idx": int(_n(r[0])), "use": use, "w": live[i] if live else w_x, "w_xlsx": w_x,
                         "desc": r[H.index("組合說明")] if "組合說明" in H else "",
                         "src": ("§4 參數備註「表 M-1 線上權重」（R-8）" if live else "表 M-1 權重") + f"；組合 {r[-1]}"})
    main_sets = [g["strips_raw"][f"main_strip / Reels_{k}"] for k in range(5)]
    fstrips = {str(k): g["strips_raw"][f"free_strip / Reels_{k}"] for k in range(1, 6)}
    # 表 F-1：保底手（第幾手，1-based → Go index 0-based）
    f1 = _one(tabs, "F-1")
    bonus = [int(_n(r[1])) for r in f1["rows"] if _n(r[0]) is not None]
    # 表 F-2：進場 SC 數 → 強度組權重（xlsx 排版：第 2 欄起 = 顆數、ULTRA、SUPER、NORMAL、WEAK、Σ）
    f2 = _one(tabs, "F-2")
    type_by_sc = []
    for r in f2["rows"]:
        v = _ints(r, 1, 7)
        if sum(v[1:5]) != v[5]:
            sys.exit(f"表 F-2 權重和不符：{r}")
        type_by_sc.append({"sc": v[0], "w": v[1:5]})
    # 表 F-3：FG 輪帶組（xlsx 排版：說明、Index、R1～R5、ULTRA、SUPER、NORMAL、WEAK）
    f3 = _one(tabs, "F-3")
    fg_rs = []
    for r in f3["rows"]:
        v = _ints(r, 1, 11)
        fg_rs.append({"idx": v[0], "use": v[1:6], "w": dict(zip(GROUPS, v[6:10])), "desc": r[0], "src": f"表 F-3 {r[-1]}"})
    # 表 F-4：保底手替換模式
    f4 = _one(tabs, "F-4")
    pats = [{"mask": _ints(r, 1, 6), "w": int(_n(r[6]))} for r in f4["rows"] if _n(r[0]) is not None]
    # 表 F-5～F-7：木／銀／金箱
    f5 = _one(tabs, "F-5")
    wood = [{"v": int(_n(r[1])), "w": int(_n(r[2]))} for r in f5["rows"] if _n(r[0]) is not None]

    def chest(t):
        return [{"v": int(_n(r[2])), "w": int(_n(r[3])), "label": r[0].strip()} for r in t["rows"] if _n(r[1]) is not None and _n(r[2]) is not None]
    silver, gold = chest(_one(tabs, "F-6")), chest(_one(tabs, "F-7"))
    # 表 F-8：金箱 ≥ 4 特殊事件（組別權重 + 三組分布；第 0 組 = 維持原金箱分數）
    f8a, f8b = _one(tabs, "F-8", 0), _one(tabs, "F-8", 1)
    ev_w = next(_ints(r, 3, 6) for r in f8a["rows"] if r[2].strip().lower() == "weight")
    H = f8b["head"]
    drows = [r for r in f8b["rows"] if _n(r[1]) is not None]
    dists = [None] + [[{"v": int(_n(r[1])), "w": int(_n(r[H.index(col)]) or 0), "label": r[0].strip()} for r in drows] for col in ("Super", "Ultra")]
    gmin = _re(text, r"(\d+)顆以上\(包含\d+顆\)金箱", "特殊事件金箱門檻") if "顆以上(包含" in text else 4
    jp = {k: int(_n(v)) for k, v in zip(_one(tabs, "J-1")["head"], _one(tabs, "J-1")["rows"][0]) if k != "來源"}
    fg = {
        "model": MODEL,
        "trigger": {"model": "count", "symbols": ["SC"], "min": gate, "src": "§1 規格簡述：出現 ≥ 6 個 Scatter 觸發免費遊戲"},
        "groups": GROUPS, "group_zh": GROUP_ZH,
        "spins": spins, "spins_src": "§1 規格簡述：Free Game 獲得免費旋轉 6 次",
        "retrigger": {"gate": None, "add": None, "src": "規格書未列（G-ML-2）→ go_fill"},
        "over_level": over, "over_src": "§1 規格簡述：最高級框再出 Scatter 給 750x 額外獎金（× Line bet）",
        "type_by_sc": type_by_sc, "type_src": "表 F-2",
        "bonus_round": bonus, "bonus_src": "表 F-1（第 1～6 手；Go index 0～5）",
        "reelsets": fg_rs, "strips": fstrips,
        "guarantee": {"strip": 5, "patterns": pats, "src": "表 F-4（1 = 換成 free_strip / Reels_5 對應軸）"},
        "chests": {"wood": wood, "silver": silver, "gold": gold, "src": "表 F-5 木箱／F-6 銀箱／F-7 金箱（multi × Line bet）"},
        "gold_event": {"min": gmin, "w": ev_w, "dists": dists, "src": "表 F-8（組別 Normal／Super／Ultra；Normal = 維持原金箱分數）"},
        "jackpot": jp, "jp_src": "表 J-1（金／銀箱中的 JP 獎項，固定分數）",
        "src": "prob-spec §1 規格簡述 + §4 表 F-1～F-8、J-1",
    }
    return {
        "board": {"rows": 3, "reels": 5, "slot_type": "WAYS", "bet": bet, "line_bet": 1, "wild": "WW", "wild_from_reel": 1,
                  "src": "§1 規格簡述：3 x 5、243 ways、Bet cost 75；贏分 = 賠率 × ways（Line bet 1）"},
        "symbols": list(paytable) + ["WW", "SC"], "paytable": paytable, "tiers": tiers,
        "strips": {"sets": main_sets, "fake": g["strips_raw"]["main_strip / 假轉"]},
        "reelsets": reelsets,
        "mg": {"all_board": None, "src": "MG：表 M-1 抽輪帶組 → 停輪 → 243 Ways（WW 替代、SC 不連線）"},
        "fg": fg,
        "gaps": GAPS,
    }


def _report(doc: dict) -> pathlib.Path | None:
    md = pathlib.Path(doc.get("md_path") or ".")
    for p in (md.parent / "rtp-report.json", md.parent.parent / REPORT_REL):
        if p.exists():
            return p
    return None


def _chance(rp: pathlib.Path, rep: dict) -> pathlib.Path | None:
    """同一次快測的 ChanceReport：Times / TotalWin 與 rtp-report 一致者。"""
    key = f"Times:{rep['spins']} TotalWin:{rep['total_win']}"
    for p in sorted(rp.parent.glob("*ChanceReport*.txt")):
        if key in p.read_text(encoding="utf-8", errors="replace")[:2000]:
            return p
    return None


def targets_extra(doc: dict) -> dict:
    rp = _report(doc)
    if rp is None:
        return {}
    rep = json.loads(rp.read_text(encoding="utf-8"))
    gm = rep.get("games", {})
    mg, fgx, tot = gm.get("MainGame", {}), gm.get("FreeGame(FG+JP)", {}), gm.get("Total", {})
    summ = {"rtp_total": round(100 * tot["rtp"], 4), "rtp_main": round(100 * mg["rtp"], 4), "rtp_free": round(100 * fgx["rtp"], 4),
            "fg_rate": round(100 / fgx["freq"], 5) if fgx.get("freq") else None, "fg_freq": fgx.get("freq"), "fg_avg": fgx.get("multi"),
            "mg_hit": round(100 * mg["hitrate"], 2) if mg.get("hitrate") else None, "spins": rep["spins"], "tol": 0.3}
    out = {"summary": summ, "src": f"{REPORT_REL}（Go 快測 {rep['spins']:,} 手；xlsx §2 為空）"}
    cp = _chance(rp, rep)
    if cp is None:
        return out
    t = cp.read_text(encoding="utf-8", errors="replace")
    fc = {"src": f"quicktest/qt-report/{cp.name}"}
    fc["spins"] = float(re.search(r"Free Game 平均手數:\s*([\d.]+)", t).group(1))
    fc["retrig"] = float(re.search(r"Retrigger機率:\s*([\d.]+)%", t).group(1))
    fc["groups"] = {}
    for g, zh in GROUP_ZH.items():
        m = re.search(r"^" + zh + r": 平均 Multi = ([\d.]+) \(次數: (\d+), 進入機率: ([\d.]+)%\)", t, re.M)
        if m:
            fc["groups"][g] = {"avg_win": float(m.group(1)), "n": int(m.group(2)), "share": float(m.group(3))}
    fc["entry"] = {int(m.group(1)): {"rate": float(m.group(2)), "avg_win": float(m.group(3))}
                   for m in re.finditer(r"^\s*(\d+) 顆進\s*\|\s*([\d.]+)%\s*\|\s*[\d.]+\s*\|\s*([\d.]+)", t, re.M)}
    gd = {int(m.group(1)): float(m.group(2)) for m in re.finditer(r"最終出現\s*(\d+)顆金寶箱的機率:([\d.]+)%", t)}
    fc["gold4"] = round(sum(v for k, v in gd.items() if k >= 4), 4)
    ev = re.findall(r"(原本金箱分數|特殊金箱分數1|特殊金箱分數2): 觸發次數 \d+ \(([\d.]+)%\), 平均倍數 ([\d.]+)", t)
    fc["events"] = [{"share": float(s), "avg": float(a)} for _, s, a in ev]
    fc["lv"] = [float(re.search(rf"FG level {k} 平均出現顆數: ([\d.]+)", t).group(1)) for k in range(4)]
    sh = {}
    for zh, k in (("木箱得分", "wood"), ("銀箱得分", "silver"), ("金箱得分", "gold"), ("線獎得分", "line"), ("金箱重複打到的得分", "over")):
        m = re.search(zh + r": \d+ \(([\d.]+)%\)", t)
        if m:
            sh[k] = float(m.group(1))
    fc["share"] = sh
    out["frame_chest"] = fc
    return out


def go_rules(cfg: dict, go: dict) -> list[dict]:
    """規格書（game-config）⇄ Go 設定檔（ProbSetting JSON，cmd/dump 或 quicktest/config/live-b.json）逐鍵對照。"""
    fg, R = cfg["fg"], []

    def rule(key, spec, gov):
        R.append({"key": key, "ok": None if spec is None else spec == gov, "spec": spec if len(str(spec)) < 160 else str(spec)[:157] + "…",
                  "go": gov if len(str(gov)) < 160 else str(gov)[:157] + "…"})
    for code, p in cfg["paytable"].items():
        rule(f"Odds[{GO_SYM[code]}] {code}", [0, 0, p["3"], p["4"], p["5"]], go["Odds"].get(str(GO_SYM[code])))
    rule("Bet_Cost", cfg["board"]["bet"], go["Bet_Cost"])
    rule("Line_bet", cfg["board"]["line_bet"], go["Line_bet"])
    ids = lambda reels: [[GO_SYM.get(s, -9) for s in r] for r in reels]  # noqa: E731
    rule("MainGameReelData（附錄 main_strip Reels_0～4）", [ids(s) for s in cfg["strips"]["sets"]] == go["MainGameReelData"] and "5 組 × 5 軸 逐格一致" or "不一致",
         "5 組 × 5 軸 逐格一致")
    rule("MainGameReelIndexSet（表 M-1 R1～R5）", [r["use"] for r in cfg["reelsets"]], go["MainGameReelIndexSet"])
    rule("MainGameReelSetWeight（R-8 線上權重）", [r["w"] for r in cfg["reelsets"]], go["MainGameReelSetWeight"])
    rule("EnterFreeGameGate", fg["trigger"]["min"], go["EnterFreeGameGate"])
    rule("FreeGameNum", fg["spins"], go["FreeGameNum"])
    rule("FreeGameRetriggerGate（規格書未列，G-ML-2）", None, go["FreeGameRetriggerGate"])
    rule("FreeGameRetriggerSpinNum（規格書未列，G-ML-2）", None, go["FreeGameRetriggerSpinNum"])
    rule("FreeGameTypeWeightBySC（表 F-2）", [x["w"] for x in fg["type_by_sc"]], go["FreeGameTypeWeightBySC"])
    rule("FreeGameReelsetConfig（表 F-3 R1～R5）", [r["use"] for r in fg["reelsets"]], go["FreeGameReelsetConfig"])
    rule("FreeGameReelsetWeightByType（表 F-3）", [[r["w"][g] for r in fg["reelsets"]] for g in GROUPS], go["FreeGameReelsetWeightByType"])
    fr = go["FreeGameReelDataByReelset"]
    ok = all(ids([fg["strips"][str(u)][i] for i, u in enumerate(r["use"])]) == fr[k] for k, r in enumerate(fg["reelsets"]))
    rule("FreeGameReelDataByReelset（附錄 free_strip Reels_1～4）", "10 組逐格一致" if ok else "不一致", "10 組逐格一致")
    rule("FreeGuaranteeReelDataBySet[0]（附錄 free_strip Reels_5）", ids(fg["strips"]["5"]) == go["FreeGuaranteeReelDataBySet"][0] and "一致" or "不一致", "一致")
    rule("BonusRoundWeight（表 F-1）", fg["bonus_round"], go["BonusRoundWeight"])
    rule("BonusReelSelectionWeight（表 F-4）", [p["w"] for p in fg["guarantee"]["patterns"]], go["BonusReelSelectionWeight"])
    rule("BonusReelReplacementPatterns（表 F-4）", [p["mask"] for p in fg["guarantee"]["patterns"]], go["BonusReelReplacementPatterns"])
    for k, gk in (("wood", "Wooden"), ("silver", "Sliver"), ("gold", "Golden")):
        rule(f"{gk}ChestScore（表 F-{ {'wood': 5, 'silver': 6, 'gold': 7}[k] }）", [x["v"] for x in fg["chests"][k]], go[f"{gk}ChestScore"])
        rule(f"{gk}ChestWeight", [x["w"] for x in fg["chests"][k]], go[f"{gk}ChestWeight"])
    rule("OverThreeWinScore", fg["over_level"], go["OverThreeWinScore"])
    rule("SpecialEventWeight（表 F-8）", fg["gold_event"]["w"], go["SpecialEventWeight"])
    for i in (1, 2):
        d = fg["gold_event"]["dists"][i]
        rule(f"SpecialEventScore{i + 1}", [x["v"] for x in d], go[f"SpecialEventScore{i + 1}"])
        rule(f"SpecialEventWeight{i + 1}", [x["w"] for x in d], go[f"SpecialEventWeight{i + 1}"])
    rule("GoldenChestSmallWeight（隱性規則 JP 互斥；Go v6 引擎未使用，G-ML-3）", None, go.get("GoldenChestSmallWeight"))
    rule("MainGameAllBoardWeight（規格書無；Go 每手空抽一次，G-ML-5）", None, [go.get("MainGameAllBoardResult"), go.get("MainGameAllBoardWeight")])
    rule("IsItemCard／GuarenteeSpinEnable（道具卡／保底，本局關閉）", None, [go.get("IsItemCard"), go.get("GuarenteeSpinEnable")])
    return R


def go_fill(cfg: dict, go: dict) -> list[str]:
    """規格書缺、Go 有的值補進 config（標來源；對應 G-ML-2、G-ML-5）。"""
    fg = cfg["fg"]
    fg["retrigger"] = {"gate": go["FreeGameRetriggerGate"], "add": go["FreeGameRetriggerSpinNum"],
                       "src": "Go 設定檔 FreeGameRetriggerGate／FreeGameRetriggerSpinNum（規格書未列，G-ML-2）"}
    cfg["mg"]["all_board"] = {"result": go["MainGameAllBoardResult"], "weight": go["MainGameAllBoardWeight"],
                              "src": "Go 設定檔 MainGameAllBoardResult／Weight（規格書無此表；結果恆 0，只空抽一次對齊 RNG，G-ML-5）"}
    if go.get("IsItemCard") or go.get("GuarenteeSpinEnable"):
        sys.exit("Go 設定檔開了道具卡或保底：frame-chest 模型未實作（G-ML-6）")
    return ["fg.retrigger", "mg.all_board"]


GAPS = [
    {"id": "G-ML-1", "what": "表 M-1 輪帶組權重用哪一組", "spec": "M-1 權重欄是第 1 候選向量 {106, 21, …, 357}；同表另有 4 組候選",
     "assume": "以線上為準：第 5 候選向量 {106, 24, …, 300}（R-8 裁定；寫在 §4 參數備註「表 M-1 線上權重」）",
     "check": "L1 主遊戲 RTP、FG 觸發率 vs 快測", "auto": "mg_rtp", "go": "quicktest/config/live-b.json MainGameReelSetWeight（= 線上 server-prob.json）"},
    {"id": "G-ML-2", "what": "FG 加局（retrigger）規則", "spec": "§1 規格簡述未提；§1 人工簡述寫「每 3 顆 SC 加 1 局」（可讀成每 3 顆加 1 或 ≥ 3 顆加 1）",
     "assume": "本手 SC ≥ 3 → 加 1 局（不論幾顆、可多次加）", "check": "FG 平均手數 vs 快測 7.97、加局率 24.75%", "auto": "fc_spins",
     "go": f"{ENGINE} freeGameProcess：if total_sc_num >= FreeGameRetriggerGate {{ remain_spin_num += FreeGameRetriggerSpinNum }}"},
    {"id": "G-ML-3", "what": "JP 互斥（一個金箱開出 Grand／Major 後其他金箱改用 small 分布）", "spec": "§6 隱性規則第 4 列；設定檔有 GoldenChestSmallWeight",
     "assume": "雛型照 Go 快測 v6：每個金箱都用表 F-7 同一張權重，不做互斥", "check": "金箱 JP 次數分布；需對照線上 Server 程式是否實作互斥",
     "go": f"{ENGINE} 結算 case 3：「簡化後的金寶箱邏輯：直接使用正常金寶箱獎勵」（GoldenChestSmallWeight 未被引用）"},
    {"id": "G-ML-4", "what": "表 F-8 特殊事件怎麼重算金箱", "spec": "F-8 說明：「根據對應權重抽選要用哪個金箱獎項組合」（沒寫是每箱各抽還是抽一次）",
     "assume": "抽一次分數 × 金箱數，取代原本所有金箱總分；Normal 組 = 維持原分數", "check": "特殊事件佔比 vs 快測（Super 1.50%／Ultra 0.39%）", "auto": "fc_event",
     "go": f"{ENGINE}：specialEventWin = chestscore × Line_bet × GoldenChest_num"},
    {"id": "G-ML-5", "what": "MG 全盤事件（M0002）", "spec": "規格書無此表", "assume": "Go 每手在停輪前空抽一次（權重 [10000]、結果 0 = 不觸發）；雛型照抽，只為對齊 RNG 流，不影響數學",
     "check": "Go 逐局對照 0 不一致", "go": f"{ENGINE} mainGameProcess：GetResultByWeight(MainGameAllBoardResult, MainGameAllBoardWeight)"},
    {"id": "G-ML-6", "what": "道具卡（Buy Bonus）與保底轉", "spec": "主版規格書不含（BB 變體另表，R-5）", "assume": "不實作；Go 設定 IsItemCard 0、GuarenteeSpinEnable false",
     "check": "go_fill 遇到開啟時直接報錯", "go": f"{ENGINE} mainGameProcess（IsItemCard／guarantee_count 分支）"},
    {"id": "G-ML-7", "what": "結算開箱順序", "spec": "未寫", "assume": "格位 idx = 軸 × 3 + 列，由 0 到 14 逐格開；順序只影響抽值歸屬，不影響期望值",
     "check": "Go 逐局對照", "go": f"{ENGINE}：for _, situation := range Situation"},
]
