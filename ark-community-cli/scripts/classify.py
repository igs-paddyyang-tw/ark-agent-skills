"""classify.py — records/ → classify/{date}.jsonl（feedback_type、sentiment、cluster）+ classify/llm-queue.jsonl。

    python classify.py --config community/config.yaml [--since 7d] [--week 2026-W39]

三層：規則詞庫分類（頻道 feedback_hint 當先驅）→ 規則情感（裝了 oseti 自動用）→ 同類內 3-gram Jaccard 連通分群。
規則分不出的進 llm-queue，LLM 只跑那批。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Ctx, read_jsonl, write_jsonl, parse_since, week_range  # noqa: E402
from normalize import norm_text, ngrams, jaccard  # noqa: E402

try:
    import oseti  # type: ignore
    _OSETI = oseti.Analyzer()
except Exception:  # noqa: BLE001
    _OSETI = None


def hits(text: str, words: dict) -> int:
    t = text.lower()
    return sum(1 for lang_words in words.values() for w in lang_words if str(w).lower() in t)


def classify_type(text: str, lex: dict, hint: str | None) -> tuple[str, dict]:
    scores = {k: hits(text, v) for k, v in lex["feedback_type"].items()}
    if hint and hint in scores:
        scores[hint] += 1
    best = max(scores.values()) if scores else 0
    top = [k for k, v in scores.items() if v == best and v > 0]
    if len(top) == 1:
        return top[0], scores
    if len(top) > 1 and hint in top:
        return hint, scores
    return "uncategorized", scores


def sentiment(text: str, lex: dict, lang: str) -> tuple[str, float]:
    if _OSETI and lang == "ja":
        try:
            s = _OSETI.analyze(text)
            v = sum(s) / len(s) if s else 0.0
            return ("pos" if v > 0.1 else "neg" if v < -0.1 else "neu"), round(v, 3)
        except Exception:  # noqa: BLE001
            pass
    sl = lex["sentiment"]
    pos, neg = hits(text, sl["pos"]), hits(text, sl["neg"])
    if any(str(n) in text for lw in sl.get("negators", {}).values() for n in lw) and pos > neg:
        pos, neg = neg, pos  # 極簡否定翻轉
    v = (pos - neg) / max(1, pos + neg)
    return ("pos" if v > 0 else "neg" if v < 0 else "neu"), round(v, 3)


def cluster(records: list[dict], thr: float) -> dict[str, list[dict]]:
    """同 feedback_type 內連通分群；回傳 cluster_id → members。"""
    by_type: dict[str, list] = defaultdict(list)
    for r in records:
        if r.get("duplicate_of"):
            continue
        by_type[r["feedback_type"]].append(r)
    out: dict[str, list[dict]] = {}
    cid = 0
    for ft, rs in by_type.items():
        grams = [ngrams(norm_text(r["text"])) for r in rs]
        parent = list(range(len(rs)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                if jaccard(grams[i], grams[j]) >= thr:
                    parent[find(i)] = find(j)
        groups: dict[int, list] = defaultdict(list)
        for i, r in enumerate(rs):
            groups[find(i)].append(r)
        for g in sorted(groups.values(), key=len, reverse=True):
            cid += 1
            key = f"C{cid:04d}"
            for r in g:
                r["cluster_id"] = key
            out[key] = g
    return out


def score(r: dict) -> int:
    m = r.get("metrics", {})
    return m.get("reactions", 0) + m.get("like", 0) + 2 * m.get("reply", 0) + m.get("repost", 0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--since")
    ap.add_argument("--week", help="只處理該 ISO 週")
    a = ap.parse_args(argv)
    ctx = Ctx(Path(a.config))
    lex = ctx.lexicon()
    ccfg = ctx.cfg.get("classify", {})
    hints = {c.get("name"): c.get("feedback_hint") for c in ctx.cfg.get("discord", {}).get("channels", [])}

    lo = hi = None
    if a.week:
        lo, hi = week_range(a.week)
    elif a.since:
        lo = parse_since(a.since)
    recs = []
    for f in sorted(ctx.path("records").glob("*.jsonl")):
        for _, r in read_jsonl(f):
            ts = r["ts"]
            if lo and ts < lo.isoformat():
                continue
            if hi and ts >= hi.isoformat():
                continue
            recs.append(r)
    if not recs:
        print("classify: 沒有 records 可處理")
        return 0

    for r in recs:
        ch_hint = hints.get((r.get("channel") or "").split("/")[0])
        r["feedback_type"], r["type_scores"] = classify_type(r["text"], lex, ch_hint)
        r["sentiment"], r["sentiment_score"] = sentiment(r["text"], lex, r["lang"])
    clusters = cluster(recs, float(ccfg.get("cluster_jaccard", 0.35)))
    for key, members in clusters.items():
        rep = max(members, key=score)
        for m in members:
            m["cluster_size"] = len(members)
            m["cluster_authors"] = len({x["author_key"] for x in members})
            m["cluster_rep"] = rep["record_id"]

    by_day: dict[str, list] = defaultdict(list)
    for r in recs:
        by_day[r["ts"][:10]].append(r)
    for day, rs in by_day.items():
        write_jsonl(ctx.path("classify", f"{day}.jsonl"), sorted(rs, key=lambda r: r["ts"]))

    queue = [r for r in recs if r["feedback_type"] == "uncategorized" and not r.get("duplicate_of")]
    mixed = {c for c, ms in clusters.items() if len(ms) >= 3 and len({m["feedback_type"] for m in ms}) > 1}
    queue += [r for r in recs if r.get("cluster_id") in mixed and r not in queue]
    write_jsonl(ctx.path("classify", "llm-queue.jsonl"),
                [{"record_id": r["record_id"], "text": r["text"], "lang": r["lang"], "source": r["source"],
                  "reason": "uncategorized" if r["feedback_type"] == "uncategorized" else "mixed-cluster",
                  "prompt_hint": "只回 JSON {feedback_type, sentiment, confidence}；feedback_type 限 player-voice schema 九類"} for r in queue])

    c = Counter(r["feedback_type"] for r in recs if not r.get("duplicate_of"))
    unc = c.get("uncategorized", 0) / max(1, sum(c.values()))
    print(f"classify: {len(recs)} records / {len(clusters)} clusters / uncategorized {unc:.0%} / llm-queue {len(queue)} / oseti {'on' if _OSETI else 'off'}")
    print("  " + ", ".join(f"{k}:{v}" for k, v in c.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
