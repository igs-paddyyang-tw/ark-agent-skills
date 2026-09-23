"""community_cli.py — ark-community-cli 單一入口。

    python community_cli.py init --out community/            # 產 config.yaml（含隨機鹽）與目錄
    python community_cli.py pull discord --config ... [args]  # → discord_pull.py
    python community_cli.py pull x --config ... [args]        # → x_pull.py
    python community_cli.py normalize --config ...            # → normalize.py
    python community_cli.py classify --config ... [--week]    # → classify.py
    python community_cli.py digest --config ... --week W      # → digest.py
    python community_cli.py loop handoff|compare --config ... # → loop.py
    python community_cli.py status --config ...               # 游標、今日 X 花費、raw 保留期、待 ingest 數

所有子命令參數原樣轉交對應腳本（--help 可看各自參數）。
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import SKILL_DIR, load_yaml, dump_yaml, read_jsonl, today  # noqa: E402


def init(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print("init --out DIR [--force]：產 config.yaml（含隨機鹽）與目錄；--force 覆寫（注意鹽值不可換）")
        return 0
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path("community")
    out.mkdir(parents=True, exist_ok=True)
    cfg_p = out / "config.yaml"
    if cfg_p.exists() and "--force" not in argv:
        print(f"{cfg_p} 已存在（--force 覆寫；注意鹽值不可換）")
        return 1
    cfg = load_yaml(SKILL_DIR / "assets" / "config.example.yaml")
    cfg["root"] = "."
    cfg["pseudonym_salt"] = secrets.token_hex(32)
    cfg["classify"]["lexicon"] = str(SKILL_DIR / "assets" / "lexicon.yaml")
    cfg_p.write_text("# 由 ark-community-cli init 產生。pseudonym_salt 永不更換；此檔權限 600、不進 git。\n" + dump_yaml(cfg), encoding="utf-8")
    try:
        os.chmod(cfg_p, 0o600)
    except OSError:
        pass
    for d in ("state/discord", "state/x", "raw/discord", "raw/x", "records", "classify", "cases", "reports/weekly", "reports/decisions"):
        (out / d).mkdir(parents=True, exist_ok=True)
    (out / ".gitignore").write_text("config.yaml\nraw/\nstate/\n", encoding="utf-8")
    print(f"init: {cfg_p}（鹽已產生）；接著填 discord.channels / x.queries，token 放環境變數 DISCORD_BOT_TOKEN / X_BEARER_TOKEN")
    return 0


def status(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print("status --config PATH：印游標、今日 X 花費、raw 保留期、records 數、待 ingest 數")
        return 0
    from common import Ctx
    ctx = Ctx(Path(argv[argv.index("--config") + 1]))
    print(f"root: {ctx.root}")
    cursors = list(ctx.path("state", "discord").glob("*.cursor"))
    print(f"discord cursors: {len(cursors)}")
    spend = [r for _, r in read_jsonl(ctx.path("state", "x", "spend.jsonl")) if r.get("date") == today()]
    usd = sum(r.get("usd", 0) for r in spend)
    print(f"x today: ${usd:.2f} / budget ${ctx.cfg.get('x', {}).get('daily_budget_usd', 0)} ({sum(r.get('posts', 0) for r in spend)} posts)")
    ret = int(ctx.cfg.get("retention_days", 90))
    cutoff = (datetime.now() - timedelta(days=ret)).strftime("%Y-%m-%d")
    old = [f for f in ctx.path("raw").rglob("*.jsonl") if f.stem < cutoff]
    print(f"raw files past retention ({ret}d): {len(old)}" + ("  → 執行清理：find raw -name '*.jsonl' 依日期刪除" if old else ""))
    recs = sum(1 for f in ctx.path("records").glob("*.jsonl") for _ in read_jsonl(f))
    print(f"records: {recs}")
    q = ctx.path("classify", "llm-queue.jsonl")
    print(f"llm-queue: {sum(1 for _ in read_jsonl(q)) if q.exists() else 0}")
    hand = sorted(ctx.path("reports", "weekly").glob("*-handoff.json"))
    print(f"handoff manifests: {len(hand)}" + (f"（最新 {hand[-1].name}）" if hand else ""))
    return 0


def run(script: str, argv: list[str]) -> int:
    import runpy
    sys.argv = [script] + argv
    try:
        runpy.run_path(str(HERE / script), run_name="__main__")
    except SystemExit as e:
        if isinstance(e.code, int) or e.code is None:
            return int(e.code or 0)
        print(e.code)
        return 1
    return 0


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = a[0], a[1:]
    if cmd == "init":
        return init(rest)
    if cmd == "status":
        return status(rest)
    if cmd == "pull":
        if not rest or rest[0] not in ("discord", "x"):
            print("pull discord|x ...")
            return 2
        return run("discord_pull.py" if rest[0] == "discord" else "x_pull.py", rest[1:])
    if cmd in ("normalize", "classify", "digest"):
        return run(f"{cmd}.py", rest)
    if cmd == "loop":
        return run("loop.py", rest)
    print(f"未知子命令 {cmd}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
