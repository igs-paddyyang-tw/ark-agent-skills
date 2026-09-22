#!/usr/bin/env python3
"""wrapup_git.py — 收尾提交：具名 add → commit → pull --rebase → push

Usage:
    python wrapup_git.py <workspace> --paths <p1> [<p2> ...] --message "<msg>" [--dry-run] [--no-push] [--no-gate "<理由>"]

收尾閘門（預設開啟）：commit 前先跑 ①②③ 的 deterministic 檢查，任一不過 → exit 5，不 commit：
    - memory/daily/今天.md 存在（② 已追加）
    - memory/memory.md ≤ 2000 tokens（② 已瘦身）
    - wrapup_check --drift 零命中（③ 規範已同步）
    - 未勾 todo 只列警告不擋（① 由 LLM 核對，腳本無法判斷「本次完成」）
    --no-gate "<理由>"  跳過閘門（hotfix 用），理由寫進 commit trailer `Wrapup-Gate: skipped (<理由>)`，留痕不留洞

行為：
    - 無 .git           → 印 skipped，exit 0（收尾前三步不依賴 git）
    - --paths 必填、具名 → 不接受 -A / . （避免暫存檔、密鑰入庫）；不存在的路徑略過並提示
    - 無變更             → 印 nothing to commit，exit 0
    - pull --rebase 衝突 → 停在衝突狀態、不 push、exit 3，列出衝突檔
    - push 失敗          → exit 4，commit 保留本地
    - 永不 force push；.env / *.key / *.pem 出現在 --paths 直接拒絕 exit 1
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 2):
    print(__doc__ or "")
    raise SystemExit(0)

import subprocess
from pathlib import Path

FORBIDDEN = (".env", ".key", ".pem", "id_rsa", ".p12")


def run(ws: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True, check=check)


def parse(argv: list[str]) -> tuple[Path, list[str], str, bool, bool, str | None]:
    ws = Path(argv[0]).resolve()
    paths, msg, dry, no_push, no_gate = [], "", False, False, None
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--paths":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                paths.append(argv[i]); i += 1
            continue
        if a == "--message":
            msg = argv[i + 1]; i += 2; continue
        if a == "--no-gate":
            no_gate = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else "(no reason)"
            i += 2 if no_gate != "(no reason)" else 1; continue
        if a == "--dry-run":
            dry = True
        elif a == "--no-push":
            no_push = True
        i += 1
    return ws, paths, msg, dry, no_push, no_gate


def wrapup_gate(ws: Path) -> list[str]:
    """收尾閘門：回傳阻擋原因清單（空 = 通過）。全 deterministic，判斷在 LLM 端已完成才會走到這。"""
    import importlib.util
    from datetime import date
    here = Path(__file__).resolve().parent
    def load(name):
        spec = importlib.util.spec_from_file_location(name, here / f"{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    blocks = []
    if not (ws / "memory" / "daily" / f"{date.today().isoformat()}.md").exists():
        blocks.append("② 今日 daily 未追加：memory_optimize.py <ws> daily \"…\"")
    mem = ws / "memory" / "memory.md"
    if mem.exists():
        tokens = load("memory_optimize").estimate_tokens(mem.read_text(encoding="utf-8", errors="ignore"))
        if tokens > 2000:
            blocks.append(f"② memory.md ≈ {tokens} tokens > 2000：先 archive 瘦身")
    chk = load("wrapup_check")
    drift = [d for d in chk.find_drift(ws) if not d.startswith("（")]
    if drift:
        blocks.append("③ 索引漂移未同步：" + "；".join(drift[:3]) + (" …" if len(drift) > 3 else ""))
    todos = chk.find_todos(ws)
    if todos:
        print(f"⚠️  ① 尚有 {len(todos)} 個未勾 todo（不擋；請確認本次完成項已標 [x]）")
    return blocks


def main() -> int:
    ws, paths, msg, dry, no_push, no_gate = parse(sys.argv[1:])
    if not (ws / ".git").exists():
        print("skipped: not a git repo"); return 0
    if not paths or any(p in ("-A", ".", "*") for p in paths):
        print("❌ --paths 必填且必須具名（不接受 -A / .）"); return 1
    bad = [p for p in paths if any(t in p for t in FORBIDDEN)]
    if bad:
        print(f"❌ 拒絕加入敏感路徑：{bad}"); return 1
    if not msg:
        print("❌ --message 必填"); return 1

    existing = [p for p in paths if (ws / p).exists()]
    for p in set(paths) - set(existing):
        print(f"⚠️  路徑不存在，略過：{p}")
    if not existing:
        print("nothing to add"); return 0

    if no_gate is None:
        blocks = wrapup_gate(ws)
        if blocks:
            print("❌ 收尾閘門未過，不 commit：")
            for b in blocks: print("   - " + b)
            print("   （hotfix 可 --no-gate \"理由\"，理由會寫進 commit trailer）")
            return 5
        print("✅ 收尾閘門通過（daily ✓ memory ≤2000 ✓ 索引同步 ✓）")
    else:
        print(f"⚠️  跳過收尾閘門：{no_gate}")
        msg = f"{msg}\n\nWrapup-Gate: skipped ({no_gate})"

    if dry:
        st = run(ws, "status", "--porcelain", "--", *existing).stdout
        print("[dry-run] 將加入：\n" + (st or "   （無變更）"))
        print(f"[dry-run] commit -m {msg!r} → pull --rebase → push"); return 0

    run(ws, "add", "--", *existing, check=True)
    if not run(ws, "diff", "--cached", "--quiet").returncode:
        print("nothing to commit"); return 0
    run(ws, "commit", "-m", msg, check=True)
    print(f"✅ commit: {msg}")

    branch = run(ws, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    has_upstream = run(ws, "rev-parse", "--abbrev-ref", "@{u}").returncode == 0
    if has_upstream:
        pr = run(ws, "pull", "--rebase")
        if pr.returncode != 0:
            conflicts = run(ws, "diff", "--name-only", "--diff-filter=U").stdout.strip()
            print("❌ pull --rebase 衝突，已停在衝突狀態、未 push。衝突檔：")
            print(conflicts or pr.stderr.strip()[-400:])
            print("   處理後：git rebase --continue，再手動 push；或 git rebase --abort 回復")
            return 3
        print("✅ pull --rebase 完成")
    else:
        print(f"⚠️  分支 {branch} 無 upstream，跳過 pull；push 將設 -u origin {branch}")

    if no_push:
        print("（--no-push）commit 保留本地"); return 0
    push = run(ws, "push") if has_upstream else run(ws, "push", "-u", "origin", branch)
    if push.returncode != 0:
        print("❌ push 失敗，commit 保留本地：\n" + push.stderr.strip()[-400:]); return 4
    print(f"✅ push → {branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
