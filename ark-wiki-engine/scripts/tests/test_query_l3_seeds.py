"""回歸測試 —— L3 圖譜擴散不可讓種子輸給鄰居（3.3.0，fish-bot 2026-11-13 回報）

## 回報的問題

舊 layer3() 把種子（L0＋L1 前 3 名）排除在 L3 之外：種子只拿 L1 一層 RRF 分數，
而種子的鄰居只要在 L1 有任何名次就拿兩層。RRF k=60 把名次差壓平 → 兩層必勝一層，
最相關的頁輸給樞紐頁（fish-bot 實測：查「逐發對照彙整」，L1 第 2 名的 parity-testing 掉出前 6）。

## 修正

種子也進 L3 且排在所有鄰居前 → 種子與鄰居都拿兩層，L1 的相對順序保留；鄰居仍可藉 L3 加分補召回。
反證：把 layer3 換回舊版（種子不進 L3）→ 本測試必紅（test_old_behaviour_fails 直接驗）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import wiki_query  # noqa: E402


def _page(wiki: Path, name: str, body: str, links: list[str]) -> None:
    (wiki / f"{name}.md").write_text(
        f"---\ntitle: \"{name}\"\ntype: concept\ntags: [a]\nsources: [raw/x.md]\nrelated: [overview]\n"
        f"created: 2026-11-17\nupdated: 2026-11-17\nstatus: seedling\ntrust: deterministic\napproved: false\n---\n\n"
        f"# {name}\n\n{body}\n\n" + " ".join(f"[[{l}]]" for l in links) + "\n", encoding="utf-8")


def _fixture(wiki: Path) -> None:
    # A、B：強命中（正確答案）；C：中等命中；hub1／hub2：弱命中但連到 A、B（樞紐頁）；其餘雜訊頁
    _page(wiki, "a-parity", "parity reconcile parity reconcile parity reconcile report", ["hub1", "hub2"])
    _page(wiki, "b-parity", "parity reconcile parity reconcile summary", ["hub1", "hub2"])
    _page(wiki, "c-other", "parity notes", [])
    _page(wiki, "hub1", "knowledge map index of everything mentions reconcile once " + "filler " * 40, ["a-parity", "b-parity"])
    _page(wiki, "hub2", "overview hub mentions parity once " + "filler " * 40, ["a-parity", "b-parity"])
    for i in range(6):
        _page(wiki, f"noise{i}", "unrelated topic " * 5, [])


def _query(wiki: Path, layers: str | None = None) -> list[str]:
    cmd = [sys.executable, str(SCRIPTS / "wiki_query.py"), "--wiki_dir", str(wiki), "--query", "parity reconcile", "--top_k", "5"]
    if layers:
        cmd += ["--layers", layers]
    out = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    return [r.get("page") or r.get("path") or r.get("id") for r in out["results"]]


def test_seeds_stay_ahead_of_neighbours(tmp_path):
    _fixture(tmp_path)
    l1 = _query(tmp_path, "L1")
    assert l1[:2] == ["a-parity", "b-parity"], l1          # 前提：BM25 自己排對
    full = _query(tmp_path)
    assert full[:2] == ["a-parity", "b-parity"], full       # 開了 L3 也不能被樞紐頁蓋過
    assert full.index("a-parity") < full.index("hub1") and full.index("b-parity") < full.index("hub2")


def test_old_behaviour_fails(tmp_path, monkeypatch):
    """反證：換回舊 layer3（種子不進 L3）→ 樞紐頁超車，證明上面的測試真的在驗這件事。"""
    _fixture(tmp_path)

    def old_layer3(seed_pids, graph, wiki_dir, metadata):
        neigh = {}
        g = graph
        if g is None:
            return []
        for rank, pid in enumerate(seed_pids):
            for nb in g.get("out", {}).get(pid, []) + g.get("in", {}).get(pid, []):
                if nb not in seed_pids:
                    neigh[nb] = max(neigh.get(nb, 0.0), 1.0 / (rank + 1))
        return sorted(neigh.items(), key=lambda kv: -kv[1])

    # 無索引 → graph 現場解析；先拿新版算出的 graph 給舊函式用
    real = wiki_query.layer3
    captured = {}

    def spy(seed_pids, graph, wiki_dir, metadata):
        if graph is None:
            slug = {m["slug"]: p for p, m in metadata.items()}
            out, inn = {}, {p: [] for p in metadata}
            for pid, m in metadata.items():
                links = [l if l in metadata else slug.get(l) for l in wiki_query.extract_wikilinks(wiki_query._page_text(wiki_dir, m))]
                out[pid] = [l for l in links if l and l != pid]
                for l in out[pid]:
                    inn.setdefault(l, []).append(pid)
            graph = {"out": out, "in": inn}
        captured["new"] = real(seed_pids, graph, wiki_dir, metadata)
        return old_layer3(seed_pids, graph, wiki_dir, metadata)

    monkeypatch.setattr(wiki_query, "layer3", spy)
    lr = {"L1": [("a-parity", 9.0), ("b-parity", 8.0), ("c-other", 3.0), ("hub1", 1.0), ("hub2", 0.9)]}
    seeds = [p for p, _ in lr["L1"]][:3]
    lr["L3"] = wiki_query.layer3(seeds, None, tmp_path, {p: {"slug": p, "file": f"{p}.md", "path": f"{p}.md"} for p in ["a-parity", "b-parity", "c-other", "hub1", "hub2"]})
    fused = wiki_query.rrf(lr)
    order = sorted(fused, key=lambda p: -fused[p]["score"])
    assert order.index("hub1") < order.index("a-parity"), f"舊行為應讓樞紐頁超車：{order}"
    lr["L3"] = captured["new"]
    fused = wiki_query.rrf(lr)
    order = sorted(fused, key=lambda p: -fused[p]["score"])
    assert order[:2] == ["a-parity", "b-parity"], order
