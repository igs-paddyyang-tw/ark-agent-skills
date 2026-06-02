---
author: paddyyang
name: ark-web-scraper
description: |
  產出進階網頁爬蟲 Skill，基於 Scrapling 框架。
  支援自適應元素追蹤（網站改版自動重新定位）、反爬繞過（Cloudflare Turnstile）、
  三種 Fetcher 模式（HTTP/隱身/動態瀏覽器）、Spider 大規模爬取、Proxy 輪換。
  使用此 Skill 當使用者提及網頁抓取、爬蟲、web scraping、
  抓取網頁、擷取網頁內容、反爬、Cloudflare 繞過、大規模爬取、
  自適應爬蟲、Scrapling、或任何需要從網頁取得資料的場景。
---

# ark-web-scraper

產出 `src/skills/internal/web_scraper.py`，基於 Scrapling 的進階網頁爬蟲，可獨立運作。

## 觸發條件

- 「網頁抓取」、「爬蟲」、「web scraping」
- 「抓取網頁」、「擷取網頁內容」
- 「反爬」、「Cloudflare 繞過」、「隱身爬蟲」
- 「大規模爬取」、「Spider」、「自適應」

## 核心概念

```
Scrapling 三層架構：
  Fetcher（HTTP 快速）→ StealthyFetcher（反爬繞過）→ DynamicFetcher（完整瀏覽器）
                              ↓
  Parser（自適應元素追蹤 — 網站改版後自動重新定位目標元素）
                              ↓
  Spider（大規模並發爬取 — 暫停/恢復/串流/Proxy 輪換）
```

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `url` | `str` | ✅ | — | 目標網址 |
| `selector` | `str` | ❌ | `None` | CSS selector（提取特定元素） |
| `xpath` | `str` | ❌ | `None` | XPath selector（替代 CSS） |
| `extract` | `str` | ❌ | `"text"` | 提取方式：`text` / `html` / `attrs` / `markdown` |
| `fetcher` | `str` | ❌ | `"auto"` | Fetcher 模式：`fast` / `stealth` / `dynamic` / `auto` |
| `adaptive` | `bool` | ❌ | `False` | 啟用自適應元素追蹤（網站改版自動定位） |
| `auto_save` | `bool` | ❌ | `False` | 儲存元素特徵供後續 adaptive 使用 |
| `headless` | `bool` | ❌ | `True` | 瀏覽器模式是否無頭 |
| `proxy` | `str` | ❌ | `None` | Proxy URL |
| `headers` | `dict` | ❌ | `{}` | 自訂 HTTP headers |
| `max_items` | `int` | ❌ | `50` | 最大提取數量 |
| `timeout` | `int` | ❌ | `30` | 請求超時（秒） |
| `solve_cloudflare` | `bool` | ❌ | `False` | 自動解決 Cloudflare challenge |

## 產出檔案

- `src/skills/internal/web_scraper.py`

---

## 產出指引

### 步驟 1：參數模型

```python
from pydantic import Field
from src.skills.base import SkillParam

class WebScraperParams(SkillParam):
    """Web Scraper 輸入參數。"""
    url: str = Field(description="目標網址")
    selector: str | None = Field(default=None, description="CSS selector")
    xpath: str | None = Field(default=None, description="XPath selector")
    extract: str = Field(default="text", description="提取方式：text/html/attrs/markdown")
    fetcher: str = Field(default="auto", description="Fetcher 模式：fast/stealth/dynamic/auto")
    adaptive: bool = Field(default=False, description="啟用自適應元素追蹤")
    auto_save: bool = Field(default=False, description="儲存元素特徵")
    headless: bool = Field(default=True, description="無頭模式")
    proxy: str | None = Field(default=None, description="Proxy URL")
    headers: dict = Field(default_factory=dict, description="自訂 headers")
    max_items: int = Field(default=50, description="最大提取數量")
    timeout: int = Field(default=30, description="超時秒數")
    solve_cloudflare: bool = Field(default=False, description="解決 Cloudflare")
```

### 步驟 2：Skill 類別

```python
class WebScraperSkill(BaseSkill):
    skill_id = "web_scraper"
    skill_type = SkillType.PYTHON
    description = "進階網頁爬蟲（Scrapling）：自適應追蹤 + 反爬繞過 + 三種 Fetcher"
    version = "2.0.0"
    input_schema = WebScraperParams
```

### 步驟 3：execute 方法

```python
async def execute(self, params: dict) -> SkillResult:
    try:
        p = WebScraperParams(**params)
        page = await self._fetch(p)
        items = self._extract(page, p)
        return SkillResult(success=True, data={
            "items": items[:p.max_items],
            "count": len(items),
            "url": p.url,
            "status_code": page.status,
            "fetcher_used": p.fetcher,
        })
    except Exception as e:
        return SkillResult(success=False, error=f"爬取失敗: {e}")
```

### 步驟 4：Fetcher 選擇邏輯

```python
async def _fetch(self, p: WebScraperParams):
    """根據 fetcher 參數選擇對應的 Scrapling Fetcher。"""
    from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher

    kwargs = {}
    if p.proxy:
        kwargs["proxy"] = p.proxy
    if p.headers:
        kwargs["headers"] = p.headers

    if p.fetcher == "fast":
        return Fetcher.get(p.url, stealthy_headers=True, timeout=p.timeout, **kwargs)

    elif p.fetcher == "stealth":
        return StealthyFetcher.fetch(
            p.url, headless=p.headless,
            network_idle=True, **kwargs
        )

    elif p.fetcher == "dynamic":
        return DynamicFetcher.fetch(
            p.url, headless=p.headless,
            network_idle=True, **kwargs
        )

    else:  # auto — 先快速，403 時升級
        try:
            page = Fetcher.get(p.url, stealthy_headers=True, timeout=p.timeout, **kwargs)
            if page.status in (403, 503):
                raise ValueError("blocked")
            return page
        except Exception:
            # 升級到隱身模式
            return StealthyFetcher.fetch(
                p.url, headless=p.headless,
                network_idle=True, **kwargs
            )
```

### 步驟 5：元素提取邏輯

```python
def _extract(self, page, p: WebScraperParams) -> list[dict]:
    """從頁面提取元素。"""
    # 選擇 selector
    if p.selector:
        if p.adaptive:
            elements = page.css(p.selector, adaptive=True)
        elif p.auto_save:
            elements = page.css(p.selector, auto_save=True)
        else:
            elements = page.css(p.selector)
    elif p.xpath:
        elements = page.xpath(p.xpath)
    else:
        # 無 selector → 回傳整頁
        return [{"text": page.text(), "html": str(page.body)}]

    # 提取資料
    items = []
    for el in elements:
        item = {}
        if p.extract in ("text", "markdown"):
            item["text"] = el.text()
        if p.extract == "html":
            item["html"] = str(el)
        if p.extract == "attrs":
            item["attrs"] = dict(el.attrib) if hasattr(el, 'attrib') else {}
        # 常用屬性自動提取
        href = el.attrib.get("href", "") if hasattr(el, 'attrib') else ""
        if href:
            item["href"] = href
        src = el.attrib.get("src", "") if hasattr(el, 'attrib') else ""
        if src:
            item["src"] = src
        items.append(item)

    return items
```

---

## 三種 Fetcher 模式

| 模式 | 類別 | 速度 | 反爬能力 | 適用場景 |
|------|------|------|---------|---------|
| `fast` | `Fetcher` | ⚡ 最快 | TLS 指紋模擬 | 靜態頁面、API |
| `stealth` | `StealthyFetcher` | 🔒 中等 | Cloudflare bypass | 有反爬的網站 |
| `dynamic` | `DynamicFetcher` | 🐢 最慢 | 完整瀏覽器 | JS 渲染頁面 |
| `auto` | 自動升級 | 自適應 | 漸進式 | 不確定時預設 |

### auto 模式邏輯

```
fast（HTTP）→ 403/503 → 自動升級 stealth → 仍失敗 → 回報錯誤
```

## 自適應元素追蹤

Scrapling 的核心特色 — 網站改版後自動重新定位目標元素：

```python
# 第一次：儲存元素特徵
products = page.css('.product', auto_save=True)

# 之後網站改版，class 從 .product 變成 .item-card
# 使用 adaptive=True 自動找到對應元素
products = page.css('.product', adaptive=True)  # 仍能找到！
```

**原理**：記錄元素的結構特徵（標籤、屬性、位置、文字模式），
改版後用相似度演算法重新定位，不依賴固定 selector。

## 輸出格式

```json
{
  "success": true,
  "data": {
    "items": [
      {"text": "Product Name", "href": "/product/1"},
      {"text": "Another Product", "href": "/product/2"}
    ],
    "count": 2,
    "url": "https://example.com/products",
    "status_code": 200,
    "fetcher_used": "fast"
  }
}
```

## Workflow 串接範例

### 基本爬取 → ETL → 圖表

```yaml
- id: scrape
  type: skill
  skill: web_scraper
  params:
    url: "https://example.com/games"
    selector: ".game-card"
    extract: "attrs"
    fetcher: "auto"
  output: raw_data

- id: transform
  type: skill
  skill: etl_pipeline
  params:
    source: "{{ outputs.raw_data.items }}"
    group_by: "provider"
    agg: "count"
    chart_type: "bar"
  output: chart_data
```

### 反爬網站 + 自適應

```yaml
- id: scrape_cf
  type: skill
  skill: web_scraper
  params:
    url: "https://protected-site.com/data"
    selector: "#main-content .item"
    fetcher: "stealth"
    adaptive: true
    solve_cloudflare: true
  output: data
```

## Spider 模式（大規模爬取）

對於需要爬取多頁的場景，直接使用 Scrapling Spider：

```python
from scrapling.spiders import Spider, Response

class GameSpider(Spider):
    name = "games"
    start_urls = ["https://example.com/games?page=1"]

    async def parse(self, response: Response):
        for item in response.css('.game-card'):
            yield {
                "name": item.css('h2::text').get(),
                "provider": item.css('.provider::text').get(),
                "url": item.css('a::attr(href)').get(),
            }
        # 翻頁
        next_page = response.css('a.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

GameSpider(max_concurrent=5).start()
```

Spider 特色：
- 並發控制（`max_concurrent`）
- 暫停/恢復（Ctrl+C 優雅關閉，重啟繼續）
- 串流模式（`async for item in spider.stream()`）
- 自動 Proxy 輪換
- robots.txt 遵守

## 依賴套件

```
scrapling>=0.4.8
```

安裝後需執行瀏覽器安裝（僅 stealth/dynamic 模式需要）：

```bash
pip install "scrapling[fetchers]"
scrapling install
```

僅用 fast 模式（HTTP only）：

```bash
pip install scrapling
```

## 與舊版的差異

| | v1（httpx + BS4） | v2（Scrapling） |
|---|---|---|
| 靜態頁面 | ✅ | ✅（更快） |
| JS 渲染 | ❌（需 ark-browser-tool） | ✅ DynamicFetcher |
| 反爬繞過 | ❌ | ✅ Cloudflare bypass |
| 自適應 | ❌ | ✅ 元素追蹤 |
| Spider | ❌ | ✅ 大規模爬取 |
| 效能 | BS4（慢） | 比 BS4 快 784x |
| Proxy | 手動 | 內建輪換 |

## 注意事項

- `fetcher: auto` 預設先用 HTTP，被擋才升級（省資源）
- `adaptive: true` 需要先用 `auto_save: true` 儲存過元素特徵
- `stealth`/`dynamic` 模式需要安裝瀏覽器（`scrapling install`）
- Spider 模式適合 10+ 頁的爬取，單頁用 Skill 即可
- 遵守 robots.txt 和網站 ToS
- Proxy 建議用環境變數 `${PROXY_URL}` 注入

## 踩坑紀錄

### Fetcher 自動降級（2026-06-01）

`auto` 模式下，部分網站回傳 200 但內容為空（JS 渲染）。
判斷邏輯應加入「頁面內容長度 < 閾值」作為升級條件：

```python
if page.status in (403, 503) or len(page.text()) < 100:
    # 升級到 stealth
```

### Scrapling 安裝注意（2026-06-01）

- `pip install scrapling` 只裝 parser（輕量）
- `pip install "scrapling[fetchers]"` 裝 fetcher 依賴
- `scrapling install` 裝瀏覽器（Chromium）
- Docker 環境用官方映像：`pyd4vinci/scrapling`
