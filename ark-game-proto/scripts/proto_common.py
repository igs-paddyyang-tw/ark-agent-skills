"""proto_common — ark-game-proto 共用：讀 prob-spec.md（經 ark-game-prob 的 ps_mdview）、通用段、§2 驗證目標、表格小工具。

adapter 只寫「這款玩法的表格語意」，其餘都在這裡。不呼叫 LLM；同輸入同輸出。
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _find_mdview() -> pathlib.Path:
    """尋找 ark-game-prob 的 ps_mdview（環境變數 > 常見安裝位置）。"""
    import os
    cands = [os.environ.get("ARK_GAME_PROB_SCRIPTS", ""),
             HERE.parents[1] / "ark-game-prob" / "scripts",            # 同層 skill（.kiro/skills/ 或 repo 根）
             pathlib.Path.cwd() / ".kiro/skills/ark-game-prob/scripts"]
    cands += [p / ".kiro/skills/ark-game-prob/scripts" for p in HERE.parents]
    cands += [p / ".kiro/skills/ark-game-prob/scripts" for p in pathlib.Path.cwd().parents]
    for c in cands:
        if c and (pathlib.Path(c) / "ps_mdview.py").exists():
            return pathlib.Path(c)
    sys.exit("找不到 ps_mdview.py：設定 ARK_GAME_PROB_SCRIPTS 指到 ark-game-prob/scripts（需 1.4+）")


sys.path.insert(0, str(_find_mdview()))
import ps_mdview as M  # noqa: E402

TID_RE = re.compile(r"表\s*([A-Z]-[\d-]+)")


def num(s):
    """'1,288' → 1288；'99.94%' → 99.94；'*2' → None（交給呼叫端）。"""
    v = M.tonum(str(s).replace(",", ""))
    return v


def walk_tables(doc: dict, sid: str) -> list[dict]:
    """展開某段所有表格，附上所在 h3（表編號）與 bold caption。"""
    sec = M.section(doc, sid)
    out, h3, bold = [], "", ""
    for b in (sec or {}).get("blocks", []):
        if b["kind"] in ("h3", "h4"):
            h3, bold = b.get("text", ""), ""
        elif b["kind"] == "bold":
            bold = b.get("text", "")
        elif b["kind"] == "table":
            m = TID_RE.search(h3)
            out.append({"h3": h3, "tid": m.group(1) if m else None, "cap": b.get("caption") or bold, "t": b})
    return out


def by_tid(tabs, tid):
    return [x for x in tabs if x["tid"] == tid]


def by_h3(tabs, key):
    return [x for x in tabs if key in x["h3"]]


def src_of(row, head):
    """表格最後一欄「來源」。"""
    return row[head.index("來源")] if "來源" in head else ""


# ───────────────────────── 通用段 ─────────────────────────
def generic(doc: dict) -> dict:
    brief = walk_tables(doc, "brief")
    kv = {r[0]: r[1] for x in brief if x["t"]["cls"] == "kv" for r in x["t"]["rows"]}
    mb = re.search(r"(\d+)\s*[x×]\s*(\d+)", kv.get("盤面", "3x5").lower())   # 容許「3×5（3 列 5 軸）」這類附註
    rows, reels = (mb.group(1), mb.group(2)) if mb else ("3", "5")
    bet = int(num(kv.get("基本收費", "1")) or 1)
    pt = next((x["t"] for x in brief if x["t"]["cls"] == "paytable"), {"head": [], "rows": []})   # 沒有就交給 adapter
    ks = [h for h in pt["head"] if re.fullmatch(r"x\d+", h)]
    paytable, tiers = {}, {}
    for r in pt["rows"]:
        sym = r[pt["head"].index("符號")]
        paytable[sym] = {h[1:]: num(r[pt["head"].index(h)]) for h in ks}
        tiers[sym] = "high" if "High" in r[0] else "low"
    strips = {f["name"]: f["reels"] for f in M.strip_fences(doc)}
    if not strips:
        sys.exit("prob-spec.md 沒有附錄 ```strip 帶面：需 ark-game-prob 1.4+ 產出的格式，請先 ps_run 重產（人工區會保留）")
    return {"board": {"rows": int(rows), "reels": int(reels), "slot_type": "WAYS" if "Ways" in kv.get("線數", kv.get("對獎方式", "")) else "LINE",
                      "bet": bet, "src": "§1 基本規格"},
            "paytable": paytable, "tiers": tiers, "strips_raw": strips}


def targets(doc: dict) -> dict:
    """§2 數據資料 → 驗證目標（快測實測值；雛型模擬要對上這些數）。"""
    s = M.summary_of(doc)
    t = {k: v.get("num") for k, v in s.items() if isinstance(v, dict) and v.get("num") is not None}
    data = walk_tables(doc, "data")
    out = {"summary": t, "src": "§2 快測摘要"}
    for x in data:
        tb, cap = x["t"], x["cap"] or x["h3"]
        H = tb["head"]
        if tb["cls"] == "reelset_rtp":
            col = lambda r, h: num(r[H.index(h)]) if h in H else None  # noqa: E731
            out["reelsets"] = [{"idx": int(num(r[0])), "theory_total": col(r, "理論 Total RTP"), "meas_total": col(r, "實測 Total RTP"),
                                "meas_fg": col(r, "實測 FG RTP")} for r in tb["rows"]]
        elif tb["cls"] == "fg_groups":
            out["fg_groups"] = {r[0]: {"share": num(r[H.index("實際佔比")]), "rtp_share": num(r[H.index("FG RTP 貢獻")])} for r in tb["rows"]}
        elif "各組別詳細" in cap:
            out["fg_group_detail"] = {r[0]: {h: num(r[i]) for i, h in enumerate(H) if i} for r in tb["rows"]}
        elif "觸發面" in cap:
            out["trigger_specials"] = {int(num(r[0])): num(r[2]) for r in tb["rows"]}
        elif "進場 SC 顆數" in cap:
            out["entry_sc"] = {int(num(r[0])): {"share": num(r[2]), "avg_win": num(r[3])} for r in tb["rows"]}
        elif tb["cls"] == "kv" and "FG 詳細" in x["h3"] and not x["cap"]:
            kv = {r[0]: r[1] for r in tb["rows"]}
            out["fg_detail"] = {"base_avg": num(kv.get("平均初始基底（倍）")), "all888_avg_win": num(kv.get("全放 888 平均贏分（倍）")),
                                "avg_mult": num(kv.get("平均總乘倍")), "avg_coin_win": num(kv.get("平均金幣贏分")),
                                "avg_carp_win": num(kv.get("平均鯉魚贏分")),
                                "all888_rate": num(re.search(r"佔 FG ([\d.]+)%", kv.get("全放 888 事件", "")).group(1)) if "全放 888 事件" in kv else None}
        elif tb["cls"] == "symhit" and "命中率" in x["h3"]:
            out["mg_symhit_total"] = num(tb["rows"][-1][-1])
    return out


def _dual(tb) -> dict:
    """SC/SS 雙欄分數表；'*2' 視為乘倍（mul）。"""
    H, sc, ss = tb["head"], [], []
    for r in tb["rows"]:
        a, w = num(r[0]), num(r[1])
        if a is None or w is None:
            continue            # 均倍 / Σ 列
        sc.append({"v": int(a), "w": int(w)})
        b, w2 = r[2].strip(), num(r[3])
        m = re.fullmatch(r"\*\s*(\d+)", b)
        ss.append({"mul": int(m.group(1)), "w": int(w2)} if m else {"v": int(num(b)), "w": int(w2)})
    return {"sc": sc, "ss": ss, "src": src_of(tb["rows"][0], H)}


def _yesno(tb) -> dict:
    H = tb["head"]
    return {r[0]: [int(num(r[1])), int(num(r[2]))] for r in tb["rows"]} | {"src": src_of(tb["rows"][0], H)}


def _weights(tb) -> dict:
    H = tb["head"]
    return {r[0]: int(num(r[1])) for r in tb["rows"]} | {"src": src_of(tb["rows"][0], H)}


def _matrix(tb) -> dict:
    """組別 × 值（欄名為數值）→ {values:[...], 組別:[w...]}。"""
    H = tb["head"]
    cols = [i for i, h in enumerate(H) if i and num(h) is not None]
    out = {"values": [int(num(H[i])) for i in cols], "src": src_of(tb["rows"][0], H)}
    for r in tb["rows"]:
        out[r[0]] = [int(num(r[i]) or 0) for i in cols]
    return out
