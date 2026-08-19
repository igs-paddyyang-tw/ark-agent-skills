"""蒸餾主引擎 — raw 文件 → wiki synthesis 頁面。

泛化自 ninja-bot src/skills/internal/distill/distiller.py。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)


class Distiller:
    """將多份 raw 文件蒸餾為結構化 wiki 頁面。

    核心邏輯：
    1. 掃描 raw/ 找到同主題文件（by tag/subject）
    2. 呼叫 LLM 摘要
    3. 產出 wiki/ synthesis 頁（含 provenance 追溯）
    """

    def __init__(self, raw_dir: str | Path = "knowledge/raw",
                 wiki_dir: str | Path = "knowledge/wiki",
                 llm_fn: Optional[Callable] = None):
        self.raw_dir = Path(raw_dir)
        self.wiki_dir = Path(wiki_dir)
        self._llm = llm_fn  # async fn(prompt) -> str

    async def distill(self, subject: str, source_files: list[Path]) -> Optional[Path]:
        """蒸餾指定主題。"""
        if not self._llm:
            log.warning("No LLM function provided, skipping distillation")
            return None

        # 組合 context
        context = ""
        for f in source_files:
            context += f"### {f.name}\n{f.read_text(encoding='utf-8')}\n\n"

        prompt = (
            f"你是知識管理員。將以下 {len(source_files)} 份文件蒸餾為一篇結構化 wiki 頁面。\n"
            f"主題：{subject}\n"
            f"要求：frontmatter（title/tags/trust:llm-distilled/sources）+ 摘要 + 重點。\n\n"
            f"{context}"
        )

        result = await self._llm(prompt)
        dest = self.wiki_dir / f"{subject.replace(' ', '-')}.md"
        dest.write_text(result, encoding="utf-8")
        log.info("Distilled %d files → %s", len(source_files), dest)
        return dest
