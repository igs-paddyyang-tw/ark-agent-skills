"""CLI：完整重建 memory FTS5 索引。

Usage:
    python -m src.memory.rebuild_index
"""
from __future__ import annotations

import sys
from pathlib import Path

# 確保專案根目錄在 path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> None:
    from src.memory.indexer import rebuild_all

    print("🔄 重建 Memory FTS5 索引...")
    results = rebuild_all()

    total = sum(results.values())
    print(f"\n✅ 完成！共索引 {total} 筆：")
    for name, count in sorted(results.items()):
        print(f"   {name}: {count}")


if __name__ == "__main__":
    main()
