"""loop.py — 與知識庫閉環的兩個子命令。

    python loop.py handoff --config community/config.yaml --week 2026-W39
        → reports/weekly/{week}-handoff.json：本週可 ingest 檔案清單（路徑、target、tags、trust、provenance），
          附 PII 掃描結果。worker 沒有 wiki_ingest，此清單交 leader 執行。

    python loop.py compare --config community/config.yaml --decision D-2026-09-22-01 [--decisions-dir knowledge/hoyeah/player-voice/decisions]
        → reports/decisions/{id}-followup.md：決策日前後各 7 天，based_on 痛點的頻次 / distinct_authors / 情感，
          並以 deterministic 規則判定是否達成 expect。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Ctx, read_jsonl, pii_scan, today, iso_week  # noqa: E402
from normalize import norm_text, ngrams, jaccard  # noqa: E402


def fm(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    try:
        import yaml  # type: ignore
        return yaml.safe_load(m.group(1)) or {}
    except Exception:  # noqa: BLE001
        return {}


def handoff(ctx: Ctx, week: str) -> int:
    items, pii = [], []
    digest = ctx.path("reports", "weekly", f"{week}-community-digest.md")
    if not digest.exists():
        sys.exit(f"缺 {digest.relative_to(ctx.root)}，先跑 digest")
    d = fm(digest.read_text(encoding="utf-8"))
    items.append({"path": str(digest.relative_to(ctx.root)), "target": "events/", "suggested_tags": d.get("tags", ["player-voice", "weekly"]),
                  "trust": "deterministic", "provenance": "mixed", "status_on_ingest": "seedling", "guard_required": True})
    pii += pii_scan(digest)
    for c in sorted(ctx.path("cases", week).glob("F-*.md")):
        f = fm(c.read_text(encoding="utf-8"))
        items.append({"path": str(c.relative_to(ctx.root)), "target": "pain-points/", "suggested_tags": f.get("tags", []),
                      "trust": f.get("trust", "llm-distilled"), "provenance": f.get("provenance", "mixed"),
                      "status_on_ingest": "seedling", "guard_required": True,
                      "distinct_authors": f.get("distinct_authors"), "feedback_type": f.get("feedback_type")})
        pii += pii_scan(c)
    fu = sorted(ctx.path("reports", "decisions").glob("*-followup.md"))
    for f in fu:
        if f.stat().st_mtime > (datetime.now() - timedelta(days=8)).timestamp():
            items.append({"path": str(f.relative_to(ctx.root)), "target": "decisions/", "suggested_tags": ["player-voice", "decision-followup"],
                          "trust": "deterministic", "provenance": "mixed", "status_on_ingest": "seedling", "guard_required": True})
    out = {"week": week, "generated": today(), "items": items, "pii_scan": "FAIL" if pii else "PASS", "pii_hits": pii[:10],
           "notes": "worker 無 wiki_ingest：清單交 market-leader；每檔先 wiki_guard scan。X 來源 provenance=public-third-party，痛點頁分欄呈現。"}
    p = ctx.path("reports", "weekly", f"{week}-handoff.json")
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"handoff: {p.relative_to(ctx.root)} / {len(items)} 檔 / PII {out['pii_scan']}")
    return 1 if pii else 0


def load_classified(ctx: Ctx, lo: datetime, hi: datetime) -> list[dict]:
    out = []
    for f in sorted(ctx.path("classify").glob("????-??-??.jsonl")):
        for _, r in read_jsonl(f):
            if lo.isoformat() <= r["ts"] < hi.isoformat() and not r.get("duplicate_of"):
                out.append(r)
    return out


def match_cluster(recs: list[dict], seed_grams: list[set], thr: float) -> list[dict]:
    return [r for r in recs if any(jaccard(ngrams(norm_text(r["text"])), g) >= thr for g in seed_grams)]


def compare(ctx: Ctx, decision_id: str, decisions_dir: Path | None) -> int:
    ddir = decisions_dir or ctx.config_path.parent / "knowledge" / "hoyeah" / "player-voice" / "decisions"
    dp = ddir / f"{decision_id}.md"
    if not dp.exists():
        sys.exit(f"找不到 decision：{dp}")
    d = fm(dp.read_text(encoding="utf-8"))
    decided = datetime.fromisoformat(str(d["decided_on"])).replace(tzinfo=timezone.utc)
    based = d.get("based_on") or []
    thr = float(ctx.cfg.get("classify", {}).get("cluster_jaccard", 0.35))

    # 種子：based_on 案件卡的 record_id → 找回文本 3-gram
    seed_ids: set[str] = set()
    for fid in based:
        m = re.match(r"F-(\d{4}-W\d{2})-\d+", fid)
        cp = ctx.path("cases", m.group(1), f"{fid}.md") if m else None
        if cp and cp.exists():
            body = cp.read_text(encoding="utf-8")
            mm = re.search(r"## 全部 record_id\n(.+)", body)
            if mm:
                seed_ids |= {s.strip() for s in mm.group(1).split(",")}
    all_recs = load_classified(ctx, decided - timedelta(days=60), decided + timedelta(days=60))
    seed_grams = [ngrams(norm_text(r["text"])) for r in all_recs if r["record_id"] in seed_ids]
    if not seed_grams:
        sys.exit("based_on 案件找不到 record，無法比對")

    before = match_cluster(load_classified(ctx, decided - timedelta(days=7), decided), seed_grams, thr)
    after = match_cluster(load_classified(ctx, decided, decided + timedelta(days=7)), seed_grams, thr)

    def stats(rs):
        return {"records": len(rs), "authors": len({r["author_key"] for r in rs}), "sent": dict(Counter(r["sentiment"] for r in rs)),
                "neg_ratio": round(sum(r["sentiment"] == "neg" for r in rs) / len(rs), 2) if rs else 0.0}
    b, a_ = stats(before), stats(after)
    drop = 1 - (a_["records"] / b["records"]) if b["records"] else None
    expect = str(d.get("expect", ""))
    target = re.search(r"(\d+)\s*%", expect)
    met = None
    if target and drop is not None:
        met = drop >= int(target.group(1)) / 100 and a_["neg_ratio"] <= b["neg_ratio"]
    verdict = "met" if met else ("not-met" if met is False else "inconclusive")
    ready = decided + timedelta(days=7) <= datetime.now(timezone.utc)

    quotes_after = [f"- （{r['source']}／{r['sentiment']}）{r['text'][:140]}"
                    for r in sorted(after, key=lambda r: -(r['metrics'].get('reactions', 0) + r['metrics'].get('like', 0)))[:3]]
    md = "\n".join([
        "---", "report_type: analysis", f"title: \"決策追蹤 {decision_id}\"", f"date: {today()}", f"decision_id: {decision_id}",
        f"decided_on: {d['decided_on']}", f"based_on: {based}", f"verdict: {verdict if ready else 'pending'}", "severity: P3",
        f"confidence: {'high' if ready and b['records'] >= 10 else 'low'}", "trust: deterministic", "tags: [player-voice, decision-followup]", "---", "",
        f"# 決策追蹤 {decision_id}", "", f"- 決策：{d.get('action', '')}", f"- 預期：{expect}", f"- 觀察窗：前 7 天 vs 後 7 天（{'已完整' if ready else '後 7 天尚未結束，結果暫定'}）", "",
        "| | 前 7 天 | 後 7 天 |", "|---|---|---|",
        f"| 則數 | {b['records']} | {a_['records']} |", f"| distinct_authors | {b['authors']} | {a_['authors']} |",
        f"| neg 比例 | {b['neg_ratio']} | {a_['neg_ratio']} |", f"| 情感分布 | {b['sent']} | {a_['sent']} |", "",
        f"**判定：{verdict if ready else '暫定 ' + verdict + '（觀察窗未滿）'}**" + (f"（頻次下降 {drop:.0%}）" if drop is not None else ""), "",
        "## 後 7 天代表句", *(quotes_after or ["- 無"]), "",
        "> 判定為 deterministic 規則（頻次下降達標且 neg 比例不升）。決策效果由資料說，不由報告宣稱；下週 digest 自動引用。",
    ])
    out = ctx.path("reports", "decisions", f"{decision_id}-followup.md")
    out.write_text(md, encoding="utf-8")
    print(f"compare: {out.relative_to(ctx.root)} / before {b['records']} → after {a_['records']} / {verdict if ready else 'pending'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("handoff"); h.add_argument("--config", required=True); h.add_argument("--week", default=iso_week())
    c = sub.add_parser("compare"); c.add_argument("--config", required=True); c.add_argument("--decision", required=True); c.add_argument("--decisions-dir")
    a = ap.parse_args(argv)
    ctx = Ctx(Path(a.config))
    if a.cmd == "handoff":
        return handoff(ctx, a.week)
    return compare(ctx, a.decision, Path(a.decisions_dir) if a.decisions_dir else None)


if __name__ == "__main__":
    sys.exit(main())
