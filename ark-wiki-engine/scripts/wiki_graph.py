"""wiki_graph.py — Wiki 知識圖譜分析

用途：解析所有 [[wikilink]]，產出圖譜分析報告。
識別 hub（高連結）、orphan（孤立）、cluster（群組）。

使用方式：
    python scripts/wiki_graph.py --wiki_dir knowledge/wiki

    # 輸出 Mermaid 圖（可貼到 Markdown）
    python scripts/wiki_graph.py --wiki_dir knowledge/wiki --mermaid

    # JSON 輸出
    python scripts/wiki_graph.py --wiki_dir knowledge/wiki --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def extract_wikilinks(content: str) -> list[str]:
    """提取所有 [[wikilink]]。"""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def build_graph(wiki_dir: Path) -> dict:
    """建構 wikilink 圖譜。"""
    md_files = list(wiki_dir.rglob("*.md"))

    nodes: dict[str, dict] = {}  # page_name → {path, outbound, inbound}
    edges: list[tuple[str, str]] = []

    # 收集所有節點
    for f in md_files:
        page_name = f.stem
        content = f.read_text(encoding="utf-8", errors="replace")
        links = extract_wikilinks(content)
        nodes[page_name] = {
            "path": str(f.relative_to(wiki_dir)),
            "outbound": links,
            "inbound": [],
            "out_degree": len(links),
            "in_degree": 0,
        }
        for target in links:
            edges.append((page_name, target))

    # 計算 inbound
    for source, target in edges:
        if target in nodes:
            nodes[target]["inbound"].append(source)
            nodes[target]["in_degree"] += 1

    return {"nodes": nodes, "edges": edges}


def analyze(graph: dict) -> dict:
    """分析圖譜：hub / orphan / 統計。"""
    nodes = graph["nodes"]
    edges = graph["edges"]

    # Hub：inbound >= 3
    hubs = sorted(
        [(name, n["in_degree"]) for name, n in nodes.items() if n["in_degree"] >= 3],
        key=lambda x: x[1], reverse=True
    )

    # Orphan：in_degree == 0 且 out_degree == 0
    orphans = [name for name, n in nodes.items()
               if n["in_degree"] == 0 and n["out_degree"] == 0]

    # Isolated：in_degree == 0（但有 outbound）
    isolated = [name for name, n in nodes.items()
                if n["in_degree"] == 0 and n["out_degree"] > 0 and name != "overview"]

    # Broken links（指向不存在的頁面）
    broken = set()
    for source, target in edges:
        if target not in nodes:
            broken.add(target)

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "hubs": hubs,
        "orphans": orphans,
        "isolated": isolated,
        "broken_links": sorted(broken),
        "avg_degree": sum(n["out_degree"] for n in nodes.values()) / max(len(nodes), 1),
    }


def to_mermaid(graph: dict) -> str:
    """產出 Mermaid flowchart。"""
    lines = ["```mermaid", "graph LR"]
    seen_edges = set()
    for source, target in graph["edges"]:
        edge_key = f"{source}-->{target}"
        if edge_key not in seen_edges:
            # sanitize node names for mermaid
            s = source.replace("-", "_")
            t = target.replace("-", "_")
            lines.append(f"    {s}[{source}] --> {t}[{target}]")
            seen_edges.add(edge_key)
    lines.append("```")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Graph — 知識圖譜分析")
    p.add_argument("--wiki_dir", required=True, help="wiki/ 目錄路徑")
    p.add_argument("--mermaid", action="store_true", help="輸出 Mermaid 圖")
    p.add_argument("--json", action="store_true", help="JSON 格式輸出")
    args = p.parse_args()

    wiki_dir = Path(args.wiki_dir)
    if not wiki_dir.exists():
        print(f"[ERROR] 目錄不存在：{wiki_dir}", file=sys.stderr)
        sys.exit(1)

    graph = build_graph(wiki_dir)
    analysis = analyze(graph)

    if args.json:
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
        return

    if args.mermaid:
        print(to_mermaid(graph))
        return

    # Human-readable
    print(f"📊 Wiki Graph: {analysis['total_nodes']} nodes, {analysis['total_edges']} edges")
    print(f"   平均 out-degree: {analysis['avg_degree']:.1f}\n")

    if analysis["hubs"]:
        print("🌟 Hub 頁面（inbound ≥ 3）:")
        for name, degree in analysis["hubs"]:
            print(f"  {name} (← {degree} pages)")
        print()

    if analysis["orphans"]:
        print("🏝️  完全孤立（無 link）:")
        for name in analysis["orphans"]:
            print(f"  {name}")
        print()

    if analysis["isolated"]:
        print("📭 無 inbound（有 outbound 但沒人連到它）:")
        for name in analysis["isolated"]:
            print(f"  {name}")
        print()

    if analysis["broken_links"]:
        print("🔗 斷裂 link（指向不存在的頁面）:")
        for name in analysis["broken_links"]:
            print(f"  [[{name}]]")
        print()

    if not analysis["orphans"] and not analysis["broken_links"]:
        print("✅ 圖譜健康，無孤立或斷裂。")


if __name__ == "__main__":
    main()
