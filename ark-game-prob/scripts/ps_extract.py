#!/usr/bin/env python3
"""ps_extract — 公版「機率表 xlsx」→ `prob-data.json`（Content 軌的機器可讀中繼層）。

讀機率人員的公版機率表（分頁：機率規格書製作方針 / 規格簡述 / 數據資料 / 機率流程圖 / 參數表 /
Main·Free Game Strip / 轉置 Strip / 隱性規則），deterministic 轉成一份 JSON，之後 ps_probspec（Content 軌 md）、
ps_html（View 軌）、ps_diff（對照快測設定檔）都只吃這份 JSON，不再各自碰 xlsx。

- 參數表：以「表 X-n」標籤為錨的區塊解析（generic），每個區塊內連續非空列切成一張張表；再用 recognizer
  辨識常見表（表M-1 輪帶組、表F-1 強中弱、權重表、SC/SS 雙欄表、是/否表、組別×次數矩陣）。
- 數據資料：FastTest 家族快測輸出（BASE INFO / Symbol Hit / Reel Set RTP / 100手 / Multiple / SpecialGame Range /
  Decile / RTP 分項 / FG 詳細統計）逐段解析；缺段略過；全文保留於 raw_log。
- Strip 分頁：每個 `Reels_g` / `假轉` 區塊的五輪帶面與右側「總顆數」表。
- 每個數字都附來源座標（sheet!cell），供 ps_lint PS-NUM 與 meta.derived 回溯。

用法: python ps_extract.py --xlsx <機率表.xlsx> --out data/prob/<slug> [--slug <slug>] [--game <名>]
交付格式：prob-data 已落盤 <out>/prob-data.json｜參數區塊 N｜數據段 M｜輪帶組 K
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402

warnings.filterwarnings("ignore")
DATA_CONTRACT = "1"
SHEETS = {
    "guide": ["機率規格書製作方針", "製作方針"],
    "brief": ["規格簡述"],
    "data": ["數據資料", "數據", "快測結果"],
    "flow": ["機率流程圖", "流程圖"],
    "params": ["參數表", "參數"],
    "main_strip": ["Main Game Strip", "MainGameStrip", "主遊戲輪帶"],
    "free_strip": ["Free Game Strip", "免費遊戲輪帶"],
    "fake_strip": ["Free Fake Strip"],
    "transpose": ["轉置 Strip", "轉置"],
    "hidden": ["隱性規則"],
    "notes": ["機率表注意事項"],
}
LABEL_RE = re.compile(r"^\s*表\s*([A-Za-z]{1,3})\s*-?\s*([\dA-Za-z\-]*)")
TOP_LABELS = {"基本資訊", "Odds表", "Odds 表", "Pay table"}
NUM_LINE_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _s(v) -> str:
    return "" if v is None else str(v).replace("\xa0", " ").strip()


def _isnum(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _cellref(ws_title: str, r: int, c: int) -> str:
    from openpyxl.utils import get_column_letter
    return f"{ws_title}!{get_column_letter(c)}{r}"


# ---------------------------------------------------------------- 參數表（generic blocks）
def parse_params(ws) -> dict:
    """掃描整張參數表：標籤列 → 區塊；區塊內連續非空列 → 表。"""
    maxr, maxc = ws.max_row, ws.max_column
    rows = []
    for r in range(1, maxr + 1):
        vals = [ws.cell(r, c).value for c in range(1, maxc + 1)]
        rows.append(vals)

    def is_label(vals):
        for c, v in enumerate(vals[:3], 1):
            s = _s(v)
            if not s:
                continue
            m = LABEL_RE.match(s)
            if m:
                return f"{m.group(1).upper()}-{m.group(2)}".rstrip("-"), c, s[m.end():].strip(" \u3000:：")
            if s in TOP_LABELS:
                return s, c, ""
            return None
        return None

    blocks = []
    cur = None
    for r, vals in enumerate(rows, 1):
        lab = is_label(vals)
        if lab:
            bid, c, inline_title = lab
            # 標題：標籤格剩餘文字，否則同列標籤之後第一個非空字串
            title = inline_title or next((_s(v) for v in vals[c:] if _s(v)), "")
            cur = {"id": bid, "title": title, "anchor": _cellref(ws.title, r, c), "rows": []}
            blocks.append(cur)
            # 標籤列本身若還有表格內容（如 基本資訊 | 盤面 | 3x5）也納入
            rest = vals[c:]
            if sum(1 for v in rest if v is not None) >= 2:
                cur["rows"].append((r, vals))
            continue
        if cur is not None:
            cur["rows"].append((r, vals))

    def split_tables(block_rows):
        tables, buf = [], []
        for r, vals in block_rows:
            nonempty = [i for i, v in enumerate(vals) if v is not None and _s(v) != ""]
            if not nonempty:
                if buf:
                    tables.append(buf); buf = []
                continue
            buf.append((r, vals, nonempty))
        if buf:
            tables.append(buf)
        out = []
        for buf in tables:
            c0 = min(min(ne) for _, _, ne in buf)
            c1 = max(max(ne) for _, _, ne in buf)
            grid = []
            for r, vals, _ in buf:
                grid.append({"r": r, "cells": [vals[i] for i in range(c0, c1 + 1)]})
            out.append({"c0": c0 + 1, "rows": grid})
        return out

    for b in blocks:
        b["tables"] = split_tables(b["rows"])
        del b["rows"]
    return {"sheet": ws.title, "blocks": blocks}


# ---------------------------------------------------------------- recognizers（辨識常見公版表）
HEADER_WORDS = {"權重", "Weight", "倍數", "機率", "%", "Total", "權重和"}


def _header_row(tbl):
    """找表頭：跳過只有一格文字的 caption 列；表頭 = 第一列有 ≥2 個字串、或 1 個表頭字 + 數字欄、或 1 個表頭字且下一列有數字。
    回傳 (head, body, captions)。"""
    rows = tbl["rows"]
    caps = []
    for i, row in enumerate(rows):
        cells = row["cells"]
        strs = [v for v in cells if isinstance(v, str)]
        nums = [v for v in cells if _isnum(v)]
        nxt_has_num = i + 1 < len(rows) and any(_isnum(v) for v in rows[i + 1]["cells"])
        if len(strs) >= 2 or (len(strs) == 1 and nums and strs[0] in HEADER_WORDS) or (len(strs) == 1 and not nums and strs[0] in HEADER_WORDS and nxt_has_num):
            # 下一列是更完整的純文字表頭（如 SC|SS 之後的 圖騰倍數|Weight|…）→ 本列當 caption
            if i + 1 < len(rows) and not nums:
                n_cells = rows[i + 1]["cells"]
                n_strs = [v for v in n_cells if isinstance(v, str)]
                if len(n_strs) > len(strs) and not any(_isnum(v) for v in n_cells):
                    caps.extend(_s(v) for v in strs); continue
            return [(_s(v) if v is not None else "") for v in cells], rows[i + 1:], caps
        if len(strs) == 1 and not nums:
            caps.append(_s(strs[0])); continue
        return None, rows, caps
    return None, rows, caps


def recognize(params: dict) -> dict:
    """從 generic blocks 抓出常見結構；抓不到的留 None。"""
    K: dict = {"board": {}, "paytable": [], "reelsets": None, "weights": [], "dual": [], "yesno": [], "matrix": [], "scalars": []}
    for b in params["blocks"]:
        bid, title = b["id"], b["title"]
        for t in b["tables"]:
            head, body, caps = _header_row(t)
            # 基本資訊：k/v 列
            if bid == "基本資訊":
                for row in t["rows"]:
                    cells = [v for v in row["cells"] if v is not None]
                    if len(cells) >= 2 and isinstance(cells[-2], str):
                        K["board"][_s(cells[-2])] = cells[-1]
                continue
            # Pay table：Symbol | 3 | 4 | 5
            if bid in ("Odds表", "Odds 表", "Pay table") and head and any(h in ("Symbol", "符號") for h in head):
                si = next(i for i, h in enumerate(head) if h in ("Symbol", "符號"))
                ks = [i for i, h in enumerate(head) if re.fullmatch(r"\d+", h)]
                tier = ""
                for row in body:
                    c = row["cells"]
                    if si > 0 and isinstance(c[si - 1], str):
                        tier = _s(c[si - 1])
                    if isinstance(c[si], str):
                        K["paytable"].append({"tier": tier, "sym": c[si], "odds": {head[i]: c[i] for i in ks}})
                continue
            # 表M-1 輪帶組：Index | R1..Rn | Weight | 說明 | TOTAL RTP | FG RTP
            if head and "Index" in head and any(h.lower() == "weight" for h in head):
                ii = head.index("Index"); wi = next(i for i, h in enumerate(head) if h.lower() == "weight")
                ri = [i for i, h in enumerate(head) if re.fullmatch(r"R\d+", h)]
                extra = {h: i for i, h in enumerate(head) if h and i not in (ii, wi) and i not in ri}
                sets = []
                for row in body:
                    c = row["cells"]
                    if not _isnum(c[ii]):
                        continue
                    sets.append({"idx": int(c[ii]), "flags": [c[i] for i in ri], "weight": c[wi],
                                 "extra": {h: c[i] for h, i in extra.items() if i < len(c) and c[i] is not None}, "row": row["r"]})
                # 合計列：Weight 欄為空但 RTP 欄有值
                tot = {}
                for row in body:
                    c = row["cells"]
                    if _isnum(c[ii]):
                        continue
                    for h, i in extra.items():
                        if i < len(c) and _isnum(c[i]):
                            tot[h] = c[i]
                    if _isnum(c[wi]):
                        tot["weight_sum"] = c[wi]
                for t2 in b["tables"]:
                    flat2 = [v for row in t2["rows"] for v in row["cells"] if v is not None]
                    if len(flat2) == 1 and _isnum(flat2[0]):
                        tot.setdefault("weight_sum", flat2[0])
                K["reelsets"] = {"block": bid, "title": title, "sets": sets, "totals": tot, "anchor": b["anchor"]}
                continue
            # SC/SS 雙欄：圖騰倍數 | Weight | … | 圖騰倍數 | Weight
            if head and head.count("Weight") >= 2:
                wis = [i for i, h in enumerate(head) if h == "Weight"]
                cols = []
                for wi in wis:
                    vi = wi - 1
                    pairs, total, extra = [], None, {}
                    for row in body:
                        v, w = row["cells"][vi], row["cells"][wi]
                        if w is None or not _isnum(w):
                            continue
                        if v is None:
                            total = w
                        elif isinstance(v, str) and not re.fullmatch(r"\*\d+|\d+(\.\d+)?", v.strip()):
                            extra[_s(v)] = w
                        else:
                            pairs.append((v, w))
                    cols.append({"col": wi, "pairs": pairs, "total": total, "extra": extra})
                # 欄名：往上一列找 SC/SS 這類字樣（在 block 其他表裡），退而用順序
                K["dual"].append({"block": bid, "title": title, "names": caps, "columns": cols, "anchor": b["anchor"]})
                continue
            # 組別 × 數字欄 矩陣（表F-2 類）：表頭第一欄 組別、其餘多為數字
            if head and head[0] in ("組別",) and sum(1 for h in head[1:] if re.fullmatch(r"\d+(\.\d+)?", h)) >= 3:
                groups = []
                for row in body:
                    c = row["cells"]
                    if isinstance(c[0], str) and c[0] not in ("機率 Prob.",):
                        groups.append({"name": _s(c[0]), "values": c[1:]})
                    if isinstance(c[0], str) and c[0].startswith("機率"):
                        break
                K["matrix"].append({"block": bid, "title": title, "head": head[1:], "groups": groups, "caption": (caps[-1] if caps else _caption_before(b, t)), "anchor": b["anchor"]})
                continue
            # 是/否 表：表頭含 是 否
            if head and "是" in head and "否" in head:
                yi, ni = head.index("是"), head.index("否")
                rows_ = [{"name": _s(row["cells"][0]) if row["cells"][0] is not None else "", "yes": row["cells"][yi], "no": row["cells"][ni]} for row in body]
                K["yesno"].append({"block": bid, "title": title, "rows": rows_, "anchor": b["anchor"]})
                continue
            # 權重表：表頭含 權重 / Weight（單欄）
            if head and any(h in ("權重", "Weight") for h in head):
                wi = next(i for i, h in enumerate(head) if h in ("權重", "Weight"))
                li = 0 if wi != 0 else None
                items = []
                for row in body:
                    c = row["cells"]
                    if _isnum(c[wi]) or (isinstance(c[wi], str) and c[wi] in ("*2", "*3", "*4")):
                        items.append({"label": _s(c[li]) if li is not None and c[li] is not None else "", "weight": c[wi], "rest": [v for i, v in enumerate(c) if i not in (li, wi) and v is not None]})
                if items:
                    K["weights"].append({"block": bid, "title": title, "head": head, "items": items, "anchor": b["anchor"]})
                continue
            # 橫向序列：每列 = 標籤 + 一串數字（表F-3-1 出場順序、表F-4-3 保留龍數）
            body_rows = body if head else t["rows"]
            is_series = len(body_rows) >= 1 and all(sum(1 for v in row["cells"] if _isnum(v)) >= 2 and any(isinstance(v, str) for v in row["cells"]) for row in body_rows) and (head or sum(1 for v in t["rows"][0]["cells"] if _isnum(v)) >= 3)
            if is_series and not (head and any(h in ("權重", "Weight") for h in head)):
                ser = []
                for row in body_rows:
                    c = row["cells"]
                    lab = next((_s(v) for v in c if isinstance(v, str)), "")
                    ser.append({"label": lab, "values": [v for v in c if _isnum(v)]})
                K.setdefault("series", []).append({"block": bid, "title": title, "head": head, "rows": ser, "anchor": b["anchor"]})
                continue
            # 權重／倍數 橫向鍵值（如 保留金龍 0..11 / 權重 …）或單值（表F-4-1 Weight 300、表F-5 200）
            flat = [v for row in t["rows"] for v in row["cells"] if v is not None]
            nums = [v for v in flat if _isnum(v)]
            if len(nums) == 1 and bid not in ("基本資訊",) and not (K["reelsets"] and K["reelsets"]["block"] == bid):
                K["scalars"].append({"block": bid, "title": title, "value": nums[0], "label": next((_s(v) for v in flat if isinstance(v, str)), ""), "anchor": b["anchor"]})
    return K


def _caption_before(block, tbl) -> str:
    """矩陣表的小標（上一張只有一格字串的表）。"""
    tabs = block["tables"]
    i = tabs.index(tbl)
    if i > 0:
        prev = tabs[i - 1]
        cells = [v for row in prev["rows"] for v in row["cells"] if v is not None]
        if len(cells) == 1 and isinstance(cells[0], str):
            return _s(cells[0])
    return ""


# ---------------------------------------------------------------- 數據資料（FastTest 報告）
def parse_fasttest(lines: list[str]) -> dict:
    """逐段解析；每段獨立 try，缺段略過。回傳 report dict（百分比保留原數值，單位 %）。"""
    R: dict = {}
    L = [ln.rstrip("\n") for ln in lines]

    def find(prefix, start=0):
        for i in range(start, len(L)):
            if L[i].strip().startswith(prefix):
                return i
        return -1

    def nums(s):
        return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s.replace(",", ""))]

    def pct(s):
        return [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?)%", s)]

    # run info
    run = {}
    for ln in L:
        m = re.search(r"Workers: (\d+), Rounds/Worker: (\d+), Total: (\d+)", ln)
        if m:
            run.update(workers=int(m[1]), rounds_per_worker=int(m[2]), total=int(m[3]))
        m = re.search(r"Done in ([\d.]+) sec", ln)
        if m:
            run["seconds"] = float(m[1])
        m = re.search(r"版本: ([\w.]+) =+ ([\d-]+ [\d:.]+)", ln)
        if m:
            run["version"], run["timestamp"] = m[1], m[2]
        m = re.search(r"Times:(\d+)\s+TotalWin:(\d+)\s+TotalBet:(\d+)", ln)
        if m:
            run.update(times=int(m[1]), total_win=int(m[2]), total_bet=int(m[3]))
        if ln.strip().startswith("速度:"):
            run["speed"] = ln.split(":", 1)[1].strip()
    first = next((ln.strip() for ln in L if ln.strip()), "")
    if first and not first.startswith("Workers"):
        run["flag"] = first
    R["run"] = run

    i = find("********** BASE INFO")
    if i >= 0:
        base = {}
        for ln in L[i + 2:i + 12]:
            t = ln.strip().split()
            if not t:
                continue
            if t[0] in ("Main", "Free") and len(t) > 1 and t[1] == "Fea":
                name, vals = t[0] + " Fea", t[2:]
            elif t[0].startswith("---"):
                continue
            else:
                name, vals = t[0], t[1:]
            if name == "Total":
                base[name] = vals
                break
            base[name] = vals
        R["base"] = base

    def symtab(anchor):
        j = find(anchor)
        if j < 0:
            return None
        out = {}
        for ln in L[j + 2:j + 40]:
            t = ln.split()
            if not t:
                break
            if t[0] == "TOTAL":
                out["TOTAL"] = [float(x.rstrip("%")) for x in t[1:]]
                break
            out[t[0]] = [float(x.rstrip("%")) for x in t[1:]]
        return out
    R["symbol_hit_rate"] = symtab("********* Main Symbol Hit Rate")
    R["symbol_hit_rtp"] = symtab("********* Main Symbol Hit RTP")

    i = find("===== ReelSet RTP")
    if i >= 0:
        rs = []
        for ln in L[i + 2:i + 40]:
            t = ln.split()
            if len(t) < 3 or not t[0].isdigit():
                break
            rs.append({"set": int(t[0]), "spins": int(t[1]), "total": float(t[2].rstrip("%")), "fg": float(t[3].rstrip("%")) if len(t) > 3 else None})
        R["reel_set_rtp"] = rs
    elif find("********* Reel Set RTP") >= 0:
        i = find("********* Reel Set RTP"); rs = []
        for ln in L[i + 1:i + 40]:
            m = re.match(r"\s*SET\s+(\d+):\s+([\d.]+)%", ln)
            if not m:
                break
            rs.append({"set": int(m[1]), "spins": None, "total": float(m[2]), "fg": None})
        R["reel_set_rtp"] = rs

    i = find("********** 100手資產")
    if i >= 0:
        a = []
        for ln in L[i + 1:i + 10]:
            if "%" not in ln:
                break
            label = re.sub(r"\s+", " ", ln[:ln.index("%")].strip().rsplit(" ", 1)[0]).strip()
            a.append({"range": label, "pct": pct(ln)[0]})
        R["asset_100"] = a

    i = find("********** Multiple Information")
    if i >= 0:
        mult = []
        for ln in L[i + 1:i + 40]:
            m = re.match(r"\s*(.+?) - 約\s+([\d.]+)局觸發\(\s*(\d+)倍以上 - 約\s+([\d.]+)局觸發", ln)
            if not m:
                if mult:
                    break
                continue
            mult.append({"range": re.sub(r"\s+", " ", m[1]).strip(), "spins_per_hit": float(m[2]), "ge": int(m[3]), "spins_per_hit_ge": float(m[4])})
        R["multiple"] = mult

    i = find("********** SpecialGame Range")
    if i >= 0:
        rng = []
        for ln in L[i + 3:i + 40]:
            if " - " not in ln or ln.strip().startswith("*"):
                break
            label, rest = ln.split(" - ", 1)
            p = pct(rest)
            if len(p) < 6:
                break
            tail = nums(rest.split("|")[-1])
            rng.append({"range": re.sub(r"\s+", " ", label).strip(), "appear": p[0:3], "rtp": p[3:6], "fg_avg_spin": tail[0] if tail else None})
        R["special_range"] = rng

    i = find("********** Decile Table")
    if i >= 0:
        dec = []
        for ln in L[i + 2:i + 20]:
            t = ln.strip().split(" - ")
            if len(t) < 2:
                break
            dec.append({"label": t[0].strip(), "vals": t[1].split()})
        R["decile"] = dec

    def after(prefix):
        j = find(prefix)
        return L[j].split(":", 1)[1].strip() if j >= 0 and ":" in L[j] else None
    summ = {}
    for key, pre in (("fg_trigger", "FG觸發率"), ("fg_avg", "FG平均倍率"), ("mg_max", "MG最大倍數"), ("fg_max", "FG最大倍數"), ("total_max", "總最大倍數")):
        v = after(pre)
        if v is not None:
            summ[key] = v
    for key, pre in (("rtp_main", "主遊戲"), ("rtp_free", "免費遊戲"), ("rtp_total", "總計")):
        j = find("===== RTP 分項")
        if j >= 0:
            for ln in L[j + 1:j + 8]:
                if ln.strip().startswith(pre) and "%" in ln:
                    summ[key] = float(ln.split()[-1].rstrip("%"))
    R["summary"] = summ

    # FG 詳細統計（彌勒佛型引擎輸出；全部選配）
    fg: dict = {}
    i = find("-- 觸發面 --")
    if i >= 0:
        n = nums(L[i + 1]); fg["trigger_total"] = int(n[0]) if n else None
        dist = []; j = i + 2
        while j < len(L) and "SC+SS=" in L[j]:
            n = nums(L[j]); dist.append({"k": int(n[0]), "count": int(n[1]), "pct": n[2]}); j += 1
        fg["trigger_dist"] = dist
        if j < len(L) and "有SS觸發" in L[j]:
            n = nums(L[j]); fg["with_ss"] = {"count": int(n[0]), "pct": n[1], "no_count": int(n[2]), "no_pct": n[3]}
        if j + 1 < len(L) and "SS抽到乘倍" in L[j + 1]:
            n = nums(L[j + 1]); fg["ss_mult"] = {"count": int(n[0]), "pct": n[1], "value_count": int(n[2]), "value_pct": n[3]}
    i = find("-- 初始基底 --")
    if i >= 0:
        fg["base_avg"] = nums(L[i + 1])[0]
        n = nums(L[i + 2]); fg["all888"] = {"count": int(n[-2]), "pct": n[-1]} if len(n) >= 2 else None
        fg["all888_avg"] = nums(L[i + 3])[-1] if i + 3 < len(L) else None
    i = find("-- FG內部 --")
    if i >= 0:
        grp = []
        for ln in L[i + 1:i + 5]:
            n = nums(ln); grp.append({"name": ln.split(":")[0].strip(), "count": int(n[0]), "pct": n[1]})
        fg["groups"] = grp
        fg["avg_times"] = {}
        for ln in L[i + 5:i + 20]:
            if "平均" in ln and "次數" in ln:
                fg["avg_times"][ln.split(":")[0].strip().replace("平均", "").replace("次數", "")] = nums(ln)[0]
            elif "平均總乘倍" in ln:
                fg["avg_mult"] = nums(ln)[0]
            elif "平均金幣贏分" in ln:
                fg["avg_coin_win"] = nums(ln)[0]
            elif "平均鯉魚贏分" in ln:
                fg["avg_fish_win"] = nums(ln)[0]
            elif ln.strip().startswith("--"):
                break
    i = find("-- 結算面 --")
    if i >= 0:
        fg["settle_avg"] = nums(L[i + 1])[0]; fg["settle_max"] = nums(L[i + 2])[0]
        n = nums(L[i + 3]); fg["sd"], fg["cv"] = (n[0], n[1]) if len(n) >= 2 else (None, None)
    i = find("-- FG贏分佔比拆解 --")
    if i >= 0:
        fg["contrib"] = [(L[j].split(":")[0].strip().replace("貢獻", ""), nums(L[j])[0]) for j in range(i + 1, i + 5) if ":" in L[j]]
    i = find("-- 各組別RTP貢獻 --")
    if i >= 0:
        fg["group_rtp"] = [(L[j].split(":")[0].strip(), nums(L[j])[0]) for j in range(i + 1, i + 5) if ":" in L[j]]
    i = find("-- 各組別詳細 --")
    if i >= 0:
        fg["group_detail_cols"] = L[i + 1].split()
        fg["group_detail"] = [L[j].split() for j in range(i + 2, i + 6) if L[j].strip()]
    i = find("-- 各進場SC顆數均倍 --")
    if i >= 0:
        sc = []
        for ln in L[i + 2:i + 30]:
            t = ln.split()
            if len(t) != 4 or not t[0].isdigit():
                break
            sc.append({"sc": int(t[0]), "count": int(t[1]), "pct": float(t[2].rstrip("%")), "avg": float(t[3])})
        fg["sc_enter"] = sc
    i = find("-- 最後乘倍十分位")
    if i >= 0:
        fg["mult_note"] = L[i].strip("- ").strip()
        fg["mult_samples"] = nums(L[i + 1])
        fg["mult_decile"] = [(L[j].split()[0], L[j].split()[1]) for j in range(i + 3, i + 13) if len(L[j].split()) >= 2]
    i = find("-- 依進場特殊SC(SS)顆數")
    if i >= 0:
        fg["ss_cols"] = L[i + 1].split()
        rows_, extra, j = [], [], i + 2
        while j < len(L) and L[j].strip():
            t = L[j].split()
            if len(t) == len(fg["ss_cols"]):
                rows_.append(t)
            j += 1
        for k in range(j + 1, len(L)):
            t = L[k].split()
            if len(t) == len(fg["ss_cols"]):
                extra.append(t)
        fg["ss_rows"], fg["ss_rows_extra"] = rows_, extra
    if fg:
        R["fg_detail"] = fg
    R["sections_found"] = [k for k in ("base", "symbol_hit_rate", "symbol_hit_rtp", "reel_set_rtp", "asset_100", "multiple", "special_range", "decile", "fg_detail") if R.get(k)]
    return R


# ---------------------------------------------------------------- Strip 分頁
def parse_strips(ws) -> dict:
    strips = {}
    for hr in range(1, min(ws.max_row, 6) + 1):
        hdr = [ws.cell(hr, c).value for c in range(1, ws.max_column + 1)]
        starts = [(c, _s(v)) for c, v in enumerate(hdr, 1) if _s(v) and (_s(v).lower().startswith("ree") or _s(v) == "假轉")]
        if not starts:
            continue
        for c, name in starts:
            name = re.sub(r"(?i)^ree1s_", "Reels_", name)
            reels = []
            for k in range(1, 6):
                col = c + k
                if col > ws.max_column or _s(ws.cell(hr, col).value) != f"R{k}":
                    break
                s, r = [], hr + 1
                while r <= ws.max_row:
                    x = ws.cell(r, col).value
                    if x in (None, ""):
                        break
                    s.append(_s(x)); r += 1
                reels.append(s)
            n = len(reels)
            counts = []
            # 右側「總顆數」表：找同列往右第一個 '總顆數'
            cc = None
            for c2 in range(c + n + 1, min(ws.max_column, c + n + 4) + 1):
                if _s(ws.cell(hr, c2).value) == "總顆數":
                    cc = c2; break
            if cc:
                for r in range(hr + 1, hr + 16):
                    lab = ws.cell(r, cc).value
                    if lab is None:
                        continue
                    counts.append([_s(lab)] + [ws.cell(r, cc + k).value for k in range(1, n + 1)])
                    if _s(lab) == "Total":
                        break
            if any(reels):
                strips[name] = {"reels": reels, "counts": counts, "anchor": _cellref(ws.title, hr, c)}
        break
    return strips


# ---------------------------------------------------------------- 文字分頁
def sheet_lines(ws, cols=(1, 2, 3, 4)) -> list[list[str]]:
    out = []
    for r in range(1, ws.max_row + 1):
        vals = [_s(ws.cell(r, c).value) for c in range(1, ws.max_column + 1)]
        if any(vals):
            out.append([v for v in vals if v])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--out", required=True, help="data/prob/<slug>")
    ap.add_argument("--slug")
    ap.add_argument("--game")
    ap.add_argument("--data-sheet", help="覆寫數據資料分頁名")
    ap.add_argument("--params-sheet", help="覆寫參數表分頁名")
    a = ap.parse_args()
    try:
        import openpyxl  # type: ignore
    except ImportError:
        C.fail("MISSING_DEP", "需要 openpyxl（pip install openpyxl）")
    xp = pathlib.Path(a.xlsx)
    if not xp.exists():
        C.fail("BAD_INPUT", f"找不到 {xp}")
    wb = openpyxl.load_workbook(xp, data_only=True)
    names = wb.sheetnames

    def pick(key, override=None):
        if override and override in names:
            return wb[override]
        for cand in SHEETS[key]:
            for n in names:
                if n.strip().lower() == cand.lower():
                    return wb[n]
        return None

    out = pathlib.Path(a.out)
    slug = a.slug or out.name
    D: dict = {"contract": DATA_CONTRACT, "kind": "prob-data", "slug": slug, "game": a.game or xp.stem.split("機率表")[0].split("_")[0] or slug,
               "source": {"path": str(xp), "name": xp.name, "sha256_16": C.sha16(xp)}, "generated": dt.datetime.now().isoformat(timespec="seconds"),
               "sheets": [{"name": ws.title, "hidden": ws.sheet_state != "visible", "dims": ws.dimensions} for ws in wb.worksheets]}
    ws = pick("params", a.params_sheet)
    if ws is None:
        C.fail("BAD_INPUT", f"找不到參數表分頁（候選 {SHEETS['params']}；實際 {names}）", "用 --params-sheet 指定")
    D["params"] = parse_params(ws)
    D["known"] = recognize(D["params"])
    ws = pick("data", a.data_sheet)
    if ws is not None:
        lines = []
        for r in range(1, ws.max_row + 1):
            v = next((ws.cell(r, c).value for c in range(1, min(ws.max_column, 4) + 1) if ws.cell(r, c).value not in (None, "")), None)
            lines.append("" if v is None else str(v))
        while lines and not lines[-1]:
            lines.pop()
        D["raw_log"] = "\n".join(lines)
        D["report"] = parse_fasttest(lines)
    else:
        D["raw_log"], D["report"] = "", {}
    D["strips"] = {}
    for key in ("main_strip", "free_strip", "fake_strip"):
        ws = pick(key)
        if ws is not None:
            got = parse_strips(ws)
            if got:
                D["strips"][key] = got
    for key in ("guide", "brief", "hidden", "notes"):
        ws = pick(key)
        D[key] = sheet_lines(ws) if ws is not None else []
    out.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out / "prob-data.json", json.dumps(D, ensure_ascii=False, indent=1, default=str))
    nb = len(D["params"]["blocks"]); ns = len(D["report"].get("sections_found", [])); nk = sum(len(v) for v in D["strips"].values())
    C.emit({"out": str(out / "prob-data.json"), "blocks": nb, "report_sections": ns, "strip_groups": nk,
            "known": {k: (len(v) if isinstance(v, list) else bool(v)) for k, v in D["known"].items()},
            "delivery": f"prob-data 已落盤 {out / 'prob-data.json'}｜參數區塊 {nb}｜數據段 {ns}｜輪帶組 {nk}"}, {"stage": "ps_extract"})


if __name__ == "__main__":
    main()
