"""digest.py — classify/ → reports/weekly/{week}-community-digest.md + cases/{week}/F-*.md。

    python digest.py --config community/config.yaml --week 2026-W39

輸出符合 ark-md-report frontmatter 契約（verdict/severity/confidence/trust/sources/tags），
Finding ID 穩定：F-{week}-{n}。只含 author_key / player_key，跑 PII 自掃。
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Ctx, read_jsonl, week_range, pii_scan, today  # noqa: E402


def load_week(ctx: Ctx, week: str) -> list[dict]:
    lo, hi = week_range(week)
    out = []
    for f in sorted(ctx.path("classify").glob("????-??-??.jsonl")):
        for _, r in read_jsonl(f):
            if lo.isoformat() <= r["ts"] < hi.isoformat():
                out.append(r)
    return out


def prev_week(week: str) -> str:
    lo, _ = week_range(week)
    d = lo - timedelta(days=1)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def q(text: str, n: int) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def build(ctx: Ctx, week: str) -> tuple[str, dict[str, str], str]:
    recs = load_week(ctx, week)
    if not recs:
        sys.exit(f"digest: {week} 沒有 classify 資料（先跑 classify --week {week}）")
    live = [r for r in recs if not r.get("duplicate_of")]
    dcfg = ctx.cfg.get("digest", {})
    thr = ctx.cfg.get("classify", {}).get("verdict_thresholds", {"act": 10, "watch": 5})
    qmax, qchars = int(dcfg.get("quote_max", 3)), int(dcfg.get("quote_chars", 140))

    by_src = defaultdict(list)
    for r in live:
        by_src[r["source"]].append(r)
    clusters: dict[str, list] = defaultdict(list)
    for r in live:
        if r.get("cluster_id"):
            clusters[r["cluster_id"]].append(r)
    ranked = sorted(clusters.values(), key=lambda ms: (len({m["author_key"] for m in ms}), len(ms)), reverse=True)

    # verdict
    verdict = "ok"
    for ms in ranked:
        authors = len({m["author_key"] for m in ms})
        neg = sum(m["sentiment"] == "neg" for m in ms) / len(ms)
        if neg >= 0.5 and authors >= thr["act"]:
            verdict = "act"
            break
        if neg >= 0.5 and authors >= thr["watch"]:
            verdict = "watch"
    severity = {"act": "P1", "watch": "P2", "ok": "P3"}[verdict]

    # 上週比較
    prev = {r["cluster_rep"]: r for r in load_week(ctx, prev_week(week)) if r.get("cluster_rep")}
    prev_sizes = Counter(r["cluster_id"] for r in prev.values())

    findings = []
    cases: dict[str, str] = {}
    for i, ms in enumerate(ranked[:5], 1):
        fid = f"F-{week}-{i}"
        rep = next(m for m in ms if m["record_id"] == m["cluster_rep"])
        authors = len({m["author_key"] for m in ms})
        players = len({m["player_key"] for m in ms if m.get("player_key")})
        src_c = Counter(m["source"] for m in ms)
        sent = Counter(m["sentiment"] for m in ms)
        quotes = sorted(ms, key=lambda m: -(m["metrics"].get("reactions", 0) + m["metrics"].get("like", 0)))[:qmax]
        findings.append({
            "id": fid, "type": rep["feedback_type"], "size": len(ms), "authors": authors, "players": players,
            "src": dict(src_c), "sent": dict(sent), "rep": rep, "quotes": quotes,
            "severity": "P1" if authors >= thr["act"] and sent.get("neg", 0) / len(ms) >= 0.5 else "P2" if authors >= thr["watch"] else "P3",
        })
        lines = [
            "---", f"case_id: {fid}", f"week: {week}", f"feedback_type: {rep['feedback_type']}", "status: open",
            f"sources: {dict(src_c)}", f"records: {len(ms)}", f"distinct_authors: {authors}", f"distinct_players: {players}",
            f"sentiment: {dict(sent)}", "trust: llm-distilled", "provenance: " + ("owned" if src_c.keys() == {"discord"} else "public-third-party" if src_c.keys() == {"x"} else "mixed"),
            "tags: [player-voice, " + rep["feedback_type"] + ", " + ", ".join(sorted(src_c)) + "]", "---", "",
            f"# {fid}：{q(rep['text'], 60)}", "",
            "## 代表句", *[f"- （{m['source']}／{m['sentiment']}）{q(m['text'], qchars)}" for m in quotes], "",
            "## 涉及", f"- author_key：{', '.join(sorted({m['author_key'] for m in ms}))}",
            f"- player_key：{', '.join(sorted({m['player_key'] for m in ms if m.get('player_key')})) or '（無對照）'}", "",
            "## 全部 record_id", ", ".join(m["record_id"] for m in ms), "",
            "## 狀態", "open → triaged（analyst 交叉分群後）→ forwarded → resolved / wontfix", "",
            "> 本卡由 ark-community-cli digest 產生；代表句選取與分類為規則候選，結論待 analyst 確認。",
        ]
        cases[f"{fid}.md"] = "\n".join(lines)

    # 週摘
    def tbl(rows, head):
        return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])

    src_rows = []
    for s in ("discord", "x"):
        rs = by_src.get(s, [])
        if not rs:
            continue
        unc = sum(r["feedback_type"] == "uncategorized" for r in rs) / len(rs)
        src_rows.append([s, len(rs), len({r["author_key"] for r in rs}), len({r["player_key"] for r in rs if r.get("player_key")}), f"{unc:.0%}"])
    types = sorted({r["feedback_type"] for r in live})
    ts_rows = [[t] + [sum(1 for r in live if r["feedback_type"] == t and r["sentiment"] == s) for s in ("neg", "neu", "pos")] for t in types]
    new_c = [f for f in findings if f["rep"]["cluster_id"] not in prev_sizes]
    top = findings[0] if findings else None
    summary = [
        f"本週有效 {len(live)} 則（去重前 {len(recs)}），Discord {len(by_src.get('discord', []))}／X {len(by_src.get('x', []))}，兩來源不合併計數。",
        f"最大痛點候選 {top['id']}（{top['type']}，{top['authors']} 位不同作者，{top['size']} 則）：{q(top['rep']['text'], 50)}" if top else "本週無 cluster。",
        f"與上週比：新出現 {len(new_c)} 個 top cluster；verdict={verdict}（規則：neg cluster distinct_authors ≥{thr['act']} act／≥{thr['watch']} watch）。",
    ]
    findings_md = []
    for f in findings:
        findings_md += [
            f"### {f['id']}｜{f['type']}｜{f['severity']}｜{f['authors']} 作者／{f['size']} 則／{f['players']} player_key",
            f"- 來源：{f['src']}；情感：{f['sent']}" + ("；**上週未出現**" if f in new_c else ""),
            *[f"- > （{m['source']}）{q(m['text'], qchars)}" for m in f["quotes"]],
            f"- 案件卡：`cases/{week}/{f['id']}.md`", "",
        ]
    src_files = sorted({f"classify/{r['ts'][:10]}.jsonl" for r in live})
    md = "\n".join([
        "---", "report_type: analysis", f"title: \"社群週摘 {week}\"", f"date: {today()}", f"verdict: {verdict}", f"severity: {severity}",
        "confidence: medium", "trust: deterministic", f"sources: [{', '.join(src_files)}]", "tags: [player-voice, weekly, discord, x]",
        f"findings: [{', '.join(f['id'] for f in findings)}]", "---", "",
        f"# 社群週摘 {week}", "", "## 摘要", *[f"- {s}" for s in summary], "",
        "## 來源統計", tbl(src_rows, ["來源", "則數", "distinct authors", "有 player_key", "uncategorized"]), "",
        "## feedback_type × sentiment", tbl(ts_rows, ["type", "neg", "neu", "pos"]), "",
        "## Top clusters", *findings_md,
        "## 與上週比較", f"- 上週 top cluster 數：{len(prev_sizes)}；本週新出現：{', '.join(f['id'] for f in new_c) or '無'}", "",
        "## Caveat", "- 分類與情感為規則層候選（日文反諷、顏文字、「w」語尾無效）；`classify/llm-queue.jsonl` 待 LLM 補判",
        "- X 抽樣受日預算限制，則數不代表母體；distinct_authors 比則數可信", "- Discord（已知玩家）與 X（匿名大眾）不可合併計數；同 cluster 兩來源皆出現為強訊號",
        "- 遮罩後文本可能失去部分語意；原文回查走 raw_ref（僅授權者）", "",
        f"> 由 ark-community-cli digest 產生 {today()}；verdict 為規則自動判定，analyst 覆寫需留原因。",
    ])
    return md, cases, verdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--week", required=True)
    a = ap.parse_args(argv)
    ctx = Ctx(Path(a.config))
    md, cases, verdict = build(ctx, a.week)
    out = ctx.path("reports", "weekly", f"{a.week}-community-digest.md")
    out.write_text(md, encoding="utf-8")
    cdir = ctx.path("cases", a.week)
    cdir.mkdir(parents=True, exist_ok=True)
    for name, body in cases.items():
        (cdir / name).write_text(body, encoding="utf-8")
    bad = pii_scan(out) + [h for f in cdir.glob("*.md") for h in pii_scan(f)]
    print(f"digest: {out.relative_to(ctx.root)} / verdict={verdict} / cases {len(cases)} / PII scan {'FAIL ' + str(bad[:3]) if bad else 'PASS'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
