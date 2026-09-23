"""discord_pull.py — Discord 白名單頻道增量拉取（bot 唯讀 REST）。

只做 GET。游標存 state/discord/{channel_id}.cursor；原始 JSON（含 author PII）只落 raw/discord/。
429 依 retry_after 等待（≤5 次）；401/403 立刻停不重試；5xx 指數退避 3 次。

    python discord_pull.py --config community/config.yaml [--since 7d] [--channel feedback] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Ctx, append_jsonl, parse_since, snowflake_from_time, now_iso  # noqa: E402

API = "https://discord.com/api/v10"
SKIP_TYPES = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 18, 21}  # 系統訊息；保留 0 DEFAULT / 19 REPLY / 20 CHAT_INPUT_COMMAND 等


class Discord:
    def __init__(self, token: str, interval_ms: int, dry: bool, user_agent: str = "ark-community-cli/1.0 (read-only)"):
        self.h = {"Authorization": f"Bot {token}", "User-Agent": user_agent}
        self.interval = interval_ms / 1000
        self.dry = dry
        self.n429 = 0

    def get(self, path: str, params: dict | None = None):
        url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        if self.dry:
            print(f"  DRY GET {url}")
            return []
        for attempt in range(6):
            time.sleep(self.interval)
            req = urllib.request.Request(url, headers=self.h)
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="ignore")
                if e.code == 429:
                    self.n429 += 1
                    try:
                        wait = float(json.loads(body).get("retry_after", 1.0))
                    except Exception:
                        wait = float(e.headers.get("Retry-After", 1.0))
                    print(f"  429 rate limited, sleep {wait:.2f}s")
                    time.sleep(wait + 0.05)
                    continue
                if e.code in (401, 403):
                    sys.exit(f"  {e.code} {body[:200]} → 停止。檢查 token / 頻道權限 / Message Content Intent。不重試。")
                if e.code >= 500 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise
        sys.exit("  429 重試超過 5 次，停止（避免觸發 10k 無效請求封 IP）")


def pull_channel(dc: Discord, ctx: Ctx, ch: dict, since: datetime | None, threads_of: dict[str, list]) -> int:
    cid, name = str(ch["id"]), ch.get("name", str(ch["id"]))
    cursor_p = ctx.path("state", "discord", f"{cid}.cursor")
    if cursor_p.exists():
        after = cursor_p.read_text(encoding="utf-8").strip()
    else:
        start = since or parse_since(f"{ctx.cfg['discord'].get('backfill_days', 30)}d")
        after = str(snowflake_from_time(start))
    total = 0
    targets = [(cid, name)] + [(t["id"], f"{name}/thread-{t['id']}") for t in threads_of.get(cid, [])]
    for tid, tname in targets:
        t_cursor_p = ctx.path("state", "discord", f"{tid}.cursor")
        t_after = t_cursor_p.read_text(encoding="utf-8").strip() if t_cursor_p.exists() else after
        while True:
            page = dc.get(f"/channels/{tid}/messages", {"limit": 100, "after": t_after})
            if not page:
                break
            page.sort(key=lambda m: int(m["id"]))
            rows = []
            for m in page:
                if m.get("type", 0) in SKIP_TYPES:
                    continue
                if ctx.cfg["discord"].get("skip_bots", True) and m.get("author", {}).get("bot") \
                        and str(m["author"].get("id")) not in map(str, ctx.cfg["discord"].get("allow_bot_authors", [])):
                    continue
                m["_channel_name"] = tname
                m["_channel_id"] = cid
                m["_pulled_at"] = now_iso()
                # 附件/embed 只留 URL 與檔名
                m["attachments"] = [{"url": a.get("url"), "filename": a.get("filename")} for a in m.get("attachments", [])]
                m["embeds"] = [{"url": e.get("url"), "title": e.get("title")} for e in m.get("embeds", [])]
                rows.append(m)
            day = page[-1]["timestamp"][:10]
            total += append_jsonl(ctx.path("raw", "discord", name.replace("/", "_"), f"{day}.jsonl"), rows)
            t_after = page[-1]["id"]
            t_cursor_p.write_text(t_after, encoding="utf-8")          # 先寫檔再推游標（上一行已寫）
            if len(page) < 100:
                break
    return total


def active_threads(dc: Discord, guild_id: str, whitelist: set[str]) -> dict[str, list]:
    data = dc.get(f"/guilds/{guild_id}/threads/active") or {}
    out: dict[str, list] = {}
    for t in data.get("threads", []):
        parent = str(t.get("parent_id"))
        if parent in whitelist:
            out.setdefault(parent, []).append({"id": str(t["id"]), "name": t.get("name")})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--since", help="首次回填起點，如 7d / 2026-09-01（有 cursor 時忽略）")
    ap.add_argument("--channel", help="只拉這個頻道名")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    ctx = Ctx(Path(a.config))
    dcfg = ctx.cfg.get("discord") or sys.exit("config 缺 discord 區塊")
    token = "dry" if a.dry_run else ctx.env_token("discord")
    dc = Discord(token, dcfg.get("request_interval_ms", 60), a.dry_run,
                 dcfg.get("user_agent", "ark-community-cli/1.0 (read-only)"))
    channels = [c for c in dcfg["channels"] if not a.channel or c.get("name") == a.channel]
    since = parse_since(a.since) if a.since else None

    threads: dict[str, list] = {}
    if dcfg.get("include_threads") and dcfg.get("guild_id"):
        threads = active_threads(dc, str(dcfg["guild_id"]), {str(c["id"]) for c in channels})

    total = 0
    for ch in channels:
        n = pull_channel(dc, ctx, ch, since, threads)
        print(f"  #{ch.get('name')}: +{n}")
        total += n
    nthreads = sum(len(v) for v in threads.values())
    print(f"discord: {len(channels)} 頻道 / {total} 則新訊息 / {nthreads} threads / 429 x{dc.n429}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
