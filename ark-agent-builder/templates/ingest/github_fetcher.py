"""GitHub 來源取得器 — 從 repo 抓取 raw 文件。

泛化自 ninja-bot src/skills/internal/ingest/github_fetcher.py。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class GitHubFetcher:
    """從 GitHub 下載文件到 raw/。"""

    def __init__(self, raw_dir: str | Path = "knowledge/raw",
                 token: Optional[str] = None):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._token = token

    async def fetch_file(self, repo: str, path: str, branch: str = "main") -> Path:
        """下載單一檔案。"""
        import httpx
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        headers = {"Authorization": f"token {self._token}"} if self._token else {}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        dest = self.raw_dir / Path(path).name
        dest.write_text(resp.text, encoding="utf-8")
        log.info("Fetched %s/%s → %s", repo, path, dest)
        return dest
