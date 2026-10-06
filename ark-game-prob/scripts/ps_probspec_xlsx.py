#!/usr/bin/env python3
"""ps_probspec_xlsx — Content 軌（xlsx 模式）：`prob-data.json`（ps_extract 產）→ `prob-spec.md` + `prob-spec.meta.json`。

與 ps_probspec 的 qt 模式同一套六段契約與人工區規則；差別只在來源：
  qt 模式  = odds.json + rtp-report.json + gdd-pack + decisions（新遊戲設計，value 可為 null）
  xlsx 模式 = 機率人員的公版機率表（已上線／還原場景，數值為定案值）
由 ps_probspec.py --data 轉呼叫；也可單獨執行。deterministic、不呼叫 LLM。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402

HUMAN_RE = re.compile(r"<!--\s*human:([a-z0-9_-]+)\s*-->\n?(.*?)<!--\s*/human\s*-->", re.S)
PENDING = "待決議"


def fnum(v) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v.is_integer():
            return f"{int(v):,}"
        return repr(v)  # 與 prob-data.json 的 JSON 文字逐字一致，PS-NUM 才回溯得到
    if isinstance(v, int):
        return f"{v:,}"
    return str(v).replace("\n", " / ")


def md_table(head: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return out + [""]


def build(data: dict, out_dir: pathlib.Path, *, slug: str, author: str, date: str, xlsx_path: pathlib.Path | None, extra_sources: dict[str, pathlib.Path]) -> dict:
    K, rep, run = data.get("known") or {}, data.get("report") or {}, (data.get("report") or {}).get("run") or {}
    game = data.get("game") or slug
    md_p = out_dir / "prob-spec.md"
    human: dict[str, str] = {}
    if md_p.exists():
        for m in HUMAN_RE.finditer(md_p.read_text(encoding="utf-8")):
            human[m.group(1)] = m.group(2).rstrip("\n")
    derived: list[dict] = []

    def dv(val, frm: str) -> str:
        derived.append({"value": str(val).replace(",", "").rstrip("%").lstrip("+"), "from": frm})
        return str(val)

    def hblock(hid: str, default: str) -> list[str]:
        return [f"<!-- human:{hid} -->", human.get(hid, default), "<!-- /human -->", ""]

    anchor_sheet = (data.get("params") or {}).get("sheet", "參數表")
    L: list[str] = []

    # ---------------- 1. 規格簡述
    L += ["## 1. 規格簡述", ""]
    board = K.get("board") or {}
    if board:
        L += ["### 基本規格", ""] + md_table(["項目", "值", "來源"], [[k, fnum(v), f"{anchor_sheet} 基本資訊"] for k, v in board.items()])
    pt = K.get("paytable") or []
    if pt:
        ks = list(pt[0]["odds"].keys())
        L += ["### Pay table（odds × Line bet）", ""] + md_table(["層級", "符號"] + [f"x{k}" for k in ks] + ["來源"], [[r["tier"], r["sym"]] + [fnum(r["odds"].get(k)) for k in ks] + [f"{anchor_sheet} Odds表"] for r in pt])
    brief = data.get("brief") or []
    if brief:
        L += ["### xlsx「規格簡述」分頁（原文）", ""]
        for row in brief:
            L.append("- **SPEC** " + " ｜ ".join(c.replace("\n", " / ") for c in row))
        L.append("")
    L += ["### 機率人員簡述", ""] + hblock("summary", f"（請以 2–4 句描述 {game} 的主遊戲與特色觸發方式；此區重產保留）")

    # ---------------- 2. 數據資料
    L += ["## 2. 數據資料", ""]
    base = rep.get("base") or {}
    if base:
        rows = []
        for name, zh in (("Main", "主遊戲"), ("Free", "免費遊戲"), ("Feature", "Feature"), ("GRAND", "GRAND"), ("Total", "總計")):
            v = base.get(name)
            if not v:
                continue
            cells = list(v) + [""] * (7 - len(v))
            rows.append([zh] + [dv(x, f"數據資料 BASE INFO {name}") if x not in ("-", "") else "—" for x in cells[:7]])
        L += ["### 快測基本資訊（BASE INFO）", ""] + md_table(["階段", "RTP", "Freq（每幾手）", "Trigger %", "平均倍率", "PlayTimes", "RetriRate", "最大倍率"], rows)
        if run:
            bits = []
            if run.get("total"):
                bits.append(f"總手數 {dv(f'{run['total']:,}', '數據資料 Total')}")
            if run.get("timestamp"):
                bits.append(f"執行時間 {run['timestamp'][:16]}")
            if run.get("flag"):
                bits.append(f"旗標 {run['flag']}")
            if run.get("seconds"):
                bits.append(f"耗時 {dv(run['seconds'], '數據資料 Done in')} s")
            L += ["- 快測執行：" + "；".join(bits), ""]
        rs = K.get("reelsets") or {}
        golden = (rs.get("totals") or {}).get("TOTAL RTP")
        tot = (rep.get("summary") or {}).get("rtp_total")
        if golden is not None and tot is not None:
            g = golden * 100 if golden < 5 else golden
            L += [f"- golden（{anchor_sheet} {rs.get('block')} 加權 TOTAL RTP）：{dv(f'{g:.2f}', 'reelsets.totals.TOTAL RTP × 100')}%；實測總 RTP {dv(f'{tot:.4f}', '數據資料 總計')}%；誤差 {dv(f'{tot - g:+.3f}', 'rtp_total − golden')} pp（容許 ± {dv('0.2', '容許誤差常數 pp')} pp）。**RTP 是模擬結果不是輸入**（P-000）。", ""]
        fg = rep.get("fg_detail") or {}
        if fg.get("groups"):
            L += ["### FG 強中弱實測分佈", ""] + md_table(["組別", "次數", "佔比", "FG RTP 貢獻"], [[g["name"], dv(f"{g['count']:,}", "數據資料 FG內部"), dv(f"{g['pct']:.2f}", "數據資料 FG內部") + "%", (dv(f"{dict(fg.get('group_rtp') or {}).get(g['name'], '—')}", "數據資料 各組別RTP貢獻") + "%") if fg.get("group_rtp") else "—"] for g in fg["groups"]])
        L += ["> 完整快測輸出見 View 軌（prob-spec.html §2）與 prob-data.json `raw_log`；本節只列守門用數字。", ""]
    else:
        L += ["> **未快測**：xlsx 無「數據資料」分頁或無法解析。跑快測後把報表貼回 xlsx 數據資料分頁，重跑 ps_extract → ps_probspec。", ""]
        L += md_table(["階段", "RTP", "Freq", "Trigger %", "平均倍率", "最大倍率"], [["主遊戲"] + ["—"] * 5, ["免費遊戲"] + ["—"] * 5, ["總計"] + ["—"] * 5])

    # ---------------- 3. 機率流程圖
    L += ["## 3. 機率流程圖", ""]
    blocks = [b for b in (data.get("params") or {}).get("blocks", []) if re.match(r"^[A-Z]-", b["id"])]
    m_ids = [b["id"] for b in blocks if b["id"].startswith("M")]
    f_ids = [b["id"] for b in blocks if b["id"].startswith("F")]
    L += ["```mermaid", "flowchart TD",
          f"    A[主遊戲 Spin{'：表 ' + m_ids[0] if m_ids else ''}] --> B{{特色觸發條件?}}",
          "    B -->|否| C[主遊戲結算" + (f"：表 {' / '.join(m_ids[1:3])}" if len(m_ids) > 1 else "") + "]",
          "    B -->|是| D[進入特色遊戲" + (f"：表 {f_ids[0]}" if f_ids else "") + "]",
          "    D --> E[特色遊戲進行" + (f"：表 {' / '.join(f_ids[1:4])}" if len(f_ids) > 1 else "") + "]",
          "    E --> F[結算]", "    C --> G[回主遊戲]", "    F --> G", "```", "",
          "> 骨架由參數表的表編號自動帶出；分支條件與演出層請在下方「流程補充」補齊（重產保留）。", ""]
    L += ["### 流程補充", ""] + hblock("flow-notes", "（可在此放完整 mermaid 或逐步說明；每個節點標對應的表編號）")

    # ---------------- 4. 參數表
    L += ["## 4. 參數表", "", "> 每一列的「來源」= xlsx 座標（分頁!儲存格）。數值為定案值（source: xlsx，pending_params 0）。", ""]
    for b in (data.get("params") or {}).get("blocks", []):
        title = f"### 表 {b['id']}" if re.match(r"^[A-Z]-", b["id"]) else f"### {b['id']}"
        if b.get("title"):
            title += f"　{b['title']}"
        L += [title, ""]
        for t in b["tables"]:
            rows = t["rows"]
            if not rows:
                continue
            width = max(len(r["cells"]) for r in rows)
            # 單格文字 → 小標；否則整張表 + 來源欄
            flat = [v for r in rows for v in r["cells"] if v is not None]
            if len(rows) == 1 and len(flat) == 1 and isinstance(flat[0], str):
                L += [f"**{flat[0]}**", ""]
                continue
            head = [f"c{i+1}" for i in range(width)]
            first = rows[0]["cells"]
            if sum(1 for v in first if isinstance(v, str)) >= 2 or (len(rows) > 1 and any(isinstance(v, str) for v in first) and not any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in first)):
                head = [("" if v is None else str(v)) for v in first] + [""] * (width - len(first))
                body = rows[1:]
            else:
                body = rows
            from openpyxl.utils import get_column_letter  # type: ignore
            md_rows = []
            for r in body:
                cells = [fnum(v) if v is not None else "" for v in r["cells"]] + [""] * (width - len(r["cells"]))
                md_rows.append(cells + [f"{anchor_sheet}!{get_column_letter(t['c0'])}{r['r']}"])
            L += md_table([h or " " for h in head] + ["來源"], md_rows)
    L += ["### 參數備註", ""] + hblock("param-notes", "（參數語意、旋鈕用途、與設定檔鍵名對照；重產保留）")

    # ---------------- 5. 競品資料／手法對應
    L += ["## 5. 競品資料／手法對應", ""]
    mech = [[f"表 {b['id']}", b.get("title") or "", "", ""] for b in blocks]
    default5 = "\n".join(md_table(["機制（參數表）", "說明", "對應手法卡", "收錄目的"], mech)) if mech else "（列出機制 → K 卡對照）"
    L += hblock("competitor", default5)

    # ---------------- 6. 隱性規則
    L += ["## 6. 隱性規則", ""]
    hid = data.get("hidden") or []
    if hid:
        L += ["### xlsx「隱性規則」分頁", ""]
        for row in hid:
            L.append("- **SPEC** " + " ｜ ".join(c.replace("\n", " / ") for c in row))
        L.append("")
    L += hblock("hidden-rules", "\n".join(md_table(["規則", "設計目的", "對應表 / K 卡", "更改需同步"], [["（例）復活為演出層攔截，不改 RTP", "製造起死回生張力", "表 F-4 / K-021", "編導規格書"]])))

    # ---------------- 邊界聲明
    L += ["## 邊界聲明", "",
          f"- 來源：`{data['source']['name']}`（sha256:{data['source']['sha256_16']}）；本檔由 ark-game-prob ps_extract → ps_probspec 程式化轉出，數字未經手抄。",
          "- 人工區（`<!-- human:… -->`）由機率人員撰寫；重產時原文保留；人工區內的數字不受 PS-NUM 保護，請自行標來源。",
          "- xlsx「規格簡述」「隱性規則」分頁若為樣板殘留，請回填 xlsx 後重產；本檔不替人判斷。", ""]

    body_md = "\n".join(L)
    verdict = "未快測"
    if base:
        if golden is None or tot is None:
            verdict = "inconclusive"
        else:
            verdict = "confirmed" if abs(tot - (golden * 100 if golden < 5 else golden)) <= 0.2 else "rejected"
    fm = ["---", f"title: {game} 機率規格書", "contract: \"1\"", "kind: prob-spec", f"slug: {slug}", f"game: {game}", "mode: xlsx",
          f"status: {'review' if base else 'draft'}", "distribution: internal", f"date: {date}", f"author: {author}", "source_skill: ark-game-prob",
          f"verdict: {verdict}", "pending_params: 0", "sources:"]
    sources: dict[str, dict] = {}
    if xlsx_path and xlsx_path.exists():
        sources["xlsx"] = {"path": xlsx_path.as_posix(), "sha256_16": C.sha16(xlsx_path)}
    for k, p in extra_sources.items():
        if p and p.exists():
            sources[k] = {"path": p.as_posix(), "sha256_16": C.sha16(p)}
    for k, s in sources.items():
        fm.append(f"  {k}: {s['path']}")
    fm.append("---")
    text = "\n".join(fm) + "\n\n" + f"# {game} 機率規格書（Content 軌）\n\n" + body_md
    C.atomic_write(md_p, text)
    meta = {"contract": "1", "kind": "prob-spec", "mode": "xlsx", "slug": slug, "game": game,
            "sections": ["1. 規格簡述", "2. 數據資料", "3. 機率流程圖", "4. 參數表", "5. 競品資料／手法對應", "6. 隱性規則"],
            "pending_params": 0, "verdict": verdict, "sources": sources, "derived": derived, "md_sha256_16": C.sha16(md_p), "generated": dt.datetime.now().isoformat(timespec="seconds")}
    C.atomic_write(out_dir / "prob-spec.meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def run_from_args(a) -> None:
    dp = pathlib.Path(a.data)
    if not dp.exists():
        C.fail("BAD_INPUT", f"找不到 {dp}", "先跑 ps_extract.py")
    data = json.loads(dp.read_text(encoding="utf-8"))
    slug = a.slug or data.get("slug") or dp.parent.name
    out_dir = pathlib.Path(a.out) / slug if pathlib.Path(a.out).name != slug else pathlib.Path(a.out)
    xlsx = pathlib.Path(a.xlsx) if a.xlsx else pathlib.Path(data["source"]["path"])
    meta = build(data, out_dir, slug=slug, author=a.author, date=a.date, xlsx_path=xlsx if xlsx.exists() else None, extra_sources={"prob-data": dp})
    C.emit({"out": str(out_dir / "prob-spec.md"), "verdict": meta["verdict"], "derived": len(meta["derived"]), "human_blocks": 5,
            "delivery": f"prob-spec 已落盤 {out_dir / 'prob-spec.md'}｜6 段｜xlsx 模式｜數據：{meta['verdict']}｜派生值 {len(meta['derived'])}"}, {"stage": "ps_probspec", "mode": "xlsx"})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="prob-data.json（ps_extract 產）")
    ap.add_argument("--out", default="data/prob")
    ap.add_argument("--slug")
    ap.add_argument("--xlsx", help="來源 xlsx（預設取 prob-data.source.path）")
    ap.add_argument("--author", default=os.getenv("ARK_AUTHOR", "paddyyang"))
    ap.add_argument("--date", default=dt.date.today().isoformat())
    run_from_args(ap.parse_args())
