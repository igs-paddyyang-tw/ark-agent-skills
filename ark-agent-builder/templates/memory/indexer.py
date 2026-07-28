"""Memory FTS5 索引：建表、增量更新、重建。

索引位置：data/memory.db
涵蓋：memory/daily/*.md + memory/memory.md + knowledge/wiki/*.md + .kiro/skills/*/SKILL.md
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "memory.db"

# 來源類型
SOURCE_DAILY = "daily"
SOURCE_MEMORY = "memory"
SOURCE_WIKI = "wiki"
SOURCE_SKILL = "skill"


def get_connection() -> sqlite3.Connection:
    """取得 memory.db 連線，自動建表。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_table(conn)
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    """確保 FTS5 虛擬表存在。"""
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
            agent,
            source,
            date,
            title,
            body,
            tags,
            content='',
            tokenize='unicode61'
        )
    """)
    # 輔助表：追蹤已索引的檔案 mtime（增量更新用）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indexed_files (
            path TEXT PRIMARY KEY,
            mtime REAL,
            agent TEXT,
            source TEXT
        )
    """)
    conn.commit()


def index_agent(agent_name: str, agents_dir: Path | None = None) -> int:
    """索引單一 Agent 的 memory + skills，回傳新增/更新筆數。"""
    if agents_dir is None:
        agents_dir = BASE_DIR / "agents"

    agent_path = agents_dir / agent_name
    conn = get_connection()
    count = 0

    # 1. Daily logs
    daily_dir = agent_path / "memory" / "daily"
    if daily_dir.exists():
        for md_file in daily_dir.glob("*.md"):
            count += _index_file(conn, md_file, agent_name, SOURCE_DAILY)

    # 2. memory.md
    memory_file = agent_path / "memory" / "memory.md"
    if memory_file.exists():
        count += _index_file(conn, memory_file, agent_name, SOURCE_MEMORY)

    # 3. Skills（只索引 name + description，不索引完整本體）
    skills_dir = agent_path / ".kiro" / "skills"
    if skills_dir.exists():
        for skill_file in skills_dir.rglob("SKILL.md"):
            count += _index_skill(conn, skill_file, agent_name)

    conn.commit()
    conn.close()
    log.info("Indexed %s: %d entries updated", agent_name, count)
    return count


def index_shared_wiki(knowledge_dir: Path | None = None) -> int:
    """索引共用知識庫 wiki 頁面。"""
    if knowledge_dir is None:
        knowledge_dir = BASE_DIR / "knowledge"

    conn = get_connection()
    count = 0

    # shared wiki
    shared_wiki = knowledge_dir / "shared" / "wiki"
    if shared_wiki.exists():
        for md_file in shared_wiki.rglob("*.md"):
            count += _index_file(conn, md_file, "_shared", SOURCE_WIKI)

    conn.commit()
    conn.close()
    log.info("Indexed shared wiki: %d entries updated", count)
    return count


def rebuild_all() -> dict[str, int]:
    """完整重建所有索引。"""
    conn = get_connection()
    conn.execute("DELETE FROM mem_fts")
    conn.execute("DELETE FROM indexed_files")
    conn.commit()
    conn.close()

    results: dict[str, int] = {}
    agents_dir = BASE_DIR / "agents"

    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and agent_dir.name.endswith("-agent"):
                results[agent_dir.name] = index_agent(agent_dir.name)

    results["_shared_wiki"] = index_shared_wiki()
    results["_default"] = index_default_memory()
    return results


def _index_file(
    conn: sqlite3.Connection,
    file_path: Path,
    agent: str,
    source: str,
) -> int:
    """索引一個 markdown 檔案（增量：只在 mtime 變化時更新）。"""
    path_str = str(file_path.resolve())
    mtime = file_path.stat().st_mtime

    # 檢查是否需要更新
    row = conn.execute(
        "SELECT mtime FROM indexed_files WHERE path = ?", (path_str,)
    ).fetchone()
    if row and row[0] == mtime:
        return 0  # 未變更

    # 刪除舊索引
    conn.execute(
        "DELETE FROM mem_fts WHERE agent = ? AND title = ?",
        (agent, path_str),
    )

    # 讀取並解析
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    entries = _parse_entries(content, file_path, source)

    # 寫入 FTS5
    for entry in entries:
        conn.execute(
            "INSERT INTO mem_fts (agent, source, date, title, body, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (agent, source, entry["date"], entry["title"], entry["body"], entry["tags"]),
        )

    # 更新追蹤
    conn.execute(
        "INSERT OR REPLACE INTO indexed_files (path, mtime, agent, source) VALUES (?, ?, ?, ?)",
        (path_str, mtime, agent, source),
    )

    return len(entries)


def _index_skill(conn: sqlite3.Connection, skill_file: Path, agent: str) -> int:
    """索引 Skill 的 name + description（不索引完整本體）。"""
    path_str = str(skill_file.resolve())
    mtime = skill_file.stat().st_mtime

    row = conn.execute(
        "SELECT mtime FROM indexed_files WHERE path = ?", (path_str,)
    ).fetchone()
    if row and row[0] == mtime:
        return 0

    conn.execute(
        "DELETE FROM mem_fts WHERE agent = ? AND source = ? AND title = ?",
        (agent, SOURCE_SKILL, path_str),
    )

    content = skill_file.read_text(encoding="utf-8", errors="ignore")
    # 從 frontmatter 取 name + description
    name = _extract_frontmatter(content, "name") or skill_file.parent.name
    description = _extract_frontmatter(content, "description") or ""

    conn.execute(
        "INSERT INTO mem_fts (agent, source, date, title, body, tags) VALUES (?, ?, ?, ?, ?, ?)",
        (agent, SOURCE_SKILL, datetime.now().strftime("%Y-%m-%d"), name, description, "skill"),
    )
    conn.execute(
        "INSERT OR REPLACE INTO indexed_files (path, mtime, agent, source) VALUES (?, ?, ?, ?)",
        (path_str, mtime, agent, SOURCE_SKILL),
    )
    return 1


def _parse_entries(content: str, file_path: Path, source: str) -> list[dict]:
    """將 markdown 內容解析為索引條目。

    Daily log：以 ## 開頭的每個段落為一筆。
    其他：整個檔案為一筆。
    """
    # 從檔名推斷日期
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
    file_date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")

    if source == SOURCE_DAILY:
        # 按 ## 切分為多筆
        sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
        entries = []
        for section in sections:
            section = section.strip()
            if not section or section.startswith("#") and not section.startswith("##"):
                continue
            # 取第一行作為 title
            lines = section.split("\n")
            title = lines[0].lstrip("# ").strip()
            body = "\n".join(lines[1:]).strip()
            # 提取 tags
            tags = ""
            tags_match = re.search(r"tags?:\s*(.+)", body, re.IGNORECASE)
            if tags_match:
                tags = tags_match.group(1).strip()
            entries.append({
                "date": file_date,
                "title": title,
                "body": body[:2000],  # 截斷
                "tags": tags,
            })
        return entries if entries else [{
            "date": file_date,
            "title": file_path.stem,
            "body": content[:2000],
            "tags": "",
        }]
    else:
        # 整檔為一筆
        title = file_path.stem
        # 嘗試從第一行 # 取標題
        first_heading = re.match(r"^#\s+(.+)", content)
        if first_heading:
            title = first_heading.group(1).strip()
        return [{
            "date": file_date,
            "title": title,
            "body": content[:2000],
            "tags": "",
        }]


def _extract_frontmatter(content: str, key: str) -> str | None:
    """從 YAML frontmatter 提取指定 key 的值。"""
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return None
    fm = fm_match.group(1)
    pattern = re.compile(rf"^{key}:\s*(.+)", re.MULTILINE)
    m = pattern.search(fm)
    if m:
        value = m.group(1).strip().strip("\"'")
        return value
    return None


def index_default_memory() -> int:
    """索引根目錄 memory/（Default 模式的 daily log + memory.md）。"""
    conn = get_connection()
    count = 0

    # Daily logs
    daily_dir = BASE_DIR / "memory" / "daily"
    if daily_dir.exists():
        for md_file in daily_dir.glob("*.md"):
            count += _index_file(conn, md_file, "_default", SOURCE_DAILY)

    # memory.md
    memory_file = BASE_DIR / "memory" / "memory.md"
    if memory_file.exists():
        count += _index_file(conn, memory_file, "_default", SOURCE_MEMORY)

    conn.commit()
    conn.close()
    log.info("Indexed _default memory: %d entries updated", count)
    return count
