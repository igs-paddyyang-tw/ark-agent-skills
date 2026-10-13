#!/usr/bin/env python3
"""ps_mdblocks — 兩種模式共用的 Content 軌「契約表格」產生器（1.4.0）。

ps_probspec（qt 模式）與 ps_probspec_xlsx（xlsx 模式）都用這裡的函式把快測結果 / 參數 / 輪帶寫成
references/prob-spec-contract.md §表格契約規定的表頭，ps_html 才能從 md 一次畫出 KPI、熱度表、長條、旗標與帶面。
每個函式回傳 md 行（list[str]）；數字一律透過呼叫端給的 dv(value, from) 登記派生值（ps_lint PS-NUM 允許集）。
"""
from __future__ import annotations

import re

PENDING = "待決議"


def md_table(head: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(str(h) for h in head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return out + [""]


def fnum(v) -> str:
    """數值 → md 文字：整數加千分位、浮點照 repr（與 JSON 文字逐字一致，PS-NUM 才回溯得到）。"""
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return f"{int(v):,}" if v.is_integer() else repr(v)
    if isinstance(v, int):
        return f"{v:,}"
    return str(v).replace("\n", " / ")


def pct_text(v, unit_fraction: bool) -> str:
    """百分比文字：unit_fraction=True 表示來源是 0–1 小數（rtp-report v1），否則來源已是 %。"""
    if v is None:
        return "—"
    x = v * 100 if unit_fraction else v
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s + "%"


# ------------------------------------------------------------------ §2 快測摘要（兩種模式都產）

def summary_table(items: list[tuple[str, str, str]]) -> list[str]:
    """items = [(指標, 值文字, 來源)]；值已由呼叫端 dv() 過。"""
    rows = [[k, v, s] for k, v, s in items if v not in (None, "", "—")]
    return ["### 快測摘要", "", "> 一表看完：總覽 KPI 與 RTP 組成圖由本表產生；值與下方各表相同來源。", ""] + md_table(["指標", "值", "來源"], rows)


# ------------------------------------------------------------------ xlsx 模式（prob-data.report：百分比單位 %）

def xlsx_summary(rep: dict, K: dict, dv) -> list[str]:
    base, summ, run = rep.get("base") or {}, rep.get("summary") or {}, rep.get("run") or {}
    main, free = base.get("Main") or [], base.get("Free") or []
    rs = K.get("reelsets") or {}
    golden = (rs.get("totals") or {}).get("TOTAL RTP")
    tot = summ.get("rtp_total")
    items = []
    if tot is not None:
        items.append(("總 RTP", dv(f"{tot}%", "數據資料 RTP 分項 總計"), "數據資料 RTP 分項"))
    elif base.get("Total"):
        items.append(("總 RTP", dv(base["Total"][0], "數據資料 BASE INFO Total"), "數據資料 BASE INFO"))
    if summ.get("rtp_main") is not None:
        items.append(("主遊戲 RTP", dv(f"{summ['rtp_main']}%", "數據資料 RTP 分項 主遊戲"), "數據資料 RTP 分項"))
    elif main:
        items.append(("主遊戲 RTP", dv(main[0], "BASE INFO Main"), "數據資料 BASE INFO"))
    if summ.get("rtp_free") is not None:
        items.append(("免費遊戲 RTP", dv(f"{summ['rtp_free']}%", "數據資料 RTP 分項 免費遊戲"), "數據資料 RTP 分項"))
    elif free:
        items.append(("免費遊戲 RTP", dv(free[0], "BASE INFO Free"), "數據資料 BASE INFO"))
    if main:
        items.append(("主遊戲命中率", dv(main[2], "BASE INFO Main Trigger %"), "數據資料 BASE INFO"))
        if len(main) > 6:
            items.append(("主遊戲最大倍數", dv(main[6], "BASE INFO Main MaxMulti"), "數據資料 BASE INFO"))
    if free:
        items.append(("FG 觸發率", dv(free[2], "BASE INFO Free Trigger %"), "數據資料 BASE INFO"))
        items.append(("FG 平均觸發局數", dv(free[1], "BASE INFO Free Freq"), "數據資料 BASE INFO"))
        items.append(("FG 平均倍率", dv(free[3], "BASE INFO Free Multi"), "數據資料 BASE INFO"))
        if len(free) > 6:
            items.append(("FG 最大倍數", dv(free[6], "BASE INFO Free MaxMulti"), "數據資料 BASE INFO"))
    if run.get("total"):
        items.append(("總手數", dv(f"{run['total']:,}", "數據資料 Total"), "數據資料 Workers 行"))
    if run.get("timestamp"):
        items.append(("執行時間", run["timestamp"][:16], "數據資料 版本行"))
    if run.get("version"):
        items.append(("引擎版本", run["version"], "數據資料 版本行"))
    if run.get("flag"):
        items.append(("旗標", run["flag"], "數據資料 第一行"))
    if golden is not None:
        g = golden * 100 if golden < 5 else golden
        items.append(("golden RTP", dv(f"{g:.2f}", f"{rs.get('block')} TOTAL RTP × 100") + "%", f"參數表 {rs.get('block')} 加權"))
        if tot is not None:
            items.append(("誤差", dv(f"{tot - g:+.3f}", "rtp_total − golden") + " pp", "計算"))
            items.append(("容許誤差", dv("0.2", "容許誤差常數 pp") + " pp", "P-000"))
    return summary_table(items)


def xlsx_data_tables(rep: dict, K: dict, dv) -> list[str]:
    """§2 其餘契約表：符號命中、輪帶組 RTP、贏分分布、100 手、十分位、FG 詳細。"""
    L: list[str] = []
    for key, title in (("symbol_hit_rate", "主遊戲符號命中率"), ("symbol_hit_rtp", "主遊戲符號 RTP 貢獻")):
        dat = rep.get(key)
        if not dat:
            continue
        n = max(len(v) for v in dat.values())
        head = ["符號"] + [f"x{i + 1}" for i in range(n - 1)] + ["TOTAL"]
        rows = [[k] + [dv(pct_text(x, False), f"{key}[{k}][{i}]") for i, x in enumerate(v)] for k, v in dat.items()]
        L += [f"### {title}", ""] + md_table(head, rows)
    sim = rep.get("reel_set_rtp") or []
    if sim:
        rs = K.get("reelsets") or {}
        by = {r["set"]: r for r in sim}
        if rs:
            head = ["組", "R1–R5 換帶", "說明", "權重", "理論 Total RTP", "實測 Total RTP", "實測 FG RTP", "實測手數"]
            rows = []
            theo_key = next((k for k in (rs["sets"][0].get("extra") or {}) if "TOTAL" in k.upper()), None)
            for s in rs["sets"]:
                m = by.get(s["idx"])
                desc = next((v for k, v in (s.get("extra") or {}).items() if isinstance(v, str)), "")
                theo = (s["extra"].get(theo_key) if theo_key else None)
                rows.append([str(s["idx"]), "/".join(str(f) for f in s["flags"]), desc, dv(fnum(s["weight"]), f"{rs['block']} weight[{s['idx']}]"),
                             dv(pct_text(theo * 100 if (theo is not None and theo < 5) else theo, False), f"{rs['block']} TOTAL RTP[{s['idx']}] × 100") if theo is not None else "—",
                             dv(pct_text(m["total"], False), f"reel_set_rtp[{s['idx']}].total") if m else "—",
                             dv(pct_text(m["fg"], False), f"reel_set_rtp[{s['idx']}].fg") if (m and m.get("fg") is not None) else "—",
                             dv(f"{m['spins']:,}", f"reel_set_rtp[{s['idx']}].spins") if (m and m.get("spins")) else "—"])
            L += ["### 輪帶組 RTP（理論 vs 實測）", ""] + md_table(head, rows)
        else:
            L += ["### 輪帶組 RTP（實測）", ""] + md_table(["組", "實測 Total RTP", "實測 FG RTP", "實測手數"],
                                                       [[str(r["set"]), dv(pct_text(r["total"], False), f"reel_set_rtp[{r['set']}].total"), dv(pct_text(r["fg"], False), f"reel_set_rtp[{r['set']}].fg") if r.get("fg") is not None else "—", dv(f"{r['spins']:,}", f"reel_set_rtp[{r['set']}].spins") if r.get("spins") else "—"] for r in sim])
    sr = rep.get("special_range") or []
    if sr:
        rows = [[r["range"]] + [dv(pct_text(x, False), f"special_range[{i}].appear[{j}]") for j, x in enumerate(r["appear"])] + [dv(pct_text(x, False), f"special_range[{i}].rtp[{j}]") for j, x in enumerate(r["rtp"])] for i, r in enumerate(sr)]
        L += ["### 贏分區間分布", ""] + md_table(["贏分區間（倍）", "出現 Total", "出現 Main", "出現 Free", "RTP Total", "RTP Main", "RTP Free"], rows)
    mu = rep.get("multiple") or []
    if mu:
        rows = [[m["range"], dv(fnum(m["spins_per_hit"]), f"multiple[{i}].spins_per_hit"), f"≥ {dv(str(m['ge']), f'multiple[{i}].ge')}", dv(fnum(m["spins_per_hit_ge"]), f"multiple[{i}].spins_per_hit_ge")] for i, m in enumerate(mu)]
        L += ["### 倍數出現頻率", ""] + md_table(["贏分區間（倍）", "約每幾局", "累計門檻", "累計約每幾局"], rows)
    a100 = rep.get("asset_100") or []
    if a100:
        L += ["### 100 手資產分布", ""] + md_table(["100 手後剩餘資產", "佔比"], [[a["range"], dv(pct_text(a["pct"], False), f"asset_100[{i}].pct")] for i, a in enumerate(a100)])
    dec = rep.get("decile") or []
    if dec:
        L += ["### 十分位", ""] + md_table(["分位", "Total", "Main", "Free", "F_Spin"], [[d["label"]] + [dv(v, f"decile[{i}].vals[{j}]") for j, v in enumerate(d["vals"])] + [""] * (4 - len(d["vals"])) for i, d in enumerate(dec)])
    fg = rep.get("fg_detail") or {}
    if fg:
        L += xlsx_fg_detail(fg, K, dv)
    return L


def xlsx_fg_detail(fg: dict, K: dict, dv) -> list[str]:
    L: list[str] = []
    if fg.get("groups"):
        w = next((x for x in K.get("weights", []) if str(x.get("block", "")).startswith("F-1")), None)
        exp = {}
        if w:
            tot = sum(i["weight"] for i in w["items"] if isinstance(i["weight"], (int, float)))
            exp = {i["label"]: (i["weight"], i["weight"] / tot * 100) for i in w["items"] if isinstance(i["weight"], (int, float)) and tot}
        grp_rtp = dict(fg.get("group_rtp") or [])
        rows = []
        for g in fg["groups"]:
            e = exp.get(g["name"])
            rows.append([g["name"], dv(fnum(e[0]), f"F-1 weight[{g['name']}]") if e else "—", (dv(f"{e[1]:.2f}", f"F-1 weight[{g['name']}] / Σ × 100") + "%") if e else "—",
                         dv(f"{g['count']:,}", "數據資料 FG內部"), dv(f"{g['pct']:.2f}", "數據資料 FG內部") + "%",
                         (dv(fnum(grp_rtp.get(g["name"])), "數據資料 各組別RTP貢獻") + "%") if grp_rtp.get(g["name"]) is not None else "—"])
        L += ["### FG 強中弱實測分佈", ""] + md_table(["組別", "F-1 權重", "理論佔比", "次數", "實際佔比", "FG RTP 貢獻"], rows)
    kv = []
    if fg.get("trigger_total") is not None:
        kv.append(["FG 總觸發次數", dv(f"{fg['trigger_total']:,}", "FG 詳細統計 觸發面")])
    for key, label in (("base_avg", "平均初始基底（倍）"), ("all888_avg", "全放 888 平均贏分（倍）"), ("settle_avg", "FG 平均贏分（倍）"), ("settle_max", "FG 最大贏分（倍）"), ("sd", "標準差"), ("cv", "變異係數"), ("avg_mult", "平均總乘倍"), ("avg_coin_win", "平均金幣贏分"), ("avg_fish_win", "平均鯉魚贏分")):
        if fg.get(key) is not None:
            kv.append([label, dv(fnum(fg[key]), f"FG 詳細統計 {key}")])
    a = fg.get("all888")
    if a:
        kv.append(["全放 888 事件", f"{dv(f'{a['count']:,}', 'FG 詳細統計 all888.count')} 次（佔 FG {dv(fnum(a['pct']), 'FG 詳細統計 all888.pct')}%）"])
    for k, v in (fg.get("avg_times") or {}).items():
        kv.append([f"每場平均{k}次數", dv(fnum(v), f"FG 詳細統計 avg_times.{k}")])
    if kv:
        L += ["### FG 詳細統計", ""] + md_table(["項目", "值"], kv)
    if fg.get("contrib"):
        L += ["**FG 贏分貢獻拆解**", ""] + md_table(["來源", "佔比"], [[k, dv(fnum(v), f"FG 詳細統計 contrib.{k}") + "%"] for k, v in fg["contrib"]])
    if fg.get("trigger_dist"):
        rows = [[f"{dv(str(d['k']), 'FG 詳細統計 trigger_dist.k')} 顆", dv(f"{d['count']:,}", "FG 詳細統計 trigger_dist.count"), dv(fnum(d["pct"]), "FG 詳細統計 trigger_dist.pct") + "%"] for d in fg["trigger_dist"]]
        L += ["**觸發面：進場特殊符號顆數分布**", ""] + md_table(["觸發顆數", "次數", "佔 FG"], rows)
    if fg.get("sc_enter"):
        rows = [[f"{dv(str(x['sc']), 'FG 詳細統計 sc_enter.sc')} 顆", dv(f"{x['count']:,}", "FG 詳細統計 sc_enter.count"), dv(fnum(x["pct"]), "FG 詳細統計 sc_enter.pct") + "%", dv(fnum(x["avg"]), "FG 詳細統計 sc_enter.avg")] for x in fg["sc_enter"]]
        L += ["**各進場 SC 顆數 → 平均 FG 倍率**", ""] + md_table(["進場 SC 顆數", "次數", "佔比", "均 FG 倍率"], rows)
    if fg.get("group_detail") and fg.get("group_detail_cols"):
        cols = fg["group_detail_cols"]
        rows = [[dv(c, f"FG 詳細統計 各組別詳細[{i}][{j}]") if j else c for j, c in enumerate(r)] for i, r in enumerate(fg["group_detail"])]
        L += ["**各組別詳細**", ""] + md_table(cols, rows)
    return L


def xlsx_param_blocks(data: dict, dv, anchor_sheet: str) -> list[str]:
    """§4：有 recognizer 的區塊寫成契約表；其餘照原樣 dump（含來源座標）。"""
    K = data.get("known") or {}
    by_block: dict[str, list] = {}
    for kind in ("weights", "dual", "yesno", "matrix", "series", "scalars"):
        for x in K.get(kind) or []:
            by_block.setdefault(x["block"], []).append((kind, x))
    if K.get("reelsets"):
        by_block.setdefault(K["reelsets"]["block"], []).append(("reelsets", K["reelsets"]))
    L: list[str] = []
    try:
        from openpyxl.utils import get_column_letter  # type: ignore
    except ImportError:  # pragma: no cover
        get_column_letter = lambda c: chr(64 + c)  # noqa: E731
    for b in (data.get("params") or {}).get("blocks", []):
        bid = b["id"]
        title = f"### 表 {bid}" if re.match(r"^[A-Z]-", bid) else f"### {bid}"
        if b.get("title"):
            title += f"　{b['title']}"
        L += [title, ""]
        rec = by_block.get(bid)
        if rec and bid not in ("基本資訊", "Odds表", "Odds 表", "Pay table"):
            for kind, x in rec:
                L += globals()["blk_" + kind](x, dv, anchor_sheet)
            continue
        if bid in ("基本資訊", "Odds表", "Odds 表", "Pay table"):
            continue  # §1 已有基本規格 / Pay table 契約表
        for t in b["tables"]:
            rows = t["rows"]
            if not rows:
                continue
            width = max(len(r["cells"]) for r in rows)
            flat = [v for r in rows for v in r["cells"] if v is not None]
            if len(rows) == 1 and len(flat) == 1 and isinstance(flat[0], str):
                L += [f"**{flat[0]}**", ""]
                continue
            first = rows[0]["cells"]
            if sum(1 for v in first if isinstance(v, str)) >= 2 or (len(rows) > 1 and any(isinstance(v, str) for v in first) and not any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in first)):
                head = [("" if v is None else str(v)) for v in first] + [""] * (width - len(first))
                body = rows[1:]
            else:
                head = [f"c{i+1}" for i in range(width)]
                body = rows
            md_rows = []
            for r in body:
                cells = [fnum(v) if v is not None else "" for v in r["cells"]] + [""] * (width - len(r["cells"]))
                md_rows.append(cells + [f"{anchor_sheet}!{get_column_letter(t['c0'])}{r['r']}"])
            L += md_table([h or " " for h in head] + ["來源"], md_rows)
    return L


def blk_reelsets(x: dict, dv, sheet: str) -> list[str]:
    extra_keys = [k for k in (x["sets"][0].get("extra") or {})]
    n = len(x["sets"][0]["flags"])
    head = ["Index"] + [f"R{i + 1}" for i in range(n)] + ["權重"] + extra_keys + ["來源"]
    rows = []
    for s in x["sets"]:
        rows.append([str(s["idx"])] + [str(f) for f in s["flags"]] + [fnum(s["weight"])] + [fnum(s["extra"].get(k)) if not isinstance(s["extra"].get(k), str) else s["extra"][k] for k in extra_keys] + [f"{sheet}!row{s['row']}" if s.get("row") else x.get("anchor", "")])
    tot = x.get("totals") or {}
    if tot:
        rows.append(["Σ"] + [""] * n + [fnum(tot.get("weight_sum")) if tot.get("weight_sum") is not None else ""] + [fnum(tot.get(k)) if tot.get(k) is not None else "" for k in extra_keys] + [x.get("anchor", "")])
    return md_table(head, rows)


def blk_weights(x: dict, dv, sheet: str) -> list[str]:
    rows = [[i["label"], fnum(i["weight"]), " ".join(str(r) for r in i["rest"]) if i.get("rest") else "", x.get("anchor", "")] for i in x["items"]]
    return md_table(["項目", "權重", "備註", "來源"], rows)


def blk_yesno(x: dict, dv, sheet: str) -> list[str]:
    return md_table(["組別", "是", "否", "來源"], [[r["name"], fnum(r["yes"]), fnum(r["no"]), x.get("anchor", "")] for r in x["rows"]])


def blk_dual(x: dict, dv, sheet: str) -> list[str]:
    names = x.get("names") or [f"欄 {i+1}" for i in range(len(x["columns"]))]
    cols = x["columns"]
    n = max(len(c["pairs"]) for c in cols)
    head = []
    for nm in names[:len(cols)]:
        head += [f"{nm} 倍數", f"{nm} 權重"]
    rows = []
    for i in range(n):
        r = []
        for c in cols:
            if i < len(c["pairs"]):
                v, w = c["pairs"][i]
                r += [fnum(v), fnum(w)]
            else:
                r += ["", ""]
        rows.append(r + [x.get("anchor", "")])
    foot = []
    for c in cols:
        ex = " · ".join(f"{k} {fnum(v)}" for k, v in (c.get("extra") or {}).items())
        foot += [ex or "Σ", fnum(c.get("total")) if c.get("total") is not None else ""]
    if any(foot):
        rows.append(foot + [x.get("anchor", "")])
    return md_table(head + ["來源"], rows)


def blk_matrix(x: dict, dv, sheet: str) -> list[str]:
    head = ["組別"] + [str(h) for h in x["head"]] + ["來源"]
    rows = [[g["name"]] + [fnum(v) for v in g["values"]] + [""] * (len(x["head"]) - len(g["values"])) + [x.get("anchor", "")] for g in x["groups"]]
    cap = x.get("caption") or x.get("title") or ""
    return ([f"**{cap}**", ""] if cap else []) + md_table(head, rows)


def blk_series(x: dict, dv, sheet: str) -> list[str]:
    head = x.get("head")
    if head:
        h = ["項目" if not head[0] else str(head[0])] + [str(c) for c in head[1:]] + ["來源"]
        return md_table(h, [[r["label"]] + [fnum(v) for v in r["values"]] + [""] * (len(head) - 1 - len(r["values"])) + [x.get("anchor", "")] for r in x["rows"]])
    if len(x["rows"]) >= 2:
        idx, w = x["rows"][0], x["rows"][1]
        return md_table([str(idx["label"])] + [fnum(v) for v in idx["values"]] + ["來源"], [[str(w["label"])] + [fnum(v) for v in w["values"]] + [x.get("anchor", "")]])
    return md_table(["項目"] + [f"c{i+1}" for i in range(len(x["rows"][0]["values"]))] + ["來源"], [[r["label"]] + [fnum(v) for v in r["values"]] + [x.get("anchor", "")] for r in x["rows"]])


def blk_scalars(x: dict, dv, sheet: str) -> list[str]:
    return md_table(["項目", "值", "來源"], [[x.get("label") or x.get("title") or "值", fnum(x["value"]), x.get("anchor", "")]])


# ------------------------------------------------------------------ 輪帶（兩種模式）

def strips_section(groups: list[dict], dv, src_note: str) -> list[str]:
    """groups = [{"name", "reels": [[sym…]…], "src"}] → 「## 輪帶 Strip（附錄）」：每組顆數表 + ```strip 帶面。"""
    if not groups:
        return []
    L = ["## 輪帶 Strip（附錄）", "", f"> {src_note}；顆數由帶面逐格計數，帶面每軸一行、由上而下。", ""]
    for g in groups:
        reels = g["reels"]
        syms: list[str] = []
        for r in reels:
            for s in r:
                if s not in syms:
                    syms.append(s)
        syms = sorted(syms, key=lambda s: (0 if s.startswith("M") else 1 if s in ("WW", "WILD") else 2 if s.startswith("SC") else 3 if s.startswith("SS") else 4, s))
        head = ["組", "軸", "長度"] + syms
        rows = []
        for ri, r in enumerate(reels):
            cnt = {s: 0 for s in syms}
            for s in r:
                cnt[s] += 1
            rows.append([g["name"], f"R{ri + 1}", dv(str(len(r)), f"len({g['name']} R{ri + 1})")] + [dv(str(cnt[s]), f"count({g['name']} R{ri + 1}, {s})") for s in syms])
        L += [f"### {g['name']}", ""] + md_table(head, rows)
        L += ["```strip", f"# {g['name']}"] + [f"R{ri + 1}: " + " ".join(str(s) for s in r) for ri, r in enumerate(reels)] + ["```", ""]
    return L


# ------------------------------------------------------------------ qt 模式（rtp-report v1：0–1 小數）

def qt_summary(rep: dict, targets: dict, dv) -> list[str]:
    g = rep.get("games") or {}
    alias = rep.get("game_aliases") or {}
    main = g.get("MainGame") or g.get(alias.get("MainGame", ""), {}) or {}
    free = g.get("SpecialGameTotal") or g.get(alias.get("SpecialGameTotal", ""), {}) or {}
    items = []
    if rep.get("rtp_total") is not None:
        items.append(("總 RTP", dv(pct_text(rep["rtp_total"], True), "rtp-report.rtp_total × 100"), "rtp-report.json"))
    if main.get("rtp") is not None:
        items.append(("主遊戲 RTP", dv(pct_text(main["rtp"], True), "games.MainGame.rtp × 100"), "rtp-report.json"))
    if free.get("rtp") is not None:
        items.append(("免費遊戲 RTP", dv(pct_text(free["rtp"], True), "games.SpecialGameTotal.rtp × 100"), "rtp-report.json"))
    if main.get("hitrate") is not None:
        items.append(("主遊戲命中率", dv(pct_text(main["hitrate"], True), "games.MainGame.hitrate × 100"), "rtp-report.json"))
    if main.get("maxmulti") is not None:
        items.append(("主遊戲最大倍數", dv(fnum(main["maxmulti"]), "games.MainGame.maxmulti"), "rtp-report.json"))
    if free.get("freq"):
        items.append(("FG 觸發率", dv(pct_text(1.0 / free["freq"], True), "1 / games.SpecialGameTotal.freq × 100"), "rtp-report.json"))
        items.append(("FG 平均觸發局數", dv(fnum(free["freq"]), "games.SpecialGameTotal.freq"), "rtp-report.json"))
    if free.get("multi") is not None:
        items.append(("FG 平均倍率", dv(fnum(free["multi"]), "games.SpecialGameTotal.multi"), "rtp-report.json"))
    if free.get("maxmulti") is not None:
        items.append(("FG 最大倍數", dv(fnum(free["maxmulti"]), "games.SpecialGameTotal.maxmulti"), "rtp-report.json"))
    if rep.get("spins"):
        items.append(("總手數", dv(f"{int(rep['spins']):,}", "rtp-report.spins"), "rtp-report.json"))
    if rep.get("generated_at"):
        items.append(("執行時間", str(rep["generated_at"])[:16], "rtp-report.json"))
    if rep.get("version"):
        items.append(("引擎版本", str(rep["version"]), "rtp-report.json"))
    if targets.get("target_rtp") is not None:
        t = targets["target_rtp"]
        items.append(("目標 RTP", dv(pct_text(t, True), "quicktest.target_rtp × 100"), "quicktest.yaml"))
        tol = targets.get("rtp_tolerance", 0.005)
        items.append(("容許誤差", dv(f"{tol * 100:g}", "quicktest.rtp_tolerance × 100") + " pp", "quicktest.yaml"))
        if rep.get("rtp_total") is not None:
            items.append(("誤差", dv(f"{(rep['rtp_total'] - t) * 100:+.3f}", "(rtp_total − target_rtp) × 100") + " pp", "計算"))
    v = (rep.get("gate") or {}).get("verdict")
    if v:
        items.append(("三向 verdict", str(v), "rtp-report.gate"))
    return summary_table(items)


def qt_data_tables(rep: dict, dv) -> list[str]:
    L: list[str] = []
    for key, title in (("symbol_hit_rate", "主遊戲符號命中率"), ("symbol_hit_rtp", "主遊戲符號 RTP 貢獻")):
        dat = rep.get(key)
        if not dat:
            continue
        cols = [c for c in next(iter(dat.values())).keys()]
        head = ["符號"] + [c.upper() if c == "total" else c for c in cols]
        rows = [[k] + [dv(pct_text(v.get(c), True), f"{key}.{k}.{c} × 100") if v.get(c) is not None else "—" for c in cols] for k, v in dat.items()]
        L += [f"### {title}", ""] + md_table(head, rows)
    es = rep.get("engine_summary") or {}
    if es.get("reel_set"):
        rows = [[str(r["set"]), dv(pct_text(r["total"], True), f"engine_summary.reel_set[{r['set']}].total × 100"), dv(pct_text(r["fg"], True), f"engine_summary.reel_set[{r['set']}].fg × 100") if r.get("fg") is not None else "—", dv(f"{r['spins']:,}", f"engine_summary.reel_set[{r['set']}].spins")] for r in es["reel_set"]]
        L += ["### 輪帶組 RTP（實測）", ""] + md_table(["組", "實測 Total RTP", "實測 FG RTP", "實測手數"], rows)
    elif rep.get("reel_set_rtp"):
        rows = [[str(k), dv(pct_text(v, True), f"reel_set_rtp.{k} × 100")] for k, v in rep["reel_set_rtp"].items() if v is not None]
        if rows:
            L += ["### 輪帶組 RTP（實測）", ""] + md_table(["組", "實測 Total RTP"], rows)
    sr = rep.get("special_range") or []
    if sr:
        rows = [[r["range"]] + [dv(pct_text(r["appear"][k], True), f"special_range[{i}].appear.{k} × 100") if r["appear"].get(k) is not None else "—" for k in ("total", "main", "free")] + [dv(pct_text(r["rtp"][k], True), f"special_range[{i}].rtp.{k} × 100") if r["rtp"].get(k) is not None else "—" for k in ("total", "main", "free")] for i, r in enumerate(sr)]
        L += ["### 贏分區間分布", ""] + md_table(["贏分區間（倍）", "出現 Total", "出現 Main", "出現 Free", "RTP Total", "RTP Main", "RTP Free"], rows)
    mu = rep.get("multiple") or []
    if mu:
        rows = [[m["range"], dv(fnum(m["spins_per_hit"]), f"multiple[{i}].spins_per_hit") if m.get("spins_per_hit") is not None else "—", f"≥ {m.get('ge')}", dv(fnum(m["spins_per_hit_ge"]), f"multiple[{i}].spins_per_hit_ge") if m.get("spins_per_hit_ge") is not None else "—"] for i, m in enumerate(mu)]
        L += ["### 倍數出現頻率", ""] + md_table(["贏分區間（倍）", "約每幾局", "累計門檻", "累計約每幾局"], rows)
    a100 = rep.get("asset_100") or []
    if a100:
        L += ["### 100 手資產分布", ""] + md_table(["100 手後剩餘資產", "佔比"], [[a["range"], dv(pct_text(a["pct"], True), f"asset_100[{i}].pct × 100")] for i, a in enumerate(a100)])
    dec = rep.get("decile") or {}
    if dec:
        L += ["### 十分位", ""] + md_table(["分位", "Total", "Main", "Free", "F_Spin"], [[k] + [dv(fnum(v.get(c)), f"decile.{k}.{c}") if v.get(c) is not None else "—" for c in ("total", "main", "free", "fspin")] for k, v in dec.items()])
    if es.get("fg_detail_raw"):
        L += ["### FG 詳細統計（引擎原文）", "", "```text"] + list(es["fg_detail_raw"]) + ["```", ""]
    return L
