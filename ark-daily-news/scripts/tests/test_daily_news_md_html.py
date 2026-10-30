"""ark-daily-news 行為測試：news_md_writer（Content 軌）與 render_news_html（View 軌）。

驗證：必要欄位守門、拒絕覆蓋、guard 狀態不被靜默吞掉、MD → HTML 往返不掉欄位、
HTML 逸出與零外部請求檢查。全部在 tmp_path，不打網路；wiki_guard 以 monkeypatch 替身。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import news_md_writer as W  # noqa: E402
import render_news_html as R  # noqa: E402

DATE = "2026-08-13"
ITEMS = [
    {"topic": "AI 焦點", "title": "模型 A < B 的評測", "source": "Example News", "url": "https://example.com/a",
     "news_date": "2026-08-12", "what": "某實驗室發布評測，A & B 差距縮小。", "why": "影響我們的選型。",
     "summary": "差距在縮小", "urgency": "立即", "action": "週五前重跑內部評測",
     "tags": [{"icon": "🤖", "text": "LLM"}, "評測"]},
    {"topic": "雲端", "title": "某雲端降價", "source": "Cloud Blog", "what": "GPU 時價下調 20%。",
     "why": "訓練成本下降。", "urgency": "超緊急"},
]


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=60)


# ── news_md_writer ──────────────────────────────────


def test_write_md_to_digest_tree_and_refuse_overwrite(tmp_path):
    """正常路徑：寫到 knowledge/raw/digest/<issue>/<date>.md、frontmatter 契約齊全；
    同日再寫不加 --force → 拒絕（exit 1）且內容不變；加 --force 才覆蓋。"""
    src = tmp_path / "items.json"
    src.write_text(json.dumps(ITEMS, ensure_ascii=False), encoding="utf-8")
    args = ["--json", str(src), "--issue", "tech", "--date", DATE, "--root", str(tmp_path), "--no-guard"]
    r = run("news_md_writer.py", *args)
    assert r.returncode == 0, r.stdout
    out = tmp_path / "knowledge" / "raw" / "digest" / "tech" / f"{DATE}.md"
    md = out.read_text(encoding="utf-8")
    for line in ("type: digest-raw", "issue_type: tech", f"date: {DATE}", "collected: 2",
                 "sources: [Cloud Blog, Example News]", "guard: skipped", "generated_by: ark-daily-news"):
        assert line in md
    assert "**緊急度**：一般" in md  # 不合法的「超緊急」降為一般
    assert f"**日期**：{DATE}" in md  # 缺 news_date 用出刊日補

    out.write_text("排程管線寫的", encoding="utf-8")
    r = run("news_md_writer.py", *args)
    assert r.returncode == 1 and "--force" in r.stdout
    assert out.read_text(encoding="utf-8") == "排程管線寫的"
    assert run("news_md_writer.py", *args, "--force").returncode == 0
    assert "排程管線寫的" not in out.read_text(encoding="utf-8")


def test_write_rejects_missing_why_bad_url_and_unknown_issue(tmp_path):
    """反例：缺 why（只是轉述）、url 非 http(s)、未知刊別 → error，且不落檔。"""
    bad = [{"title": "t", "what": "w", "url": "ftp://x"}]
    r = W.write(bad, issue="tech", date=DATE, root=tmp_path, guard=False)
    assert r["status"] == "error"
    assert any("`why`" in i for i in r["issues"]) and any("不是 http(s)" in i for i in r["issues"])
    assert W.write(ITEMS, issue="sports", date=DATE, root=tmp_path, guard=False)["status"] == "error"
    assert not (tmp_path / "knowledge").exists()


def test_guard_fail_blocks_write_and_unavailable_is_flagged(tmp_path, monkeypatch):
    """guard 未通過 → 不寫檔、暫存檔不留；guard 不可用 → 照寫但 frontmatter 標 unavailable 並附警告（不當作通過）。"""
    monkeypatch.setattr(W, "run_guard", lambda p, **k: "fail:injection detected")
    r = W.write(ITEMS, issue="tech", date=DATE, root=tmp_path)
    d = tmp_path / "knowledge" / "raw" / "digest" / "tech"
    assert r["status"] == "error" and "wiki_guard 未通過" in r["message"]
    assert list(d.iterdir()) == []

    monkeypatch.setattr(W, "run_guard", lambda p, **k: "unavailable")
    r = W.write(ITEMS, issue="tech", date=DATE, root=tmp_path)
    md = (d / f"{DATE}.md").read_text(encoding="utf-8")
    assert r["guard"] == "unavailable" and "guard: unavailable" in md and "本檔未經 wiki_guard 檢查" in md


def test_find_project_root_walks_up_to_sentinel(tmp_path):
    """邊界：在深層 agent 目錄執行時，以 knowledge/ 哨兵往上找到專案根，而不是寫在 cwd。"""
    (tmp_path / "knowledge").mkdir()
    deep = tmp_path / "agents" / "x" / "work"
    deep.mkdir(parents=True)
    assert W.find_project_root(deep) == tmp_path.resolve()


# ── render_news_html ───────────────────────────────


def test_md_roundtrip_renders_escaped_offline_html(tmp_path):
    """MD → HTML：欄位往返不掉、`<` `&` 被逸出、「立即」卡掛 urgent、行動彙總出現、
    樣板佔位符全被替換、維護者註解被剝除、零外部請求。"""
    W.write(ITEMS, issue="tech", date=DATE, root=tmp_path, guard=False)
    md_p = tmp_path / "knowledge" / "raw" / "digest" / "tech" / f"{DATE}.md"
    fm, items = R.parse_md(md_p.read_text(encoding="utf-8"))
    assert fm["issue_type"] == "tech" and fm["date"] == DATE
    assert [i["title"] for i in items] == ["模型 A < B 的評測", "某雲端降價"]
    assert items[0]["action"] == "週五前重跑內部評測" and items[0]["tags"] == ["🤖 LLM", "評測"]
    assert items[0]["url"] == "https://example.com/a" and "url" not in items[1]

    out = tmp_path / "out.html"
    r = run("render_news_html.py", "--md", str(md_p), "--out", str(out))
    assert r.returncode == 0, r.stdout
    page = out.read_text(encoding="utf-8")
    assert "模型 A &lt; B 的評測" in page and "A &amp; B" in page
    assert 'class="card urgent"' in page and "今日行動彙總" in page
    assert "{{" not in page and "<!--" not in page
    assert "週四" in page and "#0E7C7B" in page
    assert R.check_offline(page) == []


def test_check_offline_flags_external_resources():
    """反例：遠端 src、<script src>、@import 字體都要被抓出來（附件離線開啟會破版）。"""
    bad = ('<style>@import url(https://fonts.example/x.css);</style>'
           '<script src="https://cdn.example/x.js"></script><img src="https://img.example/a.png">')
    v = R.check_offline(bad)
    assert any("@import" in x for x in v) and any("<script src>" in x for x in v)
    assert any("img.example" in x for x in v)
    assert R.check_offline('<a href="https://example.com">ok</a>') == []


def test_render_empty_md_fails(tmp_path):
    """邊界：MD 沒有任何 `## N.` 條目 → 回 error（exit 1），不產空白日報。"""
    p = tmp_path / "empty.md"
    p.write_text("---\nissue_type: tech\ndate: 2026-08-13\n---\n\n# 空\n", encoding="utf-8")
    r = run("render_news_html.py", "--md", str(p), "--out", str(tmp_path / "o.html"))
    assert r.returncode == 1 and "沒有可渲染的項目" in r.stdout
    assert not (tmp_path / "o.html").exists()


def test_render_from_json_list_and_articles_dict(tmp_path):
    """JSON 入口：SKILL 步驟一的 list[dict] 與 {"articles": [...]} 兩種形狀都能直接渲染。"""
    for name, payload in (("list.json", ITEMS), ("dict.json", {"articles": ITEMS})):
        src = tmp_path / name
        src.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        out = tmp_path / f"{name}.html"
        r = run("render_news_html.py", "--json", str(src), "--date", DATE, "--out", str(out))
        assert r.returncode == 0, r.stdout
        assert "某雲端降價" in out.read_text(encoding="utf-8")
