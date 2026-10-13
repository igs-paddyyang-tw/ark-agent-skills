#!/usr/bin/env python3
"""ps_mdview — prob-spec.md（Content 軌）→ 文件模型 + 表格分類（View 軌的唯一輸入層，1.4.0）。

md 是唯一來源：不論 md 來自 xlsx（ps_extract → ps_probspec --data）、快測產物（ps_probspec --qt）、或人手照範本寫，
只要表格照契約（references/prob-spec-contract.md §表格契約）的表頭命名，ps_html 就能畫出同一套 View。

模型：
  doc = {"fm": {...frontmatter}, "title": str, "sections": [{"no": "1"|"A"|None, "title", "id", "blocks": [...]}]}
  block kinds：h3 / h4 / p / ul / quote / bold / code{lang,text} / human{id,text} / table{head,rows,caption,kind}
表格分類（classify）只看表頭與第一欄，不看章節：
  summary（指標｜值）/ base（階段｜RTP…）/ symhit（符號｜x2…TOTAL）/ reelset_rtp（組｜…實測 Total RTP）/ range（贏分區間｜出現…）
  multiple（…約每幾局）/ asset（100 手…）/ decile（分位）/ fg_groups（組別｜次數｜佔比）/ kv（項目｜值 / 參數｜值 / 指標｜值）
  reelsets（Index｜R1…｜權重）/ paytable（層級｜符號｜x3…）/ odds（符號｜sym_id…）/ strip_counts（組｜軸｜長度…）
  yesno（…是｜否）/ dual（X 倍數｜X 權重…）/ matrix（組別｜0｜1…｜權重和）/ weights（組別｜權重）/ series（標籤｜數字表頭，≤3 列）/ generic
數值：tonum("1,234") → 1234.0；tonum("12.3%") → 12.3（pct=True）；「—」「待決議」→ None。
"""
from __future__ import annotations

import re

HUMAN_OPEN = re.compile(r"<!--\s*human:([a-z0-9_-]+)\s*-->")
HUMAN_CLOSE = re.compile(r"<!--\s*/human\s*-->")
SEP_RE = re.compile(r"^:?-{2,}:?$")
NUM_RE = re.compile(r"^[+-]?\d[\d,]*(?:\.\d+)?%?$")
PENDING = "待決議"
EMPTY = {"", "—", "-", "–", PENDING, "N/A", "n/a"}


def split_fm(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            return text[4:end], text[end + 5:]
    return "", text


def parse_fm(fm: str) -> dict:
    """極簡 YAML：`k: v` 與兩層 `k:\\n  a: b`；值去引號。足夠讀 prob-spec frontmatter（不引 pyyaml，渲染端零依賴）。"""
    out: dict = {}
    cur: str | None = None
    for ln in fm.splitlines():
        if not ln.strip():
            continue
        if ln.startswith("  ") and cur is not None:
            m = re.match(r"\s+([^:]+):\s*(.*)$", ln)
            if m:
                if not isinstance(out.get(cur), dict):
                    out[cur] = {}
                out[cur][m.group(1).strip()] = _unq(m.group(2))
            continue
        m = re.match(r"([^:]+):\s*(.*)$", ln)
        if m:
            cur = m.group(1).strip()
            v = m.group(2).strip()
            out[cur] = {} if v == "" else ({} if v == "{}" else _unq(v))
    return out


def _unq(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def split_cells(ln: str) -> list[str]:
    s = ln.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    parts, buf = [], ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf += "|"; i += 2; continue
        if ch == "|":
            parts.append(buf.strip()); buf = ""; i += 1; continue
        buf += ch; i += 1
    parts.append(buf.strip())
    return parts


def tonum(s) -> float | None:
    if s is None:
        return None
    t = str(s).strip().replace("**", "")
    if t in EMPTY:
        return None
    t = t.replace(",", "")
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*(%|pp|倍|x|手|顆|局|次)?\s*$", t)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def is_pct(s) -> bool:
    return isinstance(s, str) and s.strip().replace("**", "").endswith("%")


def numeric_col(rows: list[list[str]], i: int, min_frac: float = 0.6) -> bool:
    vals = [r[i] for r in rows if i < len(r) and r[i].strip() not in EMPTY]
    if not vals:
        return False
    return sum(tonum(v) is not None for v in vals) / len(vals) >= min_frac


# ------------------------------------------------------------------ parse

def parse_md(text: str) -> dict:
    fm_txt, body = split_fm(text)
    fm = parse_fm(fm_txt)
    lines = body.splitlines()
    title = next((ln[2:].strip() for ln in lines if ln.startswith("# ")), fm.get("title") or "")
    sections: list[dict] = []
    cur: dict | None = None
    blocks: list[dict] = []
    i = 0
    para: list[str] = []

    def flush_para():
        nonlocal para
        if para:
            blocks.append({"kind": "p", "text": "\n".join(para)})
            para = []

    def new_section(head: str):
        nonlocal cur, blocks
        flush_para()
        if cur is not None:
            cur["blocks"] = blocks
            sections.append(cur)
        m = re.match(r"^(\d+|[A-Z])\.\s*(.*)$", head)
        no, t = (m.group(1), m.group(2)) if m else (None, head)
        cur = {"no": no, "title": t.strip(), "raw_title": head, "blocks": []}
        blocks = []

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# ") and cur is None:
            i += 1; continue
        if ln.startswith("## "):
            new_section(ln[3:].strip()); i += 1; continue
        if cur is None:
            new_section("前言")
        if ln.startswith("```"):
            flush_para()
            lang = ln[3:].strip(); buf = []; i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            blocks.append({"kind": "code", "lang": lang, "text": "\n".join(buf)}); i += 1; continue
        m = HUMAN_OPEN.match(ln.strip())
        if m:
            flush_para()
            hid = m.group(1); buf = []; i += 1
            while i < len(lines) and not HUMAN_CLOSE.match(lines[i].strip()):
                buf.append(lines[i]); i += 1
            blocks.append({"kind": "human", "id": hid, "text": "\n".join(buf).strip("\n")}); i += 1; continue
        if ln.startswith("|"):
            flush_para()
            tl = []
            while i < len(lines) and lines[i].startswith("|"):
                tl.append(lines[i]); i += 1
            rows = [split_cells(x) for x in tl]
            rows = [r for r in rows if not all(SEP_RE.match(c) for c in r)]
            if not rows:
                continue
            head, body_rows = rows[0], rows[1:]
            cap = None
            for b in reversed(blocks):
                if b["kind"] in ("bold", "h4"):
                    cap = b["text"]; break
                if b["kind"] in ("table", "h3", "code", "human"):
                    break
            tbl = {"kind": "table", "head": head, "rows": body_rows, "caption": cap}
            tbl["cls"] = classify(tbl, _last_heading(blocks))
            blocks.append(tbl); continue
        if ln.startswith("### "):
            flush_para(); blocks.append({"kind": "h3", "text": ln[4:].strip()}); i += 1; continue
        if ln.startswith("#### "):
            flush_para(); blocks.append({"kind": "h4", "text": ln[5:].strip()}); i += 1; continue
        if re.match(r"^\s*[-*] ", ln):
            flush_para(); items = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                items.append(re.sub(r"^\s*[-*] ", "", lines[i])); i += 1
            blocks.append({"kind": "ul", "items": items}); continue
        if re.match(r"^\s*\d+\. ", ln):
            flush_para(); items = []
            while i < len(lines) and re.match(r"^\s*\d+\. ", lines[i]):
                items.append(re.sub(r"^\s*\d+\. ", "", lines[i])); i += 1
            blocks.append({"kind": "ol", "items": items}); continue
        if ln.startswith(">"):
            flush_para(); q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i].lstrip("> ").rstrip()); i += 1
            blocks.append({"kind": "quote", "text": "\n".join(q)}); continue
        if re.fullmatch(r"\*\*[^*]+\*\*", ln.strip()):
            flush_para(); blocks.append({"kind": "bold", "text": ln.strip()[2:-2]}); i += 1; continue
        if ln.startswith("<!--"):
            i += 1; continue
        if not ln.strip():
            flush_para(); i += 1; continue
        para.append(ln.rstrip()); i += 1
    flush_para()
    if cur is not None:
        cur["blocks"] = blocks
        sections.append(cur)
    for s in sections:
        s["id"] = _sec_id(s)
    return {"fm": fm, "title": title, "sections": sections}


def _last_heading(blocks: list[dict]) -> str:
    for b in reversed(blocks):
        if b["kind"] in ("h3", "h4", "bold"):
            return b["text"]
    return ""


SEC_IDS = [("規格簡述", "brief"), ("數據資料", "data"), ("流程圖", "flow"), ("參數表", "params"), ("手法對應", "kcards"), ("競品", "kcards"),
           ("隱性規則", "hidden"), ("輪帶", "strips"), ("邊界", "bounds")]


def _sec_id(s: dict) -> str:
    for k, v in SEC_IDS:
        if k in s["title"]:
            return v
    return "s" + re.sub(r"[^a-z0-9]", "", s["title"].lower())[:12] or "sec"


# ------------------------------------------------------------------ classify

def _h(c: str) -> str:
    return c.strip().replace("**", "")


def classify(tbl: dict, heading: str = "") -> str:
    head = [_h(c) for c in tbl["head"]]
    rows = tbl["rows"]
    h0 = head[0] if head else ""
    hl = [h.lower() for h in head]
    hs = set(head)
    n = len(head)
    if h0 in ("指標",) and n >= 2 and head[1] in ("值", "數值"):
        return "summary"
    if h0 in ("階段", "區塊") and n >= 3 and any("RTP" in h for h in head[1:3]):
        return "base"
    if h0 == "符號" and "sym_id" in hs:
        return "odds"
    if h0 in ("符號", "SYMBOL") and sum(bool(re.fullmatch(r"x\d+", h.lower())) for h in head) >= 2 and head[-1].upper() in ("TOTAL", "合計"):
        return "symhit"
    if h0 == "層級" and "符號" in hs and any(re.fullmatch(r"x\d+", h.lower()) for h in head):
        return "paytable"
    if h0 == "組" and "軸" in hs and "長度" in hs:
        return "strip_counts"
    if h0 in ("組", "Index", "組合") and any("實測" in h and "RTP" in h for h in head):
        return "reelset_rtp"
    if h0 in ("Index", "組合") and sum(bool(re.match(r"R\d", h)) for h in head) >= 2 and ("權重" in hs or "Weight" in hs):
        return "reelsets"
    if h0.startswith("贏分區間") and any(h.startswith("出現") for h in head):
        return "range"
    if any("約每幾局" in h for h in head):
        return "multiple"
    if "100" in h0 and "資產" in h0:
        return "asset"
    if h0 == "分位":
        return "decile"
    if h0 == "組別" and "次數" in hs and any("佔比" in h for h in head):
        return "fg_groups"
    if h0 in ("項目", "參數", "欄位") and n >= 2 and head[1] in ("值", "內容", "數值", "設定") and (n == 2 or head[-1] in ("來源", "說明", "單位", "備註")):
        return "kv"
    if "是" in hs and "否" in hs:
        return "yesno"
    if any(head[j].endswith("倍數") and j + 1 < n and head[j + 1].endswith("權重") for j in range(n - 1)):
        return "dual"
    numeric_heads = [h for h in head[1:] if re.fullmatch(r"\d+(\.\d+)?", h)]
    if h0 in ("組別", "") and len(numeric_heads) >= 3 and (any("權重和" in h or "合計" in h or "Σ" in h for h in head) or h0 == "組別"):
        return "matrix"
    if h0 in ("組別", "項目", "") and n >= 2 and head[1] in ("權重", "Weight") and n <= 5:
        return "weights"
    if len(rows) <= 3 and n >= 3 and all(re.fullmatch(r"\d+(\.\d+)?|[^\d]{1,6}", h) for h in head[1:]) \
            and rows and all(sum(tonum(c) is not None for c in r[1:]) >= max(1, (len(r) - 1) * 0.7) for r in rows):
        return "series"
    return "generic"


def table_dict(tbl: dict) -> dict:
    """kv / summary 表 → {key: (value, source)}。"""
    out = {}
    for r in tbl["rows"]:
        if not r:
            continue
        k = _h(r[0])
        v = _h(r[1]) if len(r) > 1 else ""
        src = _h(r[2]) if len(r) > 2 else ""
        out[k] = (v, src)
    return out


def find_tables(doc: dict, cls: str, section: str | None = None) -> list[dict]:
    out = []
    for s in doc["sections"]:
        if section and s["id"] != section:
            continue
        out += [b for b in s["blocks"] if b["kind"] == "table" and b.get("cls") == cls]
    return out


def section(doc: dict, sid: str) -> dict | None:
    return next((s for s in doc["sections"] if s["id"] == sid), None)


def human_blocks(doc: dict) -> dict:
    out = {}
    for s in doc["sections"]:
        for b in s["blocks"]:
            if b["kind"] == "human":
                out[b["id"]] = b["text"]
    return out


# ------------------------------------------------------------------ 快測摘要 → KPI

SUMMARY_KEYS = {  # 摘要表「指標」→ 內部鍵（兩種寫法都認）
    "總 RTP": "rtp_total", "總RTP": "rtp_total", "Total RTP": "rtp_total", "主遊戲 RTP": "rtp_main", "免費遊戲 RTP": "rtp_free", "特色遊戲 RTP": "rtp_free",
    "FG 觸發率": "fg_rate", "特色觸發率": "fg_rate", "FG 平均觸發局數": "fg_freq", "平均觸發局數": "fg_freq", "FG 平均倍率": "fg_avg", "FG 最大倍數": "fg_max",
    "主遊戲最大倍數": "mg_max", "主遊戲命中率": "mg_hit", "主遊戲 Hit %": "mg_hit", "總手數": "spins", "執行時間": "timestamp", "引擎版本": "version",
    "旗標": "flag", "golden RTP": "golden", "golden": "golden", "目標 RTP": "target", "誤差": "delta", "容許誤差": "tol", "verdict": "verdict", "三向 verdict": "verdict",
    "總最大倍數": "max_all", "耗時": "seconds", "速度": "speed", "總押注": "total_bet", "總贏分": "total_win",
}


def summary_of(doc: dict) -> dict:
    """§2 快測摘要表 → {key: {"text", "num", "src"}}；沒有摘要表時從 BASE INFO 表回推（相容 1.2 以前的 md）。"""
    out: dict = {}
    for t in find_tables(doc, "summary"):
        for k, (v, src) in table_dict(t).items():
            key = SUMMARY_KEYS.get(k) or SUMMARY_KEYS.get(k.replace(" ", "")) or k
            out[key] = {"text": v, "num": tonum(v), "src": src}
    if "rtp_total" not in out:
        for t in find_tables(doc, "base"):
            head = [_h(c) for c in t["head"]]
            cols = {h: i for i, h in enumerate(head)}
            for r in t["rows"]:
                name = _h(r[0])
                std = {"主遊戲": "main", "MainGame": "main", "Main": "main", "免費遊戲": "free", "SpecialGameTotal": "free", "Free": "free", "總計": "total", "Total": "total"}.get(name)
                if not std:
                    continue
                g = lambda col: (_h(r[cols[col]]) if col in cols and cols[col] < len(r) else "")  # noqa: E731
                rtp = g("RTP")
                if std == "total" and rtp:
                    out.setdefault("rtp_total", {"text": rtp, "num": tonum(rtp), "src": "BASE INFO"})
                if std == "main":
                    out.setdefault("rtp_main", {"text": rtp, "num": tonum(rtp), "src": "BASE INFO"})
                    hit = g("Hit %") or g("Trigger %")
                    if hit:
                        out.setdefault("mg_hit", {"text": hit, "num": tonum(hit), "src": "BASE INFO"})
                    mx = g("最大倍率") or g("MaxMulti")
                    if mx:
                        out.setdefault("mg_max", {"text": mx, "num": tonum(mx), "src": "BASE INFO"})
                if std == "free":
                    out.setdefault("rtp_free", {"text": rtp, "num": tonum(rtp), "src": "BASE INFO"})
                    tr = g("觸發率") or g("Trigger %")
                    fq = g("平均觸發局數") or g("Freq（每幾手）") or g("Freq")
                    av = g("平均倍率") or g("Multi")
                    mx = g("最大倍率") or g("MaxMulti")
                    for key, val in (("fg_rate", tr), ("fg_freq", fq), ("fg_avg", av), ("fg_max", mx)):
                        if val:
                            out.setdefault(key, {"text": val, "num": tonum(val), "src": "BASE INFO"})
    return out


def strip_fences(doc: dict) -> list[dict]:
    """```strip 區塊：第一行可為「# 名稱」，其後 `R1: M1 M2 …` 每軸一行 → [{"name", "reels": [[sym…]…]}]。"""
    out = []
    for s in doc["sections"]:
        for b in s["blocks"]:
            if b["kind"] != "code" or b["lang"] != "strip":
                continue
            name, reels = None, []
            for ln in b["text"].splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith("#"):
                    name = ln.lstrip("# ").strip(); continue
                m = re.match(r"^(R?\d+)\s*[:：]\s*(.*)$", ln)
                if m:
                    reels.append(m.group(2).split())
            if reels:
                out.append({"name": name or f"strip-{len(out)+1}", "reels": reels, "section": s["id"]})
    return out
