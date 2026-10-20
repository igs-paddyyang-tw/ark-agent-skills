#!/usr/bin/env python3
"""gr_build — 標準資料集 → 指標 → report.json（報告資料契約）＋ metrics.json（給 gr_insight）。

依 capability.json（gr_probe）決定算哪些區塊；缺的區塊在 JSON 裡留空，版面顯示「尚無資料」。
歷史基準兩種來源擇一：benchmark.csv（直接給分位數），或 bench/<遊戲>/ 資料集（本程式自己算）。

用法:
  python gr_build.py --config report.yaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gr_common as C  # noqa: E402
import gr_probe  # noqa: E402


# ── 載入 ──────────────────────────────────────────────────────────────────

def load_game_rows(path: pathlib.Path) -> list:
    rows = []
    for r in C.read_csv(path):
        r["d"] = C.to_date(r["d"])
        for k in list(r.keys()):
            if k in ("bet", "spins", "win") or k.startswith("trig_"):
                r[k] = C.num(r[k])
        rows.append(r)
    return rows


def load_slot_daily(path: pathlib.Path) -> dict:
    out = {}
    if not path.is_file():
        return out
    for r in C.read_csv(path):
        out[(r["view"], C.to_date(r["d"]))] = {"slot_bet": C.num(r["slot_bet"]), "slot_players": C.num(r["slot_players"]),
                                               "rank": int(C.num(r.get("game_rank"), 0)) or None}
    return out


def quantile(xs: list, q: float):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


# ── 核心指標（目標機台與基準機台共用）────────────────────────────────────────

def core(rows: list, slot: dict, view_name: str, launch: dt.date, n_days: int, ret_days: list, deep_k: float) -> dict:
    last = max((r["d"] for r in rows), default=launch)
    n = min(n_days, (last - launch).days + 1)
    dates = [launch + dt.timedelta(days=i) for i in range(n)]
    by_day = defaultdict(lambda: {"bet": 0.0, "spins": 0.0, "win": 0.0, "uids": set(), "deep": 0, "ud": 0})
    seen = {}
    play = set()
    for r in rows:
        if r["d"] > dates[-1] or r["d"] < launch or r["spins"] <= 0:
            continue
        b = by_day[r["d"]]
        b["bet"] += r["bet"]
        b["spins"] += r["spins"]
        b["win"] += r.get("win", 0.0) or 0.0
        b["uids"].add(r["uid"])
        b["ud"] += 1
        b["deep"] += 1 if r["spins"] >= deep_k else 0
        play.add((r["uid"], r["d"]))
        if r["uid"] not in seen or r["d"] < seen[r["uid"]]:
            seen[r["uid"]] = r["d"]
    share, trial, rank, deep = [], [], [], []
    for d in dates:
        b, s = by_day[d], slot.get((view_name, d))
        share.append(b["bet"] / s["slot_bet"] if s and s["slot_bet"] else None)
        trial.append(len(b["uids"]) / s["slot_players"] if s and s["slot_players"] else None)
        rank.append(s["rank"] if s else None)
        deep.append(b["deep"] / b["ud"] if b["ud"] else None)
    ret = []
    for k in ret_days:
        elig = [u for u, f in seen.items() if (f + dt.timedelta(days=k)) <= dates[-1]]
        ret.append(sum(1 for u in elig if (u, seen[u] + dt.timedelta(days=k)) in play) / len(elig) if elig else None)
    cohorts = []
    first_by_day = defaultdict(list)
    for u, f in seen.items():
        first_by_day[f].append(u)
    for d in dates[:8]:
        us = first_by_day.get(d, [])
        vals = []
        for k in ret_days:
            t = d + dt.timedelta(days=k)
            vals.append(round(sum(1 for u in us if (u, t) in play) / len(us), 4) if us and t <= dates[-1] else None)
        cohorts.append({"date": d.strftime("%m-%d"), "users": len(us), "values": vals})
    return {"dates": dates, "by_day": by_day, "share": share, "trial": trial, "rank": rank, "deep": deep,
            "ret": ret, "cohorts": cohorts, "first": seen}


def game_scalars(rows: list, launch: dt.date, n_days: int, hk: float) -> dict:
    """單一機台全期純量（基準分布用）：實際 RTP、前 1% 玩家押量佔比、高強度玩家比例。"""
    end = launch + dt.timedelta(days=n_days - 1)
    bet = win = 0.0
    per_uid, intense, players = defaultdict(float), set(), set()
    for r in rows:
        if r["d"] < launch or r["d"] > end or r["spins"] <= 0:
            continue
        bet += r["bet"]
        win += r.get("win", 0.0) or 0.0
        per_uid[r["uid"]] += r["bet"]
        players.add(r["uid"])
        if r["spins"] >= hk:
            intense.add(r["uid"])
    bets = sorted(per_uid.values(), reverse=True)
    tb = sum(bets) or 1
    return {"rtp": (win / bet) if bet and any("win" in r for r in rows[:1]) else None,
            "top1": sum(bets[:max(1, len(bets) // 100)]) / tb if bets else None,
            "intense": len(intense) / len(players) if players else None}


def benchmarks(cfg: dict, dd: pathlib.Path, view_name: str, n_days: int, ret_days: list, deep_k: float) -> dict:
    """回傳 {metric: {'p30': [...], 'p50': [...], 'p60': [...]}}；metric ∈ share／trial／deep／ret。"""
    out = {}
    bp = dd / "benchmark.csv"
    if bp.is_file():
        tmp = defaultdict(dict)
        for r in C.read_csv(bp):
            if r.get("view") and r["view"] != view_name:
                continue
            tmp[r["metric"]][int(C.num(r["day"]))] = (C.num(r["p30"], None), C.num(r["p50"], None), C.num(r["p60"], None))
        for m, by in tmp.items():
            keys = ret_days if m == "ret" else list(range(1, n_days + 1))
            out[m] = {q: [by.get(k, (None, None, None))[i] for k in keys] for i, q in enumerate(("p30", "p50", "p60"))}
        return out
    games = []
    for g in sorted((dd / "bench").glob("*")) if (dd / "bench").is_dir() else []:
        gp = g / "game_user_daily.csv"
        if not gp.is_file():
            continue
        rows = load_game_rows(gp)
        if not rows:
            continue
        launch = min(r["d"] for r in rows)
        k = core(rows, load_slot_daily(g / "slot_daily.csv"), view_name, launch, n_days, ret_days, deep_k)
        k["scalar"] = game_scalars(rows, launch, n_days, float((cfg.get("health") or {}).get("intense_spins", 3000)))
        games.append(k)
    if len(games) < 3:
        return out
    for m, key in (("share", "share"), ("trial", "trial"), ("deep", "deep"), ("ret", "ret")):
        length = len(ret_days) if m == "ret" else n_days
        cols = [[(g[key][i] if i < len(g[key]) else None) for g in games] for i in range(length)]
        out[m] = {q: [quantile(c, p) for c in cols] for q, p in (("p30", 0.3), ("p50", 0.5), ("p60", 0.6))}
    # 全期純量的同期分布（Q5 暫定基準、健康觀察相對門檻）
    for key in ("rtp", "top1", "intense"):
        xs = [g["scalar"][key] for g in games if g["scalar"].get(key) is not None]
        if len(xs) >= 3:
            out["dist_" + key] = {f"p{int(q * 100)}": quantile(xs, q) for q in (0.1, 0.3, 0.5, 0.6, 0.8, 0.9)} | {"n": len(xs)}
    out["_n_games"] = len(games)
    return out


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def light_by_bench(v, p30, p60, reverse=False):
    if v is None or p30 is None or p60 is None:
        return "na"
    if reverse:
        return "g" if v <= p30 else ("y" if v <= p60 else "r")
    return "g" if v >= p60 else ("y" if v >= p30 else "r")


# ── 主流程 ────────────────────────────────────────────────────────────────

def build(cfg: dict) -> tuple:
    dd = C.data_dir(cfg)
    cap = gr_probe.probe(cfg)
    sec = {k: v["status"] for k, v in cap["sections"].items()}
    if not cap["datasets"]["game_user_daily"]["present"]:
        C.fail("GATE_BLOCKED", "沒有 game_user_daily.csv", "先跑 gr_run.py query／probe")
    g = cfg["game"]
    launch = C.to_date(g["launch_date"])
    n_days = int(cfg["stage"])
    ret_days = [k for k in C.stage_days(cfg) if k < n_days or k == n_days]
    deep_k = float((cfg.get("depth") or {}).get("deep_spins", 200))
    lt = cfg.get("lights") or {}
    rows_all = load_game_rows(dd / "game_user_daily.csv")
    slot = load_slot_daily(dd / "slot_daily.csv")
    slot_users = list(C.read_csv(dd / "slot_users.csv")) if (dd / "slot_users.csv").is_file() else []
    spec = cfg.get("spec") or {}
    views_out, metrics_out, notes = {}, {}, []

    # Q6（全域，不分切分）
    sources, increment, q6 = [], [], {}
    ep = dd / "erosion.csv"
    if ep.is_file():
        er = {r["game"]: (C.num(r["pre_bet"]), C.num(r["post_bet"])) for r in C.read_csv(ep)}
        tgt_post = er.get("__TARGET__", (0, 0))[1]
        others = {k: v for k, v in er.items() if k not in ("__TARGET__", "__ALL_SLOTS__")}
        dec = sorted(((k, pre - post, pre, post) for k, (pre, post) in others.items() if pre > post), key=lambda x: -x[1])
        names = cfg.get("game_names") or {}
        for k, amt, pre, post in dec[:5]:
            sources.append({"name": names.get(k, k), "delta": round((post - pre) / pre, 4) if pre else -1.0,
                            "note": f"押量減少 {C.fmt_money(amt, cfg)}（{(post - pre) / pre * 100:.0f}%）" if pre else ""})
        eros = sum(x[1] for x in dec) / tgt_post if tgt_post else None
        allp = er.get("__ALL_SLOTS__")
        slot_chg = (allp[1] - allp[0]) / allp[0] if allp and allp[0] else None
        w = int(cfg.get("erosion_window_days", 7))
        increment = [{"label": "虎機總押量", "value": "—" if slot_chg is None else f"{slot_chg * 100:+.1f}%", "note": f"上線後 {w} 日 vs 上線前 {w} 日"},
                     {"label": "侵蝕率", "value": C.pct(eros, 0), "note": "本機押量中，來自本機玩家在其他機台減少的部分"}]
        q6 = {"erosion_rate": eros, "slot_change": slot_chg, "top_source": dec[0][0] if dec else None}

    hours = None
    hp = dd / "hours.csv"
    if hp.is_file():
        hr = [(r["bucket"], C.num(r["bet"])) for r in C.read_csv(hp)]
        tot = sum(b for _, b in hr) or 1
        hours = {"labels": [k for k, _ in hr], "values": [round(b / tot, 4) for _, b in hr]}

    dims = cfg.get("composition") or []
    for view in cfg.get("views") or [{"name": "全體"}]:
        vn = view["name"]
        if view.get("column") and view["column"] not in cap["datasets"]["game_user_daily"]["columns"]:
            notes.append(f"切分「{vn}」略過：game_user_daily 沒有欄位 {view['column']}")
            continue
        rows = [r for r in rows_all if C.in_view(r, view)]
        if not rows:
            notes.append(f"切分「{vn}」沒有資料")
            continue
        K = core(rows, slot, vn, launch, n_days, ret_days, deep_k)
        B = benchmarks(cfg, dd, vn, len(K["dates"]), ret_days, deep_k)
        days = [f"D{i + 1}" for i in range(len(K["dates"]))]
        tot_bet = sum(b["bet"] for b in K["by_day"].values())
        tot_spins = sum(b["spins"] for b in K["by_day"].values())
        tot_win = sum(b["win"] for b in K["by_day"].values())
        players = len(K["first"])
        share_avg, trial_avg = avg(K["share"]), avg(K["trial"])
        bshare = B.get("share") or {}
        v = {}
        # Q1
        rank_last = next((x for x in reversed(K["rank"]) if x), None)
        v["kpi"] = [
            {"label": "累計押量", "value": C.fmt_money(tot_bet, cfg), "note": f"日均 {C.fmt_money(tot_bet / len(days), cfg)}"},
            {"label": "平均押注佔比", "value": C.pct(share_avg), "note": ("同期中位 " + C.pct(avg(bshare.get("p50", [])))) if bshare else "沒有歷史基準"},
            {"label": "最新押量排名", "value": f"第 {rank_last} 名" if rank_last else "—", "note": "市場虎機押量"},
            {"label": "累計遊玩人數", "value": f"{players:,}", "note": "平均試玩率 " + C.pct(trial_avg)},
        ]
        if any(x is not None for x in K["share"]):
            v["share"] = {"days": days, "game": K["share"]}
            if bshare:
                v["share"].update({"bench_p50": bshare["p50"], "bench_p30": bshare["p30"], "bench_p60": bshare["p60"]})
        # Q2
        latest = {}
        for r in sorted(rows, key=lambda r: r["d"]):
            latest[r["uid"]] = r
        su = [r for r in slot_users if C.in_view(r, view)]
        comp, top_ratio = [], None
        for dim in dims:
            col = dim.get("column")
            if col not in rows[0]:
                continue
            groups = C.groups_of(dim)

            def dist(items):
                cnt = defaultdict(int)
                for it in items:
                    b = C.bucket_of(it.get(col), dim)
                    if b is not None:
                        cnt[b] += 1
                t = sum(cnt.values())
                return [round(cnt[gname] / t, 4) if t else 0 for gname in groups], t
            gd, gt = dist(latest.values())
            ad, at = dist(su) if su and col in su[0] else ([], 0)
            if not gt:
                continue
            item = {"title": dim["title"], "groups": groups, "game": gd, "all": ad if at else gd, "base_label": "全虎機" if at else "（無對照）"}
            comp.append(item)
            if dim is dims[0] and at and ad[-1]:
                top_ratio = gd[-1] / ad[-1]
        if comp:
            v["composition"] = comp
        # Q3
        bret = B.get("ret") or {}
        v["retention"] = {"days": ret_days, "game": K["ret"], "cohorts": K["cohorts"]}
        if bret:
            v["retention"]["bench"] = bret["p50"]
        # Q4
        dseg = next((d for d in dims if d["title"] == (cfg.get("depth") or {}).get("segment")), None)
        drows = []

        def depth_row(label, rs, denom):
            us = {r["uid"] for r in rs}
            sp = sum(r["spins"] for r in rs)
            bt = sum(r["bet"] for r in rs)
            dpr = sum(1 for r in rs if r["spins"] >= deep_k) / len(rs) if rs else None
            return [label, C.pct(len(us) / denom) if denom else "—", f"{sp / len(us):,.0f}" if us else "—",
                    f"{bt / sp:,.0f}" if sp else "—", C.pct(dpr)]
        if dseg and dseg.get("column") in rows[0]:
            for gname in C.groups_of(dseg):
                rs = [r for r in rows if C.bucket_of(latest[r["uid"]].get(dseg["column"]), dseg) == gname]
                den = sum(1 for r in su if C.bucket_of(r.get(dseg["column"]), dseg) == gname) if su else 0
                if rs:
                    drows.append(depth_row(gname, rs, den))
        drows.append(depth_row("全部", rows, len(su)))
        v["depth"] = {"columns": ["分層", "試玩率（期間）", "人均手數", "平均押注", f"深度玩家比例（單日 ≥ {deep_k:.0f} 手）"], "rows": drows}
        # Q5
        q5 = {"has_win": "win" in rows[0], "out_streak": 0, "trigger_alerts": []}
        if q5["has_win"] and spec.get("target_rtp") and spec.get("sigma"):
            cb = cs = cw = 0.0
            act, lo, hi, streak = [], [], [], 0
            for d in K["dates"]:
                b = K["by_day"][d]
                cb += b["bet"]
                cs += b["spins"]
                cw += b["win"]
                if not cb or not cs:
                    act.append(None), lo.append(None), hi.append(None)
                    continue
                half = 1.96 * float(spec["sigma"]) / math.sqrt(cs)
                r_ = cw / cb
                act.append(round(r_, 6)); lo.append(spec["target_rtp"] - half); hi.append(spec["target_rtp"] + half)
                streak = streak + 1 if not (lo[-1] <= r_ <= hi[-1]) else 0
                q5["out_streak"] = max(q5["out_streak"], streak)
            v["rtp"] = {"days": days, "actual_cum": act, "target": spec["target_rtp"], "lo": lo, "hi": hi}
            q5.update({"rtp": act[-1], "rtp_lo": lo[-1], "rtp_hi": hi[-1], "rtp_dir": "high" if act[-1] and act[-1] > hi[-1] else ("low" if act[-1] and act[-1] < lo[-1] else "in")})
        elif q5["has_win"] and B.get("dist_rtp"):
            # 暫定基準：規格沒給目標 RTP（線上設定檔未提供）→ 用同期新機實際 RTP 的 P10～P90；只能判「是否落在平台常態」，不代表符合設計
            dr = B["dist_rtp"]
            cb = cw = 0.0
            act = []
            for d in K["dates"]:
                b = K["by_day"][d]
                cb += b["bet"]
                cw += b["win"]
                act.append(round(cw / cb, 6) if cb else None)
            n_ = len(days)
            v["rtp"] = {"days": days, "actual_cum": act, "target": dr["p50"], "lo": [dr["p10"]] * n_, "hi": [dr["p90"]] * n_,
                        "baseline": f"暫定基準：同期新機 {dr['n']} 款實際 RTP（中位數 {dr['p50']:.2%}、P10～P90 {dr['p10']:.2%}～{dr['p90']:.2%}）；線上設定檔目標 RTP 未提供"}
            last = act[-1]
            q5.update({"rtp": last, "rtp_lo": dr["p10"], "rtp_hi": dr["p90"], "baseline": "bench",
                       "rtp_dir": "high" if last and last > dr["p90"] else ("low" if last and last < dr["p10"] else "in")})
        trig = []
        for name, freq in (spec.get("triggers") or {}).items():
            col = f"trig_{name}"
            if col not in rows[0]:
                continue
            cnt = sum(r[col] for r in rows)
            exp = tot_spins / float(freq) if freq else 0
            dev = (cnt / exp - 1) if exp else None
            status = "樣本不足" if exp < 30 else ("異常" if dev is not None and abs(dev) > float(lt.get("q5_trigger_dev", 0.2)) else "正常")
            trig.append({"name": name, "spec": f"1 / {float(freq):,.0f}", "actual": f"1 / {tot_spins / cnt:,.0f}" if cnt else "0 次",
                         "deviation": "—" if dev is None else f"{dev * 100:+.1f}%", "status": status})
            if status == "異常":
                q5["trigger_alerts"].append({"name": name, "dev": dev})
        if trig:
            v["triggers"] = trig
        # Q6
        if sources:
            v["sources"] = sources
        if increment:
            v["increment"] = increment
        # 健康
        per_uid = defaultdict(float)
        intense = set()
        hk = float((cfg.get("health") or {}).get("intense_spins", 3000))
        for r in rows:
            per_uid[r["uid"]] += r["bet"]
            if r["spins"] >= hk:
                intense.add(r["uid"])
        bets = sorted(per_uid.values(), reverse=True)
        tb = sum(bets) or 1
        top1 = sum(bets[:max(1, len(bets) // 100)]) / tb
        top10 = sum(bets[:max(1, len(bets) // 10)]) / tb
        late = None
        if hours:
            lb = (cfg.get("health") or {}).get("late_buckets") or []
            late = sum(val for k, val in zip(hours["labels"], hours["values"]) if k in lb)
        v["health"] = {"tiles": [
            {"label": "前 1% 玩家押量佔比", "value": C.pct(top1, 0), "note": f"{max(1, len(bets) // 100):,} 人"},
            {"label": "前 10% 玩家押量佔比", "value": C.pct(top10, 0), "note": f"{max(1, len(bets) // 10):,} 人"},
            {"label": "高強度玩家", "value": f"{len(intense):,} 人", "note": f"單日單機 ≥ {hk:.0f} 手，佔遊玩人數 {C.pct(len(intense) / players if players else None)}"},
            {"label": "深夜押量佔比", "value": C.pct(late, 0) if late is not None else "—", "note": "、".join((cfg.get("health") or {}).get("late_buckets") or []) or "未設定"}]}
        if hours:
            v["health"]["hours"] = hours
        # 燈號
        early = n_days <= 7
        ret_key = 1 if early else 7
        ri = ret_days.index(ret_key) if ret_key in ret_days else None
        ret_v = K["ret"][ri] if ri is not None else None
        b_ret30 = bret["p30"][ri] if bret and ri is not None else None
        b_ret60 = bret["p60"][ri] if bret and ri is not None else None
        share_eval = share_avg if early else avg(K["share"][-7:])
        bs30 = avg(bshare.get("p30", [])) if early else avg((bshare.get("p30") or [])[-7:])
        bs60 = avg(bshare.get("p60", [])) if early else avg((bshare.get("p60") or [])[-7:])
        deep_avg = avg(K["deep"])
        bdeep = B.get("deep") or {}
        lights = {"Q1": light_by_bench(share_eval, bs30, bs60) if sec["Q1"] != "skip" else "na"}
        r2 = lt.get("q2_top_group_ratio", [0.8, 1.0])
        lights["Q2"] = "na" if top_ratio is None else ("g" if top_ratio >= r2[1] else ("y" if top_ratio >= r2[0] else "r"))
        lights["Q3"] = light_by_bench(ret_v, b_ret30, b_ret60)
        lights["Q4"] = light_by_bench(deep_avg, avg(bdeep.get("p30", [])), avg(bdeep.get("p60", []))) if bdeep else "na"
        if not q5["has_win"] and not trig:
            lights["Q5"] = "na"
        elif q5.get("baseline") == "bench":
            lights["Q5"] = "r" if q5["rtp_dir"] != "in" or q5["trigger_alerts"] else "y"   # 暫定基準不給綠燈
        elif q5["out_streak"] >= int(lt.get("q5_out_streak", 3)) or q5["trigger_alerts"]:
            lights["Q5"] = "r"
        elif q5["out_streak"] > 0:
            lights["Q5"] = "y"
        else:
            lights["Q5"] = "g" if ("rtp" in q5 or trig) else "na"
        e6 = lt.get("q6_erosion", [0.4, 0.6])
        er_ = q6.get("erosion_rate")
        lights["Q6"] = "na" if er_ is None else ("g" if er_ < e6[0] else ("y" if er_ < e6[1] else "r"))
        hi_ratio = len(intense) / players if players else 0
        hq = f"p{int(float(lt.get('h_bench_q', 0.8)) * 100)}"
        dt1, dti = B.get("dist_top1"), B.get("dist_intense")
        top1_cut = dt1[hq] if dt1 else float(lt.get("h_top1", 0.4))          # 有同期基準 → 同期 P80；否則固定門檻
        int_cut = dti[hq] if dti else float(lt.get("h_intense_ratio", 0.01))
        flags = (top1 > top1_cut) + (hi_ratio > int_cut)
        basis = f"同期 {hq.upper()}" if dt1 else "固定門檻"
        for t_ in v["health"]["tiles"]:
            if t_["label"] == "前 1% 玩家押量佔比":
                t_["note"] += f"；{basis} {C.pct(top1_cut, 0)}" + (f"（同期中位數 {C.pct(dt1['p50'], 0)}）" if dt1 else "")
            elif t_["label"] == "高強度玩家":
                t_["note"] += f"；{basis} {C.pct(int_cut)}"
        lights["H"] = ["g", "y", "r"][flags]
        v["verdict"] = {"lights": lights}
        views_out[vn] = v
        metrics_out[vn] = {
            "stage": n_days, "days": len(days), "players": players, "bet": tot_bet, "spins": tot_spins,
            "share_avg": share_avg, "share_first": next((x for x in K["share"] if x is not None), None),
            "share_last": next((x for x in reversed(K["share"]) if x is not None), None),
            "share_eval": share_eval, "bench_share_p30": bs30, "bench_share_p50": (avg(bshare.get("p50", [])) if early else avg((bshare.get("p50") or [])[-7:])) if bshare else None,   # 與 p30／p60 同窗口
            "bench_share_p60": bs60, "trial_avg": trial_avg, "bench_trial_p50": avg((B.get("trial") or {}).get("p50", [])) if B.get("trial") else None,
            "ret": dict(zip(ret_days, K["ret"])), "ret_eval": ret_v, "bench_ret_p30": b_ret30, "bench_ret_p60": b_ret60,
            "top_group_ratio": top_ratio, "deep_avg": deep_avg, "rank_last": rank_last,
            "q5": q5, "q6": q6, "top1": top1, "top10": top10, "intense_ratio": hi_ratio, "late_share": late,
            "h_top1_cut": top1_cut, "h_intense_cut": int_cut, "h_basis": "bench" if dt1 else "fixed",
            "bench_rtp": B.get("dist_rtp"), "bench_top1": dt1, "bench_intense": dti,
            "lights": lights, "bench_games": B.get("_n_games") or ("benchmark.csv" if (dd / "benchmark.csv").is_file() else 0),
        }
    if not views_out:
        C.fail("GATE_BLOCKED", "所有切分都沒有資料", "檢查 views 設定與 game_user_daily 欄位", {"notes": notes})
    first = next(iter(views_out.values()))
    data_through = max(r["d"] for r in rows_all)
    report = {
        "meta": {"game_name": g["name"], "game_id": g.get("id"), "launch_date": str(launch), "data_through": str(data_through),
                 "stage": n_days, "benchmark_label": _bench_label(first, metrics_out)},
        "verdict": {"headline": "", "lights": first["verdict"]["lights"], "next": []},
        "views": views_out,
        "definitions": [
            ["粒度", "日；本機所有子 ID 合併計算"], ["押注佔比", "本機押量 ÷ 該切分虎機總押量"],
            ["試玩率", "本機遊玩人數 ÷ 當日（或期間）虎機有下注人數"], ["回訪率 Dn", "首玩日 d 的玩家，在 d+n 日再玩本機的比例"],
            ["RTP 信賴帶", "目標 RTP ± 1.96·σ／√累計手數"], ["侵蝕率", "本機玩家在其他機台減少的押量 ÷ 本機押量（上線後窗口）"],
            ["燈號", "有歷史基準時看分位數（≥P60 綠、P30–P60 黃、<P30 紅）；機率與侵蝕用 report.yaml 的固定門檻"]],
        "footnote": "；".join(notes + [f"{k}：{v['why']}" for k, v in cap["sections"].items() if v["status"] != "ok" and v["why"]]),
        "capability": {k: v["status"] for k, v in cap["sections"].items()},
    }
    return report, metrics_out, cap


def _bench_label(first, metrics):
    m = next(iter(metrics.values()))
    b = m.get("bench_games")
    if not b:
        return "無歷史基準（燈號以固定門檻與絕對值判斷）"
    return f"歷史新機同期（{b} 款）" if isinstance(b, int) else "benchmark.csv 提供的歷史分位數"


def main() -> None:
    ap = argparse.ArgumentParser(description="資料集 → report.json + metrics.json")
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    report, metrics, cap = build(cfg)
    dd = C.data_dir(cfg)
    (dd / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (dd / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    C.emit({"report": str(dd / "report.json"), "metrics": str(dd / "metrics.json"), "views": list(report["views"]),
            "lights": report["verdict"]["lights"], "capability": report["capability"],
            "next": f"gr_run.py insight --config {a.config}"}, {"stage": "build"})


if __name__ == "__main__":
    main()
