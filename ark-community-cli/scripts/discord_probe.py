"""discord_probe.py — Discord 頻道運維輔助（唯讀）：probe 健檢 + resolve 補頻道名。

    python discord_probe.py probe   --config community/config.yaml [--channel feedback]
    python discord_probe.py resolve --config community/config.yaml [--write]

- probe：逐一探測 config.discord.channels 白名單，印可讀性 + 最近一則訊息摘要。
- resolve：GET /guilds/{guild}/channels，用 API 的真實名稱回填 config 的 channels[].name；
  預設只印差異（dry），加 --write 才回寫 config。

複用 discord_pull.Discord（UA/429/get）與 common.Ctx（config/白名單/token）。只 GET，不寫 Discord。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Ctx, load_yaml, dump_yaml  # noqa: E402
from discord_pull import Discord  # noqa: E402

TYPE_MAP = {0: "text", 2: "voice", 4: "category", 5: "news", 10: "news-thread",
            11: "public-thread", 12: "private-thread", 13: "stage", 15: "forum"}


def _fmt_last(msgs: list) -> str:
    """把最近一則訊息格式化成一行摘要（不含作者 PII 之外的原始 ID）。"""
    if not msgs:
        return "(無訊息)"
    m = msgs[0]
    content = (m.get("content") or "").replace("\n", " ").strip()
    if len(content) > 30:
        content = content[:30] + "…"
    if not content:
        content = "(附件/貼圖/嵌入)"
    ts = (m.get("timestamp") or "")[:10]
    author = (m.get("author") or {}).get("username", "?")
    return f"[{ts}] {author}: {content}"


def probe(dc: Discord, ctx: Ctx, only: str | None) -> int:
    channels = [c for c in ctx.cfg["discord"]["channels"] if not only or c.get("name") == only]
    print(f"probe: {len(channels)} 個白名單頻道\n")
    ok = 0
    for c in channels:
        cid = str(c["id"])
        try:
            ch = dc.get(f"/channels/{cid}")
            tn = TYPE_MAP.get(ch.get("type"), f"t{ch.get('type')}")
            msgs = dc.get(f"/channels/{cid}/messages", {"limit": 1})
            print(f"  [{tn}] {c.get('name')} ({cid}) -> {_fmt_last(msgs)}")
            ok += 1
        except SystemExit as e:
            print(f"  {c.get('name')} ({cid}) FAIL: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  {c.get('name')} ({cid}) FAIL: {str(e)[:80]}")
    print(f"\n可讀 {ok}/{len(channels)} / 429 x{dc.n429}")
    return 0 if ok == len(channels) else 1


def resolve(dc: Discord, ctx: Ctx, write: bool) -> int:
    guild = str(ctx.cfg["discord"].get("guild_id", ""))
    if not guild or set(guild) == {"0"}:
        sys.exit("config.discord.guild_id 未設定，無法 resolve")
    remote = {str(ch["id"]): ch.get("name") for ch in dc.get(f"/guilds/{guild}/channels")}
    diffs = 0
    for c in ctx.cfg["discord"]["channels"]:
        cid, cur = str(c["id"]), c.get("name")
        real = remote.get(cid)
        if real and real != cur:
            print(f"  {cid}: {cur!r} -> {real!r}")
            c["name"] = real
            diffs += 1
        elif not real:
            print(f"  {cid}: (guild 內找不到，略過)")
    if diffs and write:
        ctx.config_path.write_text(
            "# 由 ark-community-cli init 產生。pseudonym_salt 永不更換；此檔權限 600、不進 git。\n"
            + dump_yaml(ctx.cfg), encoding="utf-8")
        print(f"\nresolve: 回寫 {diffs} 個頻道名到 {ctx.config_path.name}")
    else:
        print(f"\nresolve: {diffs} 個差異" + ("（加 --write 回寫）" if diffs and not write else ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe"); p.add_argument("--config", required=True); p.add_argument("--channel")
    r = sub.add_parser("resolve"); r.add_argument("--config", required=True); r.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)

    ctx = Ctx(Path(a.config))
    dcfg = ctx.cfg.get("discord") or sys.exit("config 缺 discord 區塊")
    dc = Discord(ctx.env_token("discord"), dcfg.get("request_interval_ms", 60), False,
                 dcfg.get("user_agent", "ark-community-cli/1.0 (read-only)"))
    if a.cmd == "probe":
        return probe(dc, ctx, a.channel)
    return resolve(dc, ctx, a.write)


if __name__ == "__main__":
    sys.exit(main())
