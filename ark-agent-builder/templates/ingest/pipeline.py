"""入庫主流程 — source → parse → guard → store。

泛化自 ninja-bot src/skills/internal/ingest/pipeline.py。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class IngestPipeline:
    """知識入庫管線。

    流程：fetch(source) → parse(content) → guard(check) → store(wiki/)
    """

    def __init__(self, raw_dir: str | Path = "knowledge/raw",
                 wiki_dir: str | Path = "knowledge/wiki"):
        self.raw_dir = Path(raw_dir)
        self.wiki_dir = Path(wiki_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self._guards: list[Callable] = []

    def add_guard(self, guard_fn: Callable[[str], tuple[bool, str]]) -> None:
        """加入安全檢查函式。回傳 (pass, reason)。"""
        self._guards.append(guard_fn)

    async def ingest_file(self, source_path: Path) -> dict:
        """入庫單一檔案。"""
        content = source_path.read_text(encoding="utf-8")

        # Guard 檢查
        for guard in self._guards:
            ok, reason = guard(content)
            if not ok:
                log.warning("Guard blocked %s: %s", source_path.name, reason)
                return {"status": "blocked", "reason": reason, "file": str(source_path)}

        # 存入 wiki/
        dest = self.wiki_dir / source_path.name
        dest.write_text(content, encoding="utf-8")
        log.info("Ingested: %s → %s", source_path.name, dest)
        return {"status": "ok", "file": str(dest)}

    async def ingest_batch(self, source_dir: Path) -> list[dict]:
        """批次入庫目錄。"""
        results = []
        for f in sorted(source_dir.glob("*.md")):
            r = await self.ingest_file(f)
            results.append(r)
        return results
