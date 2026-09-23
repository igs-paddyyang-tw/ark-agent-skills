"""normalize.py — raw/{discord,x} → records/{date}.jsonl（統一 schema、假名化、遮罩、去重、PII 自掃）。

    python normalize.py --config community/config.yaml [--since 7d] [--force]

規則：原始 author id 只用來算 HMAC；username/暱稱不落 records；identity_map 可讀時補 player_key。
去重：正規化文字 sha1 完全去重 + 3-gram Jaccard ≥ dedupe_jaccard 近似去重（標 duplicate_of，不刪）。
已處理的 raw 檔記在 state/normalized.json，重跑只處理新檔（--force 全重跑）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Ctx, read_jsonl, write_jsonl, record_id, detect_lang, mask, pii_scan, parse_since  # noqa: E402


def norm_text(t: str) -> str:
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"<a?:\w+:\d+>", "", t)            # discord custom emoji
    t = re.sub(r"<@!?\d+>|<#\d+>|<@&\d+>", "", t)  # mentions
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def ngrams(t: str, n: int = 3) -> set[str]:
    t = re.sub(r"\s", "", t)
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))} or {t}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def load_identity_map(ctx: Ctx) -> dict[str, str]:
    p = ctx.cfg.get("identity_map")
    if not p:
        return {}
    path = Path(p) if Path(p).is_absolute() else ctx.config_path.parent / p
    if not path.exists():
        print(f"  identity_map 不存在：{path}（跳過 player_key）")
        return {}
    out = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[str(row.get("author_id", "")).strip()] = row.get("player_key", "").strip()
    return out


def from_discord(ctx: Ctx, m: dict, ref: str, idmap: dict, patterns: dict) -> dict | None:
    text = mask(m.get("content") or "", patterns)
    if not text.strip():
        return None
    aid = str(m.get("author", {}).get("id", ""))
    reply = m.get("referenced_message", {}) or {}
    reactions = sum(r.get("count", 0) for r in m.get("reactions", []) or [])
    return {
        "record_id": record_id("discord", m["id"]),
        "source": "discord", "surface": "discord",
        "ts": m["timestamp"],
        "author_key": ctx.pseudonym(aid),
        "player_key": idmap.get(aid) or None,
        "text": text, "lang": detect_lang(text),
        "reply_to": record_id("discord", reply["id"]) if reply.get("id") else None,
        "metrics": {"reactions": reactions, "attachments": len(m.get("attachments", []))},
        "channel": m.get("_channel_name"), "query": None,
        "duplicate_of": None, "raw_ref": ref,
    }


def from_x(ctx: Ctx, p: dict, ref: str, patterns: dict) -> dict | None:
    text = mask(p.get("text") or "", patterns)
    if not text.strip():
        return None
    pm = p.get("public_metrics", {}) or {}
    reply = next((r["id"] for r in p.get("referenced_tweets", []) or [] if r.get("type") == "replied_to"), None)
    lang = p.get("lang") or detect_lang(text)
    return {
        "record_id": record_id("x", p["id"]),
        "source": "x", "surface": "x",
        "ts": p["created_at"],
        "author_key": ctx.pseudonym(str(p.get("author_id", ""))),
        "player_key": None,
        "text": text, "lang": lang if lang in ("ja", "zh", "en") else ("zh" if lang.startswith("zh") else "other"),
        "reply_to": record_id("x", reply) if reply else None,
        "metrics": {"like": pm.get("like_count", 0), "reply": pm.get("reply_count", 0),
                    "repost": pm.get("retweet_count", 0), "quote": pm.get("quote_count", 0)},
        "channel": None, "query": p.get("_query"),
        "duplicate_of": None, "raw_ref": ref,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--since", help="只處理此時間後的 raw 檔（依檔名日期）")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    ctx = Ctx(Path(a.config))
    patterns = ctx.cfg.get("mask_patterns", {})
    idmap = load_identity_map(ctx)
    state_p = ctx.path("state", "normalized.json")
    done = set() if a.force else set(json.loads(state_p.read_text()) if state_p.exists() else [])
    since_day = parse_since(a.since).strftime("%Y-%m-%d") if a.since else None

    new_by_day: dict[str, list] = defaultdict(list)
    usernames: set[str] = set()
    files = sorted(list(ctx.path("raw", "discord").rglob("*.jsonl")) + list(ctx.path("raw", "x").rglob("*.jsonl")))
    processed = []
    for f in files:
        rel = str(f.relative_to(ctx.root))
        if rel in done or (since_day and f.stem < since_day):
            continue
        src = "discord" if "/discord/" in rel.replace("\\", "/") else "x"
        for ln, raw in read_jsonl(f):
            ref = f"{rel}:{ln}"
            if src == "discord":
                usernames.add(raw.get("author", {}).get("username", ""))
                rec = from_discord(ctx, raw, ref, idmap, patterns)
            else:
                usernames.add((raw.get("_author") or {}).get("username", ""))
                rec = from_x(ctx, raw, ref, patterns)
            if rec:
                new_by_day[rec["ts"][:10]].append(rec)
        processed.append(rel)

    # 去重（同日內 + 對既有 records 的 sha 表）
    thr = float(ctx.cfg.get("classify", {}).get("dedupe_jaccard", 0.9))
    seen_sha: dict[str, str] = {}
    for f in ctx.path("records").glob("*.jsonl"):
        for _, r in read_jsonl(f):
            seen_sha[hashlib.sha1(norm_text(r["text"]).encode()).hexdigest()] = r["record_id"]
    total = dup = 0
    for day, recs in sorted(new_by_day.items()):
        grams = []
        for r in recs:
            nt = norm_text(r["text"])
            sha = hashlib.sha1(nt.encode()).hexdigest()
            if sha in seen_sha and seen_sha[sha] != r["record_id"]:
                r["duplicate_of"] = seen_sha[sha]
            else:
                seen_sha[sha] = r["record_id"]
                g = ngrams(nt)
                for rid, gg in grams:
                    if jaccard(g, gg) >= thr:
                        r["duplicate_of"] = rid
                        break
                else:
                    grams.append((r["record_id"], g))
            dup += bool(r["duplicate_of"])
        out = ctx.path("records", f"{day}.jsonl")
        existing = {r["record_id"]: r for _, r in read_jsonl(out)}
        for r in recs:
            existing.setdefault(r["record_id"], r)
        write_jsonl(out, sorted(existing.values(), key=lambda r: r["ts"]))
        total += len(recs)
        hits = pii_scan(out, [u for u in usernames if u])
        if hits:
            print(f"  🔴 PII 漏出 {out.name}: {hits[:5]} —— 檢查 mask_patterns / 假名化")
    state_p.write_text(json.dumps(sorted(done | set(processed)), ensure_ascii=False))
    print(f"normalize: {len(processed)} raw 檔 → {total} records（dup {dup}）→ records/ ；player_key 補齊 {sum(1 for rs in new_by_day.values() for r in rs if r['player_key'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
