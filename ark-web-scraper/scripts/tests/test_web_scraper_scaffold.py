"""ark-web-scraper 行為測試 —— scaffold_scraper.py 產出的骨架與其程式行為。

## 驗什麼

1. scaffold：產出 6 個檔、Python 檔都能 parse、news_sources.yaml 結構完整；
   重跑**不覆蓋**使用者改過的檔；沒給 project_dir → exit 1。
2. 產出的 skill 程式本身（不打網路）：以 stub 取代宿主專案的 `src.skills.base` 與
   `scrapling.fetchers`，直接執行產出的 WebScraperSkill／NewsParserSkill：
   - auto fetcher 被 403 擋時要退到 StealthyFetcher
   - selector 擷取帶出 href、max_items 截斷
   - news_parser 把項目寫成帶 frontmatter 的 Markdown

stub 全以 monkeypatch.setitem(sys.modules, ...) 注入，測試結束自動還原。
"""
from __future__ import annotations

import ast
import asyncio
import enum
import importlib.util
import subprocess
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import scaffold_scraper as ss  # noqa: E402

pydantic = pytest.importorskip("pydantic")  # 產出的 skill 參數用 pydantic


# ── scaffold 本身 ────────────────────────────────────────────

def test_scaffold_creates_parseable_files(tmp_path):
    """產出 FILES 清單的全部檔案；每個 .py 都能被 ast.parse；sources 設定每筆有 name/url/selector。"""
    created = ss.scaffold(tmp_path)
    assert sorted(created) == sorted(ss.FILES) and len(created) == 6
    for rel in created:
        if rel.endswith(".py"):
            ast.parse((tmp_path / rel).read_text(encoding="utf-8"), filename=rel)
    cfg = yaml.safe_load((tmp_path / "config/news_sources.yaml").read_text(encoding="utf-8"))
    assert cfg["sources"] and all({"name", "url", "selector"} <= set(s) for s in cfg["sources"])


def test_rerun_preserves_user_edits(tmp_path):
    """重跑 scaffold 不得覆蓋已存在的檔（使用者可能改過）；只補缺的。"""
    ss.scaffold(tmp_path)
    edited = tmp_path / "src/skills/internal/web_scraper.py"
    edited.write_text("# 我改過\n", encoding="utf-8")
    (tmp_path / "config/news_sources.yaml").unlink()
    assert ss.scaffold(tmp_path) == ["config/news_sources.yaml"]
    assert edited.read_text(encoding="utf-8") == "# 我改過\n"


def test_cli_without_project_dir_exits_1(tmp_path):
    """沒給 project_dir → 印用法、exit 1，且不在 cwd 產任何檔。"""
    r = subprocess.run([sys.executable, str(SCRIPTS / "scaffold_scraper.py")], cwd=tmp_path,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and "使用方式" in r.stdout
    assert list(tmp_path.iterdir()) == []


# ── 產出程式的行為（stub 宿主框架與 scrapling）────────────────

@dataclass
class _Result:
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None


class _El:
    def __init__(self, text: str, href: str = ""):
        self._t, self.attrib = text, ({"href": href} if href else {})

    def text(self) -> str:
        return self._t


class _Page:
    def __init__(self, status: int, body: str = "", elements: list | None = None):
        self.status, self._body, self._els = status, body, elements or []

    def text(self) -> str:
        return self._body

    def css(self, selector, **kw):
        return list(self._els)


@pytest.fixture
def gen(tmp_path, monkeypatch):
    """scaffold 到 tmp_path，注入 stub 模組，回傳 (載入產出模組的函式, fetcher 呼叫紀錄)。"""
    ss.scaffold(tmp_path)

    base = types.ModuleType("src.skills.base")
    base.BaseSkill = object
    base.SkillParam = pydantic.BaseModel
    base.SkillResult = _Result
    base.SkillType = enum.Enum("SkillType", "PYTHON")
    for name in ("src", "src.skills"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "src.skills.base", base)

    calls: list[str] = []
    fetchers = types.ModuleType("scrapling.fetchers")

    class Fetcher:
        page = _Page(403, "blocked")

        @staticmethod
        def get(url, **kw):
            calls.append("fast")
            return Fetcher.page

    class StealthyFetcher:
        page = _Page(200, "ok" * 100, [_El("A", "/a"), _El("B"), _El("C", "/c")])

        @staticmethod
        def fetch(url, **kw):
            calls.append("stealth")
            return StealthyFetcher.page

    fetchers.Fetcher, fetchers.StealthyFetcher, fetchers.DynamicFetcher = Fetcher, StealthyFetcher, StealthyFetcher
    monkeypatch.setitem(sys.modules, "scrapling", types.ModuleType("scrapling"))
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", fetchers)

    def load(stem: str):
        path = tmp_path / "src/skills/internal" / f"{stem}.py"
        spec = importlib.util.spec_from_file_location(f"ws_generated_{stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    return load, calls, Fetcher


def test_auto_fetcher_falls_back_on_403_and_extracts(gen):
    """auto 模式：Fetcher 回 403 → 改用 StealthyFetcher；selector 擷取帶 href，max_items 截斷。"""
    load, calls, _ = gen
    skill = load("web_scraper").WebScraperSkill()
    res = asyncio.run(skill.execute({"url": "https://example.invalid", "selector": "li", "max_items": 2}))
    assert res.success, res.error
    assert calls == ["fast", "stealth"]
    assert res.data["count"] == 2
    assert res.data["items"] == [{"text": "A", "href": "/a"}, {"text": "B"}]
    assert res.data["status_code"] == 200


def test_auto_fetcher_keeps_fast_result_when_ok(gen):
    """邊界：Fetcher 回 200 且內容 ≥ 100 字 → 不升級成 stealth；無 selector 時回整頁文字。"""
    load, calls, fast = gen
    fast.page = _Page(200, "x" * 150)
    res = asyncio.run(load("web_scraper").WebScraperSkill().execute({"url": "https://example.invalid"}))
    assert res.success and calls == ["fast"]
    assert res.data["items"] == [{"text": "x" * 150}]


def test_invalid_params_return_failure_not_raise(gen):
    """反例：缺必填 url → 回 success=False 與錯誤訊息，不把例外丟給呼叫端。"""
    load, calls, _ = gen
    res = asyncio.run(load("web_scraper").WebScraperSkill().execute({"selector": "li"}))
    assert not res.success and "爬取失敗" in res.error
    assert calls == []


def test_news_parser_writes_frontmatter_markdown(gen, tmp_path):
    """news_parser：每個項目一個 md，含 source/url frontmatter 與標題。"""
    load, _, _ = gen
    out = tmp_path / "raw"
    res = asyncio.run(load("news_parser").NewsParserSkill().execute({
        "items": [{"title": "Hello World", "href": "https://e.invalid/1", "text": "內文"}],
        "output_dir": str(out), "source": "unit"}))
    assert res.success and res.data["count"] == 1
    md = Path(res.data["files"][0])
    assert md.name.endswith("-hello-world.md")
    text = md.read_text(encoding="utf-8")
    assert text.startswith("---\nsource: unit\n") and "url: https://e.invalid/1" in text
    assert "# Hello World" in text


@pytest.mark.xfail(strict=True, reason=(
    "news_parser 的 slug 只把空白換成 -，標題含 `/`（如 'AI/ML 週報'）時檔名變成子路徑，"
    "write_text 因目錄不存在失敗 → 整批 success=False，同批其他文章也不落檔"))
def test_news_parser_title_with_slash(gen, tmp_path):
    """標題含 `/` 仍應成功落檔（slug 應消毒路徑分隔符）。"""
    load, _, _ = gen
    res = asyncio.run(load("news_parser").NewsParserSkill().execute({
        "items": [{"title": "AI/ML 週報", "text": "x"}], "output_dir": str(tmp_path / "raw")}))
    assert res.success, res.error
