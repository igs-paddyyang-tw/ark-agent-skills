#!/usr/bin/env python3
"""gh_docs.py — L2 平台知識：從 GitHub repo 同步文件到 knowledge/github/，本地優先檢索

Usage:
    python gh_docs.py sync <owner/repo> --paths <p1> [<p2> ...] --dest <workspace> [--ref main]
    python gh_docs.py search "<query>" [--repo <owner/repo>] [--dest <workspace>]
    python gh_docs.py issue <owner/repo> <number>
    python gh_docs.py list --dest <workspace>

sync  以 git sparse-checkout 拉指定路徑 → <dest>/knowledge/github/<repo>/，寫 _meta.json（sha/時間/路徑）
search 先 grep 本地已同步檔；miss 且有 gh 時走 `gh search code`
issue 需 gh（已 auth）
唯讀：不 commit / push / 開 issue
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 2):
    print(__doc__ or "")
    raise SystemExit(0)

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sh(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def opt(argv: list[str], name: str, default=None, multi=False):
    if name not in argv:
        return [] if multi else default
    i = argv.index(name) + 1
    if not multi:
        return argv[i] if i < len(argv) else default
    vals = []
    while i < len(argv) and not argv[i].startswith("--"):
        vals.append(argv[i]); i += 1
    return vals


def kb_dir(dest: Path, repo: str) -> Path:
    return dest / "knowledge" / "github" / repo.split("/")[-1]


def cmd_sync(argv: list[str]) -> int:
    repo = argv[0]
    paths = [p.rstrip("/") for p in opt(argv, "--paths", multi=True)]  # cone-mode sparse-checkout 不吃尾斜線
    dest = Path(opt(argv, "--dest", ".")).resolve()
    ref = opt(argv, "--ref", "main")
    if not paths:
        print("❌ --paths 必填（README.md docs/ …）"); return 1
    if not have("git"):
        print("❌ 需要 git"); return 1
    url = f"https://github.com/{repo}.git"
    out = kb_dir(dest, repo); out.mkdir(parents=True, exist_ok=True)
    meta_p = out / "_meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {"repo": repo, "files": {}}

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r = sh("git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", "--branch", ref, url, str(tmp / "r"))
        if r.returncode != 0:
            print("❌ clone 失敗：" + r.stderr.strip()[-300:]); return 2
        rr = tmp / "r"
        # cone-mode 只接受目錄；根層檔案（README.md）本來就隨 cone 根目錄帶入，子目錄內的檔案改拉其父目錄
        dirs = sorted({p if "." not in p.rsplit("/", 1)[-1] else (p.rsplit("/", 1)[0] if "/" in p else "") for p in paths})
        dirs = [d for d in dirs if d]
        sc = sh("git", "sparse-checkout", "set", *dirs, cwd=rr) if dirs else None
        if sc is not None and sc.returncode != 0:
            print("❌ sparse-checkout 失敗：" + sc.stderr.strip()[-200:]); return 2
        sha = sh("git", "rev-parse", "HEAD", cwd=rr).stdout.strip()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        seen, changed = set(), 0
        for p in paths:
            src = rr / p
            files = [src] if src.is_file() else [f for f in src.rglob("*") if f.is_file()] if src.exists() else []
            if not files:
                print(f"⚠️  repo 內無此路徑：{p}")
            for f in files:
                rel = f.relative_to(rr).as_posix(); seen.add(rel)
                blob = sh("git", "hash-object", str(f), cwd=rr).stdout.strip()
                if meta["files"].get(rel, {}).get("blob") == blob:
                    continue
                tgt = out / rel; tgt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, tgt); changed += 1
                meta["files"][rel] = {"blob": blob, "synced": now, "stale": False}
        for rel, m in meta["files"].items():
            if rel not in seen and any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in paths):
                m["stale"] = True
        meta.update({"sha": sha, "ref": ref, "synced": now, "paths": paths})
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    stale = sum(1 for m in meta["files"].values() if m.get("stale"))
    print(f"✅ {repo}@{sha[:7]} → {out}  更新 {changed} 檔，共 {len(meta['files'])}（stale {stale}）")
    return 0


def cmd_search(argv: list[str]) -> int:
    query = argv[0]
    repo = opt(argv, "--repo")
    dest = Path(opt(argv, "--dest", ".")).resolve()
    base = dest / "knowledge" / "github"
    hits = []
    if base.exists():
        scope = [kb_dir(dest, repo)] if repo else [d for d in base.iterdir() if d.is_dir()]
        pat = re.compile(re.escape(query), re.I)
        for d in scope:
            for f in d.rglob("*"):
                if f.is_file() and f.name != "_meta.json" and f.suffix in {".md", ".py", ".yaml", ".yml", ".txt", ".json", ".toml"}:
                    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if pat.search(line):
                            hits.append(f"{f.relative_to(dest)}:{i}  {line.strip()[:100]}")
    if hits:
        print(f"── 本地命中 {len(hits)}（knowledge/github/）")
        for h in hits[:40]: print("   " + h)
        return 0
    if not have("gh"):
        print("⚠️  本地無命中，且無 gh CLI 可查遠端；先 sync 文件"); return 1
    args = ["gh", "search", "code", query, "--limit", "20"]
    if repo: args += ["--repo", repo]
    r = sh(*args)
    if r.returncode != 0:
        print("❌ gh search 失敗：" + r.stderr.strip()[-200:]); return 2
    print("── 遠端命中（gh search code）"); print(r.stdout.strip() or "   （無）")
    return 0


def cmd_issue(argv: list[str]) -> int:
    if not have("gh"):
        print("❌ 需要 gh CLI（gh auth login）"); return 1
    repo, num = argv[0], argv[1]
    r = sh("gh", "issue", "view", num, "--repo", repo, "--comments")
    if r.returncode != 0:
        r = sh("gh", "pr", "view", num, "--repo", repo, "--comments")
    if r.returncode != 0:
        print("❌ 讀取失敗：" + r.stderr.strip()[-200:]); return 2
    print(r.stdout[:6000]); return 0


def cmd_list(argv: list[str]) -> int:
    dest = Path(opt(argv, "--dest", ".")).resolve()
    base = dest / "knowledge" / "github"
    if not base.exists():
        print("（尚未同步任何 repo）"); return 0
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        m = d / "_meta.json"
        if m.exists():
            j = json.loads(m.read_text())
            print(f"{j.get('repo', d.name):40} {j.get('sha', '')[:7]:8} {j.get('synced', '')[:19]}  files={len(j.get('files', {}))}")
    return 0


def main() -> int:
    cmd, rest = sys.argv[1], sys.argv[2:]
    table = {"sync": cmd_sync, "search": cmd_search, "issue": cmd_issue, "list": cmd_list}
    if cmd not in table:
        print(f"❌ 未知子命令：{cmd}（sync | search | issue | list）"); return 1
    return table[cmd](rest)


if __name__ == "__main__":
    raise SystemExit(main())
