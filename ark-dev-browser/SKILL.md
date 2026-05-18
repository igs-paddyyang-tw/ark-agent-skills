---
name: ark-dev-browser
description: |
  瀏覽器視覺測試與驗證：讓 Agent 能開啟瀏覽器、截圖、點擊元素、填表單，
  驗證自己產出的 UI 是否正確。閉合開發回饋迴圈。
  使用此 Skill 當使用者提及 瀏覽器測試、截圖驗證、visual testing、
  dev-browser、看一下畫面、確認 UI、E2E 驗證、localhost 預覽、
  或任何需要視覺化確認 Web 產出的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-16
  reference: https://github.com/SawyerHood/dev-browser
---

# ark-dev-browser

瀏覽器視覺測試 — 讓 Agent 看見自己的產出，閉合回饋迴圈。

## 觸發條件

- 「看一下畫面」「截圖」「確認 UI」
- 「瀏覽器測試」「visual testing」「E2E」
- 「localhost 預覽」「開啟頁面」
- 前端任務完成後的驗證階段

## 核心原則

```
沒有瀏覽器的 Agent = 盲人寫 UI
→ 寫完 code 必須看到結果才算完成
```

---

## 工作流程

### 1. 啟動本地服務

確認開發伺服器已啟動：
```bash
# 確認 port 可用
curl -s http://localhost:{port} > /dev/null && echo "OK"
```

### 2. 截圖驗證

使用 Playwright/Puppeteer 截圖：
```python
# scripts/screenshot.py
from playwright.sync_api import sync_playwright

def screenshot(url: str, output: str = "screenshot.png", width: int = 1280, height: int = 720):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(url, wait_until="networkidle")
        page.screenshot(path=output, full_page=True)
        browser.close()
```

### 3. 視覺檢查清單

截圖後確認：
- [ ] 頁面正常載入（無白屏/錯誤）
- [ ] 佈局符合設計（元素位置正確）
- [ ] 文字可讀（無溢出/截斷）
- [ ] 互動元素可見（按鈕/連結）
- [ ] 響應式正確（如需要）

### 4. 互動測試（進階）

```python
# 點擊、填表、驗證
page.click("button#submit")
page.fill("input[name='email']", "test@example.com")
assert page.locator(".success-message").is_visible()
```

---

## 使用場景

| 場景 | 動作 | 驗證 |
|------|------|------|
| 前端開發完成 | 截圖 localhost | 佈局正確 |
| CSS 修改 | 前後截圖對比 | 無意外變化 |
| 表單功能 | 填寫 + 提交 | 成功訊息出現 |
| 錯誤處理 | 觸發錯誤狀態 | 錯誤 UI 正確顯示 |
| 響應式 | 多尺寸截圖 | 各斷點正常 |

---

## 與 ark-superpowers 整合

在 ④ Execute 階段的 TDD 循環中：
```
RED → GREEN → REFACTOR → VISUAL VERIFY → COMMIT
```

視覺驗證作為 commit 前的最後一步。

---

## 前置需求

- Python + Playwright：`pip install playwright && playwright install chromium`
- 或 Node + Puppeteer：`npm install puppeteer`
- 本地開發伺服器已啟動

## 注意事項

- 截圖存放在 `artifacts/screenshots/`（不入版控）
- 不要在 CI 環境無頭瀏覽器未安裝時強制執行
- 截圖僅用於驗證，不作為測試的唯一依據（搭配 unit test）
- 敏感頁面（登入後）需要 session/cookie 管理
