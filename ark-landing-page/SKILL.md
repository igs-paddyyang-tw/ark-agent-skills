---
name: ark-landing-page
description: |
  快速產出高轉換率 Landing Page：遊戲預註冊頁、活動頁、產品介紹頁。
  包含結構模板、文案框架、CTA 設計、響應式佈局、SEO 基礎。
  使用此 Skill 當使用者提及 landing page、著陸頁、預註冊頁、
  活動頁、產品頁、一頁式網站、或任何需要快速產出行銷頁面的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-16
---

# ark-landing-page

快速產出高轉換率 Landing Page — 遊戲預註冊 / 活動 / 產品介紹。

## 觸發條件

- 「landing page」「著陸頁」「預註冊頁」
- 「活動頁」「產品頁」「一頁式」
- 「行銷頁面」「轉換頁」

---

## 頁面結構（7 區塊）

```
1. Hero（首屏）— 標題 + 副標 + CTA + 視覺
2. Social Proof — 數據/評價/媒體 logo
3. Features — 3-4 個核心賣點（icon + 文字）
4. How It Works — 3 步驟流程
5. Screenshots/Demo — 遊戲畫面展示
6. FAQ — 3-5 個常見問題
7. Final CTA — 重複主 CTA + 緊迫感
```

---

## Hero 區塊 SOP

| 元素 | 規則 |
|------|------|
| 標題 | ≤ 10 字，一句話價值主張 |
| 副標題 | ≤ 30 字，補充說明 |
| CTA 按鈕 | 動作導向（「立即體驗」非「了解更多」） |
| 視覺 | 遊戲截圖 / 短影片 / 動態 GIF |

---

## CTA 設計原則

- 一頁只有一個主要 CTA（重複出現 2-3 次）
- 按鈕顏色與背景高對比
- 文案用動詞開頭（「開始」「領取」「加入」）
- 加入緊迫感（限時/限量/倒數）

---

## 技術實作

### 推薦技術棧

| 場景 | 技術 | 原因 |
|------|------|------|
| 快速原型 | 單一 HTML + Tailwind CDN | 零建置，秒部署 |
| 正式版 | Next.js + Vercel | SSR + 分析 + 快 |
| 遊戲活動 | PixiJS 嵌入 HTML | 互動效果 |

### 效能要求

- First Contentful Paint < 1.5s
- 總頁面大小 < 2MB
- 圖片用 WebP + lazy load
- 手機優先（60%+ 流量來自手機）

---

## 遊戲預註冊頁模板

```html
Hero: 遊戲名 + 一句話 + 預註冊按鈕 + 預告影片
↓
亮點: 3 個核心玩法（icon + 標題 + 一句話）
↓
畫面: 4 張遊戲截圖（輪播）
↓
獎勵: 預註冊獎勵清單（里程碑解鎖）
↓
CTA: 「立即預註冊，搶先體驗」+ 社群連結
```

---

## 注意事項

- 一頁一目標（不要塞太多 CTA）
- 手機版優先設計
- 載入速度 > 視覺花俏
- 加入 Google Analytics / Facebook Pixel 追蹤
- 多語言版本用 hreflang 標記
