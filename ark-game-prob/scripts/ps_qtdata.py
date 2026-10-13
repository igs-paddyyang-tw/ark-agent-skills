#!/usr/bin/env python3
"""ps_qtdata — qt 模式的 prob-data.json adapter。

把 qt 模式的來源（odds.json + qt-report/rtp-report.json + qt-config.yaml）轉成 ps_html.py 吃的
`prob-data.json` 結構，讓 qt 款的 View 走與 xlsx 款同一套 ps_html 引擎（色階熱度 / KPI / 輪帶組對照）。

產出結構（對齊 ps_html `__init__` 讀取的鍵）：
  game / slug
  report.base{Main|Free|Feature|Total: [RTP%, Freq, Trig%, Multi, PlayTimes, Retri%, MaxMulti]}
  report.summary{rtp_total, rtp_main, rtp_free}
  report.symbol_hit_rate / symbol_hit_rtp / reel_set_rtp / special_range / multiple / decile / run
  known.board / paytable / reelsets / weights   ← W4 補（色階熱度資料源）

用法：python ps_qtdata.py --qt data/quicktest/<slug> [--out <prob-data.json 路徑>]
不破壞 xlsx 模式：本腳本只在 qt 模式被 ps_run 呼叫。
"""
from __future__ import annotations
import argparse, json, os, pathlib, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402


def _pct(v):
    """小數 → 'xx.xx%' 字串（ps_html base 顯示用）；None → '—'。"""
    return "—" if v is None else f"{v * 100:.4f}%"


def _game_row(g: dict) -> list:
    """rtp-report games[x] dict → ps_html base 的 7 欄 list。
    欄序：GAME%(RTP) / Freq / Trig% / Multi / PlayTimes / Retri% / MaxMulti。"""
    freq = g.get("freq")
    return [
        _pct(g.get("rtp")),
        (f"{freq:.2f}" if freq else "—"),
        _pct(g.get("hitrate")) if g.get("hitrate") is not None else (_pct(1 / freq) if freq else "—"),
        (f"{g.get('multi'):.2f}" if g.get("multi") is not None else "—"),
        (f"{g.get('playtimes'):.2f}" if g.get("playtimes") is not None else "—"),
        _pct(g.get("retrirate")) if g.get("retrirate") is not None else "—",
        (f"{g.get('maxmulti'):.2f}" if g.get("maxmulti") is not None else "—"),
    ]


def build(qt_dir: pathlib.Path, slug: str | None = None) -> dict:
    cfg = C.yaml_load(qt_dir / "qt-config.yaml")
    ver = str(cfg.get("version") or "1.0.0")
    odds = json.loads((qt_dir / "odds" / f"odds_{ver}.json").read_text(encoding="utf-8"))
    rep_p = qt_dir / "qt-report" / "rtp-report.json"
    rep = json.loads(rep_p.read_text(encoding="utf-8")) if rep_p.exists() else {}
    slug = slug or qt_dir.name
    game = cfg.get("game") or slug

    data: dict = {"game": game, "slug": slug,
                  "source": {"name": f"qt-adapter（odds_{ver}.json + rtp-report.json）", "sha256_16": "qt-mode"},
                  "odds_version": ver}

    # ── report 段（W1：接通快測結果）──
    report: dict = {}
    games = rep.get("games") or {}
    name_map = {"MainGame": "Main", "SpecialGameTotal": "Free", "Total": "Total"}
    base = {}
    for src_name, dst_name in name_map.items():
        if src_name in games:
            base[dst_name] = _game_row(games[src_name])
    if base:
        report["base"] = base
    report["summary"] = {
        "rtp_total": rep.get("rtp_total"),
        "rtp_main": rep.get("rtp_main"),
        "rtp_free": rep.get("rtp_special"),  # 本引擎 special = 範本的 free 位
    }
    # 直接轉接的統計（ps_html 認得的結構）
    # symbol_hit_rate/rtp：rtp-report 是 {sym:{x2,x3,x4,x5,total}} dict；ps_html symtab 期望 {sym:[list]}
    for k in ("symbol_hit_rate", "symbol_hit_rtp"):
        src = rep.get(k)
        if isinstance(src, dict) and src:
            conv = {}
            for sym, cols in src.items():
                if isinstance(cols, dict):
                    conv[sym] = [cols.get("x2", 0) or 0, cols.get("x3", 0) or 0,
                                 cols.get("x4", 0) or 0, cols.get("x5", 0) or 0, cols.get("total", 0) or 0]
                elif isinstance(cols, list):
                    conv[sym] = cols
            if conv:
                report[k] = conv
    # 註：special_range / multiple / decile 的 rtp 在 rtp-report 是 dict（{total,main,free}），
    # 與 ps_html 期望的 list 結構不同；qt 模式暫不轉接（非核心視覺，避免結構地雷），
    # ps_html 的 data() 對缺這些 key 會自然跳過（if R.get(k) 保護）。
    # reel_set_rtp：ps_html 期望 [{set, total}]；rtp-report 是 {set: rtp}
    rsr = rep.get("reel_set_rtp") or {}
    rows = [{"set": int(k), "total": (v * 100 if v is not None and v < 5 else v)} for k, v in rsr.items() if v is not None]
    if rows:
        report["reel_set_rtp"] = rows
    # run 資訊
    report["run"] = {"version": rep.get("version"), "timestamp": rep.get("generated_at"),
                     "total": rep.get("spins"), "total_bet": rep.get("total_bet"), "total_win": rep.get("total_win")}
    data["report"] = report

    # ── known 段（色階熱度/Pay table 資料源）──
    st = cfg.get("structure") or {}
    known: dict = {}
    if st.get("reels") and st.get("rows"):
        known["board"] = {"盤面": f"{st['reels']}x{st['rows']}",
                          "對獎方式": st.get("pay_mode", ""),
                          "基本收費": st.get("bet_cost", "")}
    # Pay table：從 odds.json 的線賠符號組（ps_html brief 的 paytable：[{tier,sym,odds:{x3,x4,x5}}]）
    syms = st.get("symbols") or []
    oddsmap = (odds.get("extra_odds") or {}).get("odds") or {}
    pt = []
    for s in syms:
        sid = str(s.get("sym_id"))
        arr = oddsmap.get(sid)
        if s.get("group") == "normal" and isinstance(arr, list) and len(arr) >= 5:
            # arr 升序 [x1..x5]；取 x3/x4/x5（線賠從 3 連起）
            tier = "High Pay Symbols" if int(sid) < 20 else "Low Pay Symbols"
            pt.append({"tier": tier, "sym": s.get("code"),
                       "odds": {"3": arr[2], "4": arr[3], "5": arr[4]}})
    if pt:
        known["paytable"] = pt
    # golden：quicktest.yaml 選填 golden_rtp（競品反解無原廠理論值則不給 → ps_html graceful 顯「無理論值對照」）
    golden = (C.yaml_load(qt_dir / "quicktest.yaml") or {}).get("golden_rtp") if (qt_dir / "quicktest.yaml").exists() else None
    if golden is not None:
        known["reelsets"] = {"totals": {"TOTAL RTP": golden}}
    if known:
        data["known"] = known
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qt", required=True, help="data/quicktest/<slug>")
    ap.add_argument("--slug", help="slug（預設 qt 目錄名；當 qt 在 <slug>/quicktest 下須明給）")
    ap.add_argument("--out", help="prob-data.json 輸出路徑（預設 <qt>/../prob/<slug>/prob-data.json 不適用時需給）")
    ap.add_argument("--dest", help="直接指定輸出目錄（放 prob-data.json）")
    a = ap.parse_args()
    qt_dir = pathlib.Path(a.qt).resolve()
    if not (qt_dir / "qt-config.yaml").exists():
        C.fail("BAD_INPUT", f"{qt_dir} 缺 qt-config.yaml")
    data = build(qt_dir, a.slug)
    if a.out:
        out = pathlib.Path(a.out)
    elif a.dest:
        out = pathlib.Path(a.dest) / "prob-data.json"
    else:
        out = qt_dir / "prob-data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out, json.dumps(data, ensure_ascii=False, indent=1))
    C.emit({"prob_data": out.as_posix(), "game": data["game"], "slug": data["slug"],
            "has_report": "report" in data and bool(data["report"].get("base")),
            "delivery": f"ps_qtdata 產出 {out.as_posix()}｜report.base {list((data.get('report') or {}).get('base') or {})}"},
           {"stage": "ps_qtdata"})


if __name__ == "__main__":
    main()
