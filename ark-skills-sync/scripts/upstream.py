#!/usr/bin/env python3
"""upstream.py — 解析並取得上游 ark-agent-skills（ark-skills-sync 共用模組 C-1）。

上游來源只認一套優先序（消費端腳本、wrapper、套件都經這裡，不各寫一份）：

1. 明確參數 `--upstream`（本機目錄或 git URL）
2. 環境變數 `ARK_SKILLS_UPSTREAM`（`ARK_AGENT_SKILLS_DIR` 視為別名 —— 套件 build 腳本的舊名）
3. manifest 的 `upstream.path`
4. 預設本機 clone `~/kiro-cli/github/shared/ark-agent-skills`
5. 都不是 git repo → `upstream.url`（預設公開 repo）clone 到快取 `~/.cache/ark-agent-skills`

🔴 快取 clone 必須是**完整歷史**：mirror_sync 以「本地 blob 是否曾出現在上游歷史」判斷 STALE／LOCAL，
shallow clone 會把所有舊版誤判成 LOCAL。
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

DEFAULT_URL = "https://github.com/igs-paddyyang-tw/ark-agent-skills.git"
DEFAULT_LOCAL = "~/kiro-cli/github/shared/ark-agent-skills"
DEFAULT_CACHE = "~/.cache/ark-agent-skills"
ENV_VARS = ("ARK_SKILLS_UPSTREAM", "ARK_AGENT_SKILLS_DIR")
_URL_RE = re.compile(r"^(https?://|git@|ssh://|file://)")


class UpstreamError(RuntimeError):
    """上游取不到（參數錯、clone 失敗）—— 呼叫端轉成 exit 2。"""


def is_url(s: str) -> bool:
    return bool(_URL_RE.match(s))


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")


def is_repo(p: Path) -> bool:
    return (p / ".git").exists()


def describe_source(explicit: str | None = None, manifest_upstream: dict | None = None) -> tuple[str, str]:
    """回傳 (來源, 依據)，不碰網路 —— 給 status 顯示「現在用的是哪個上游、為什麼」。"""
    up = manifest_upstream or {}
    for cand, why in ((explicit, "--upstream"),
                      *((os.environ.get(v), f"${v}") for v in ENV_VARS),
                      (up.get("path"), "manifest upstream.path"),
                      (DEFAULT_LOCAL, "預設本機 clone")):
        if not cand:
            continue
        if is_url(cand):
            return cand, why
        p = Path(cand).expanduser()
        if is_repo(p):
            return str(p), why
        if why == "--upstream":
            raise UpstreamError(f"--upstream 不是 git repo：{p}")
    return up.get("url") or DEFAULT_URL, "URL（本機沒有上游 clone）"


def resolve(explicit: str | None = None, manifest_upstream: dict | None = None, *,
            fetch: bool = False, cache: str | Path = DEFAULT_CACHE) -> Path:
    """回傳可用的上游 git repo 路徑；URL 來源會 clone／fetch 到 cache。

    fetch=True：本機 clone 做 `pull --ff-only`（失敗只警告、沿用 HEAD —— 上游主樹可能有別人的 WIP）；
    快取 clone 做 fetch＋detach 到 origin/HEAD。
    """
    src, _ = describe_source(explicit, manifest_upstream)
    if not is_url(src):
        p = Path(src)
        if fetch:
            r = _git("-C", str(p), "pull", "--ff-only", "-q")
            if r.returncode != 0:
                print(f"⚠ 上游 pull 失敗，沿用目前 HEAD：{(r.stderr or r.stdout).strip()[:160]}")
        return p
    c = Path(cache).expanduser()
    if not is_repo(c):
        c.parent.mkdir(parents=True, exist_ok=True)
        r = _git("clone", "-q", src, str(c))
        if r.returncode != 0:
            raise UpstreamError(f"clone {src} 失敗：{r.stderr.strip()[:200]}")
        return c
    if fetch:
        _git("-C", str(c), "fetch", "-q", "origin")
        _git("-C", str(c), "checkout", "-q", "--detach", "origin/HEAD")
    return c


def head(repo: Path) -> str:
    """`<短 hash> <日期> <標題>`；取不到回空字串。"""
    r = _git("-C", str(repo), "log", "-1", "--format=%h %cs %s")
    return r.stdout.strip()[:100] if r.returncode == 0 else ""
