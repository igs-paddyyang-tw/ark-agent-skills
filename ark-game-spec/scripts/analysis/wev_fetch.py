#!/usr/bin/env python3
"""wev_fetch — 把一個 Web 來源（官網/賠付表/規則頁）轉成一筆 type:"web" evidence，append 到 evidence.jsonl。

定位：補「影片拍不到、但官方文件白紙黑字」的欄位。web evidence 走 ga_analyze 既有的
「非 visual → 最高只能撐 INFERRED」路徑，不繞過守門紅線、不謊報成 OBSERVED。

deterministic：不呼叫 LLM。抓正文 → 存 <run>/web/<Wid>.txt → 算 sha256 → regex 粗抽數字
→ 段落/清單切節錄 → append 一筆 web evidence。外部正文一律當「資料」不當指令。

用法:
  python wev_fetch.py --run artifacts/cva/<run_id> --url <URL> --title "官方賠付表" [--note "..."]
  python wev_fetch.py --run <run> --urls-file <run>/web/sources.txt   # 一行一 URL（可 "URL | 標題"）
  python wev_fetch.py --run <run> --text-file page.txt --url <URL> --title "..."  # 已有正文檔，跳過抓取

exit: 0 OK / 2 BAD_INPUT / 5 CONN_FAILED
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html as _html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import os  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # skill root（_lib）
from _lib import run_common as C

UA = "Mozilla/5.0 (compatible; ark-game-analysis/wev_fetch)"
_TAG_DROP = re.compile(r"(?is)<(script|style|noscript|template|svg)\b.*?</\1>")
_TAG = re.compile(r"(?is)<[^>]+>")
_WS = re.compile(r"[ \t\x0b\f\r]+")
_MULTI_NL = re.compile(r"\n{3,}")
_NUM = re.compile(r"(?<![\w.])(\d{1,4})(?![\w.])")


def _fetch(url: str, timeout: int = 30) -> str:
    if not re.match(r"^https?://", url):
        C.fail("BAD_INPUT", f"URL 需以 http(s):// 開頭：{url}", "檢查 --url")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL 由使用者提供)
            raw = r.read()
            enc = r.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        C.fail("CONN_FAILED", f"抓取失敗：{url}", str(e))
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def html_to_text(doc: str) -> str:
    """極簡 HTML→純文字：去 script/style，塊級標籤換行，剝標籤，反轉義，壓空白。"""
    doc = _TAG_DROP.sub(" ", doc)
    doc = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|section|article|br)\s*>", "\n", doc)
    doc = re.sub(r"(?i)<br\s*/?>", "\n", doc)
    doc = re.sub(r"(?i)<li\b[^>]*>", "\n- ", doc)
    text = _TAG.sub("", doc)
    text = _html.unescape(text)
    text = _WS.sub(" ", text)
    text = "\n".join(ln.strip() for ln in text.splitlines())
    text = _MULTI_NL.sub("\n\n", text).strip()
    return text


def excerpt(text: str, max_items: int = 14, max_len: int = 200) -> list[str]:
    """把正文切成節錄（去空行、去過短雜訊、限長）——deterministic，不做語意判斷。"""
    out, seen = [], set()
    for ln in text.splitlines():
        ln = ln.strip(" -•·\t")
        if len(ln) < 6 or ln in seen:
            continue
        seen.add(ln)
        out.append(ln[:max_len])
        if len(out) >= max_items:
            break
    return out


def numbers_from(lines: list[str], max_nums: int = 12) -> list[dict]:
    """粗抽數字（label 用該行前綴當線索）；label 由 ga_analyze / 人事後判讀，此處只保留原文脈絡。"""
    nums = []
    for ln in lines:
        for m in _NUM.finditer(ln):
            nums.append({"label": ln[:40], "value": int(m.group(1))})
            if len(nums) >= max_nums:
                return nums
    return nums


def next_web_id(evidence: list[dict]) -> str:
    n = 0
    for e in evidence:
        eid = str(e.get("evidence_id", ""))
        if eid.startswith("W") and eid[1:].isdigit():
            n = max(n, int(eid[1:]))
    return f"W{n + 1:03d}"


def build_evidence(eid: str, url: str, title: str, text: str, note: str) -> dict:
    obs = excerpt(text)
    return {
        "evidence_id": eid,
        "type": "web",
        "extractor": "web_fetch",
        "source_url": url,
        "source_title": title,
        "fetched_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "t_start": "web",
        "t_end": "web",
        "t_sec": None,
        "frame": None,
        "sheet": None,
        "trust": {"timestamp": "deterministic", "observation": "web-extracted"},
        "observation": obs,
        "numbers": numbers_from(obs),
        "confidence": "high",
        "extra": {"note": note or f"節錄自 {title or url}；正文全文見 web/{eid}.txt", "chars": len(text)},
    }


def _sources(a) -> list[tuple[str, str]]:
    if a.urls_file:
        p = Path(a.urls_file)
        if not p.exists():
            C.fail("BAD_INPUT", f"找不到 {p}", "檢查 --urls-file")
        items = []
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            if "|" in ln:
                u, t = ln.split("|", 1)
                items.append((u.strip(), t.strip()))
            else:
                items.append((ln, ""))
        return items
    if a.url:
        return [(a.url, a.title or "")]
    C.fail("BAD_INPUT", "需提供 --url 或 --urls-file", "至少一個來源")
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="fetch web source → append type:web evidence")
    ap.add_argument("--run", required=True)
    ap.add_argument("--url")
    ap.add_argument("--title", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--urls-file")
    ap.add_argument("--text-file", help="已有純文字正文檔，跳過網路抓取（需同時給 --url 當來源標註）")
    ap.add_argument("--timeout", type=int, default=30)
    a = ap.parse_args()

    run = C.run_dir(a.run)
    web_dir = run / "web"
    web_dir.mkdir(exist_ok=True)
    ev_path = run / "evidence.jsonl"
    evidence = C.load_evidence(run)

    added = []
    with C.Timer() as t:
        if a.text_file:
            if not a.url:
                C.fail("BAD_INPUT", "--text-file 需同時給 --url 標註來源", "")
            text = html_to_text(Path(a.text_file).read_text(encoding="utf-8"))
            sources = [(a.url, a.title or "")]
            texts = {a.url: text}
        else:
            sources = _sources(a)
            texts = {u: html_to_text(_fetch(u, a.timeout)) for u, _ in sources}

        with ev_path.open("a", encoding="utf-8") as fh:
            for url, title in sources:
                eid = next_web_id(evidence)
                text = texts[url]
                (web_dir / f"{eid}.txt").write_text(text, encoding="utf-8")
                rec = build_evidence(eid, url, title, text, a.note)
                evidence.append(rec)  # 讓同批次的下一筆算對 next id
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                added.append({"evidence_id": eid, "url": url, "chars": len(text),
                              "obs": len(rec["observation"]), "numbers": len(rec["numbers"])})

    C.emit({"added": added, "count": len(added), "evidence_jsonl": str(ev_path),
            "next": f"重跑 ga_analyze：python ga_analyze.py --run {run} --force"},
           {"stage": "wev_fetch", "elapsed_ms": t.elapsed_ms})
    return 0


if __name__ == "__main__":
    sys.exit(main())
