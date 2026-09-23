"""x_pull.py — X API v2 recent search 增量拉取（pay-per-use，預算硬上限）。

    python x_pull.py --config community/config.yaml --query official-mentions --estimate
    python x_pull.py --config community/config.yaml --query official-mentions [--max-posts 200] [--dry-run]
    python x_pull.py --config community/config.yaml --all            # 所有 enabled query，各自 default_max_posts

規則：先 estimate 再拉；每頁回傳則數 × price 記進 state/x/spend.jsonl；今日累計 ≥ daily_budget_usd 直接停。
只用 app-only Bearer token；只 GET。原始貼文與 includes.users 只落 raw/x/。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Ctx, append_jsonl, read_jsonl, now_iso, today  # noqa: E402

API = "https://api.x.com/2"
FIELDS = {
    "tweet.fields": "created_at,lang,public_metrics,conversation_id,in_reply_to_user_id,author_id,referenced_tweets",
    "expansions": "author_id",
    "user.fields": "username",
}


def spent_today(ctx: Ctx) -> float:
    return sum(r.get("usd", 0.0) for _, r in read_jsonl(ctx.path("state", "x", "spend.jsonl")) if r.get("date") == today())


def record_spend(ctx: Ctx, qname: str, n: int, usd: float, kind: str) -> None:
    append_jsonl(ctx.path("state", "x", "spend.jsonl"),
                 [{"ts": now_iso(), "date": today(), "query": qname, "kind": kind, "posts": n, "usd": round(usd, 4)}])


class X:
    def __init__(self, token: str, dry: bool):
        self.h = {"Authorization": f"Bearer {token}", "User-Agent": "ark-community-cli/1.0 (read-only)"}
        self.dry = dry

    def get(self, path: str, params: dict) -> dict:
        url = f"{API}{path}?{urllib.parse.urlencode(params)}"
        if self.dry:
            print(f"  DRY GET {url}")
            return {}
        for attempt in range(4):
            req = urllib.request.Request(url, headers=self.h)
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="ignore")
                if e.code == 429:
                    reset = int(e.headers.get("x-rate-limit-reset", time.time() + 60))
                    wait = max(1, reset - int(time.time()))
                    print(f"  429, sleep {wait}s until rate-limit reset")
                    time.sleep(wait + 1)
                    continue
                if e.code in (401, 402, 403):
                    sys.exit(f"  {e.code} {body[:200]} → 停止。401 token / 402 credits 用完 / 403 權限。不重試。")
                if e.code >= 500 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise
        sys.exit("  重試耗盡，停止")


def estimate(x: X, ctx: Ctx, q: dict, budget_left: float, price: float) -> None:
    data = x.get("/tweets/counts/recent", {"query": q["query"], "granularity": "day"})
    if not data:
        return
    days = data.get("data", [])
    total = sum(d.get("tweet_count", 0) for d in days)
    per_day = total / max(1, len(days))
    est = total * price
    suggest = int(min(budget_left / price, ctx.cfg["x"].get("default_max_posts", 200)))
    print(f"  {q['name']}: 近 7 天 {total} 則 / 日均 {per_day:.0f} / 全拉預估 ${est:.2f} / 今日預算剩 ${budget_left:.2f} → 建議 --max-posts {suggest}")
    if per_day > 700:
        print("  ⚠️ 日均 > 700，query 太寬：加引號、限定詞或 min_likes:，不要加預算")
    record_spend(ctx, q["name"], 0, 0.0, "estimate")


def pull(x: X, ctx: Ctx, q: dict, max_posts: int, price: float, budget: float) -> tuple[int, float]:
    qname = q["name"]
    cursor_p = ctx.path("state", "x", f"{qname}.cursor")
    params = {"query": q["query"], "max_results": 100, **FIELDS}
    if cursor_p.exists():
        params["since_id"] = cursor_p.read_text(encoding="utf-8").strip()
    got, cost, newest = 0, 0.0, None
    while got < max_posts:
        if spent_today(ctx) + cost >= budget:
            print(f"  預算到頂（${budget}），停止")
            break
        params["max_results"] = max(10, min(100, max_posts - got))
        data = x.get("/tweets/search/recent", params)
        if not data:
            break
        posts = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        if not posts:
            break
        rows = []
        for p in posts:
            p["_query"] = qname
            p["_pulled_at"] = now_iso()
            p["_author"] = users.get(p.get("author_id"), {})     # 只在 raw 層有 username
            rows.append(p)
        day = posts[0]["created_at"][:10]
        append_jsonl(ctx.path("raw", "x", qname, f"{day}.jsonl"), rows)
        page_cost = len(posts) * price
        record_spend(ctx, qname, len(posts), page_cost, "search")
        got += len(posts)
        cost += page_cost
        newest = newest or data.get("meta", {}).get("newest_id")
        nt = data.get("meta", {}).get("next_token")
        if not nt:
            break
        params["next_token"] = nt
    if newest:
        cursor_p.write_text(str(newest), encoding="utf-8")
    return got, cost


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--query", help="config.x.queries 的 name")
    ap.add_argument("--all", action="store_true", help="所有 enabled query")
    ap.add_argument("--estimate", action="store_true", help="只打 counts endpoint，不拉貼文")
    ap.add_argument("--max-posts", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    ctx = Ctx(Path(a.config))
    xcfg = ctx.cfg.get("x") or sys.exit("config 缺 x 區塊")
    price = float(xcfg.get("price_per_post_usd", 0.005))
    budget = float(xcfg.get("daily_budget_usd", 1.0))
    queries = [q for q in xcfg["queries"] if q.get("enabled", True)]
    if a.query:
        queries = [q for q in xcfg["queries"] if q["name"] == a.query] or sys.exit(f"query `{a.query}` 不在 config")
    elif not a.all:
        sys.exit("指定 --query <name> 或 --all")

    x = X("dry" if a.dry_run else ctx.env_token("x"), a.dry_run)
    spent = spent_today(ctx)
    if spent >= budget:
        print(f"x: 今日已花 ${spent:.2f} ≥ 預算 ${budget:.2f}，不拉。收窄 query 或明天再來。")
        return 1
    if a.estimate:
        for q in queries:
            estimate(x, ctx, q, budget - spent, price)
        return 0
    for q in queries:
        n, c = pull(x, ctx, q, a.max_posts or xcfg.get("default_max_posts", 200), price, budget)
        total = spent_today(ctx)
        print(f"x/{q['name']}: {n} 則 / ${c:.2f} / 今日累計 ${total:.2f} / 預算剩 ${max(0, budget - total):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
