"""Wiki Indexer — 建置持久化搜尋索引。

產出到 knowledge/.index/:
  - metadata.json  — 所有頁面的 slug/title/aliases/tags 快速查表
  - userdict.txt   — jieba 自定義詞典（從 title + aliases 產生）
  - manifest.json  — 索引版本 + 最後重建時間 + 頁面數
  - bm25s/         — bm25s 持久化索引（Phase 1）
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("wiki.indexer")

BASE_DIR = Path(__file__).resolve().parents[2]
WIKI_DIR = BASE_DIR / "knowledge" / "shared" / "wiki"
INDEX_DIR = BASE_DIR / "knowledge" / "shared" / ".index"


def rebuild_index() -> dict:
    """重建所有搜尋索引。回傳 manifest 內容。"""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    pages = scan_wiki_pages()
    log.info("Rebuilding index: %d pages", len(pages))

    # 1. metadata.json
    build_metadata(pages)

    # 2. userdict.txt
    build_userdict(pages)

    # 3. bm25s 索引（選配）
    build_bm25_index(pages)

    # 4. manifest.json
    manifest = write_manifest(len(pages))

    log.info("Index rebuilt: %d pages, manifest=%s", len(pages), manifest)
    return manifest


def scan_wiki_pages(include_agents: bool = True) -> list[dict]:
    """掃描 wiki/ 所有 .md，擷取 frontmatter 資訊。

    搜尋範圍：shared/wiki/ + agents/*/knowledge/wiki/
    """
    pages = []

    # Layer 1: 共用 wiki（主要）
    pages.extend(_scan_wiki_dir(WIKI_DIR, scope="shared"))

    # Layer 2: Agent 私有 wiki（選配）
    if include_agents:
        agents_dir = BASE_DIR / "agents"
        if agents_dir.exists():
            for agent in sorted(agents_dir.iterdir()):
                if not agent.is_dir() or agent.name.startswith("."):
                    continue
                agent_wiki = agent / "knowledge" / "wiki"
                if agent_wiki.exists():
                    pages.extend(_scan_wiki_dir(agent_wiki, scope=agent.name))

    return pages


def _scan_wiki_dir(wiki_dir: Path, scope: str = "shared") -> list[dict]:
    """掃描單一 wiki 目錄。"""
    pages = []
    if not wiki_dir.exists():
        return pages

    for md in sorted(wiki_dir.rglob("*.md")):
        if md.name.startswith("."):
            continue
        content = md.read_text(encoding="utf-8")
        # Strip BOM
        if content.startswith("\ufeff"):
            content = content[1:]

        fm = _parse_frontmatter(content)
        body = _strip_frontmatter(content)
        rel_path = str(md.relative_to(wiki_dir))

        pages.append({
            "slug": md.stem,
            "title": fm.get("title", md.stem),
            "aliases": fm.get("aliases", []),
            "tags": fm.get("tags", []),
            "related": fm.get("related", []),
            "type": fm.get("type", ""),
            "path": rel_path,
            "scope": scope,
            "updated": fm.get("updated", ""),
            "body": body,  # 暫存供 BM25 用，不寫入 metadata.json
        })

    return pages


def build_metadata(pages: list[dict]) -> None:
    """產出 metadata.json（不含 body）。"""
    metadata = []
    for p in pages:
        metadata.append({
            "slug": p["slug"],
            "title": p["title"],
            "aliases": p["aliases"],
            "tags": p["tags"],
            "related": p["related"],
            "type": p["type"],
            "path": p["path"],
            "scope": p.get("scope", "shared"),
            "updated": p["updated"],
        })

    out = INDEX_DIR / "metadata.json"
    out.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("metadata.json: %d entries", len(metadata))


def build_userdict(pages: list[dict]) -> None:
    """從 title + aliases 產生 jieba 自定義詞典。"""
    words: set[str] = set()
    for p in pages:
        # title 作為詞
        title = p["title"]
        if len(title) >= 2:
            words.add(title)
        # aliases
        for alias in p["aliases"]:
            if len(alias) >= 2:
                words.add(alias)
        # tags
        for tag in p["tags"]:
            if len(tag) >= 2:
                words.add(tag)

    out = INDEX_DIR / "userdict.txt"
    lines = [f"{w} 5" for w in sorted(words)]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("userdict.txt: %d words", len(words))


def build_bm25_index(pages: list[dict]) -> None:
    """建置 bm25s 持久化索引（選配，沒安裝則跳過）。"""
    try:
        import bm25s
    except ImportError:
        log.info("bm25s not installed, skipping BM25 index")
        return

    corpus_tokens = []
    for p in pages:
        tokens = _tokenize_for_bm25(p)
        corpus_tokens.append(tokens)

    if not corpus_tokens:
        return

    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)

    bm25_dir = (INDEX_DIR / "bm25s").resolve()

    # 清空舊索引（避免 Windows mmap 鎖定問題）
    if bm25_dir.exists():
        import shutil
        try:
            shutil.rmtree(bm25_dir)
        except OSError:
            pass

    bm25_dir.mkdir(parents=True, exist_ok=True)

    try:
        retriever.save(str(bm25_dir))
        log.info("bm25s index: %d documents", len(corpus_tokens))
    except OSError as e:
        log.warning("bm25s save failed (index still in memory): %s", e)


def _tokenize_for_bm25(page: dict) -> list[str]:
    """BM25 分詞：title×3 + tags×2 + body×1，jieba + bigram 保險絲。"""
    # 欄位加權：用重複文本實現
    title = page["title"]
    tags = " ".join(page.get("tags", []))
    body = page.get("body", "")

    weighted_text = f"{title} {title} {title} {tags} {tags} {body}"

    return tokenize_text(weighted_text)


def tokenize_text(text: str) -> list[str]:
    """分詞：jieba cut_for_search + bigram 保險絲 + 停用詞過濾。"""
    stopwords = {"的", "是", "了", "在", "有", "什麼", "嗎", "呢", "可以", "怎麼",
                 "一個", "和", "與", "到", "也", "就", "都", "會", "要", "這", "那",
                 "不", "我", "你", "他", "她", "它", "們"}

    try:
        import jieba
        # 載入自定義詞典
        userdict = INDEX_DIR / "userdict.txt"
        if userdict.exists():
            jieba.load_userdict(str(userdict))
        tokens = list(jieba.cut_for_search(text))
    except ImportError:
        # Fallback：空格 + bigram
        tokens = text.lower().split()

    # Bigram 保險絲（未登錄詞保險）
    cjk_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
    bigrams = [cjk_chars[i] + cjk_chars[i + 1] for i in range(len(cjk_chars) - 1)]
    tokens.extend(bigrams)

    # 停用詞過濾 + 去空白
    return [t.lower() for t in tokens if t.strip() and t not in stopwords and len(t) > 0]


def write_manifest(page_count: int) -> dict:
    """寫入 manifest.json。"""
    manifest = {
        "version": "1.0.0",
        "rebuilt_at": datetime.now(timezone.utc).isoformat(),
        "page_count": page_count,
        "has_bm25": (INDEX_DIR / "bm25s" / "params.index.json").exists(),
    }
    out = INDEX_DIR / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_metadata() -> list[dict]:
    """讀取 metadata.json。不存在則回空。"""
    path = INDEX_DIR / "metadata.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


# ─── Helpers ─────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter（簡易版，不依賴 pyyaml）。"""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end]

    result: dict = {}
    for line in fm_text.splitlines():
        m = re.match(r'^(\w+):\s*(.+)$', line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            # 解析列表 [a, b, c]
            if val.startswith("[") and val.endswith("]"):
                items = [x.strip().strip("'\"") for x in val[1:-1].split(",")]
                result[key] = [x for x in items if x]
            else:
                result[key] = val.strip("'\"")
    return result


def _strip_frontmatter(content: str) -> str:
    """移除 frontmatter，回傳純正文。"""
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content
    return content[end + 3:].strip()
