---
name: ark-ui-design-system
description: |
  設計系統自動生成：分析專案需求後產出完整設計系統（色彩、字型、元件、間距），
  確保 UI 產出不是 AI 預設風格（紫色漸層）而是專業、一致的設計。
  使用此 Skill 當使用者提及 設計系統、design system、UI 風格、
  色彩規範、元件庫、ui-ux、前端設計、視覺規範、
  或任何需要建立/套用設計系統的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-16
  reference: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
---

# ark-ui-design-system

設計系統自動生成 — 讓 Agent 產出專業 UI，不再是 AI 預設紫色漸層。

## 觸發條件

- 「設計系統」「design system」「UI 風格」
- 「色彩規範」「元件庫」「視覺規範」
- 「前端設計」「ui-ux」「建立風格指南」
- 新專案前端啟動時

## 核心原則

```
AI 預設 UI = 紫色漸層 + 圓角卡片 + 千篇一律
→ 先建設計系統，再寫 UI code
```

---

## 工作流程

### 1. 需求分析

確認以下資訊：
- **產品類型**：遊戲 / SaaS / 電商 / 內部工具
- **目標受眾**：年齡層、技術程度
- **品牌調性**：專業 / 活潑 / 科技 / 復古
- **參考網站**：2-3 個喜歡的設計參考

### 2. 產出設計系統（DESIGN-SYSTEM.md）

```markdown
# Design System — {專案名稱}

## 色彩
| 用途 | 色碼 | 說明 |
|------|------|------|
| Primary | #XXXXXX | 主色（CTA、重點） |
| Secondary | #XXXXXX | 輔色 |
| Background | #XXXXXX | 背景 |
| Surface | #XXXXXX | 卡片/面板 |
| Text | #XXXXXX | 主文字 |
| Text-muted | #XXXXXX | 次要文字 |
| Success | #XXXXXX | 成功狀態 |
| Error | #XXXXXX | 錯誤狀態 |

## 字型
| 用途 | 字型 | 大小 | 行高 |
|------|------|------|------|
| H1 | {font} | 2.5rem | 1.2 |
| H2 | {font} | 2rem | 1.3 |
| Body | {font} | 1rem | 1.6 |
| Small | {font} | 0.875rem | 1.4 |

## 間距系統
Base: 4px → 4, 8, 12, 16, 24, 32, 48, 64

## 圓角
- Small: 4px（按鈕、輸入框）
- Medium: 8px（卡片）
- Large: 16px（Modal）

## 元件規範
### Button
- Primary: bg-primary, text-white, hover 加深 10%
- Secondary: border-primary, text-primary, hover bg-primary/10
- 高度：36px（sm）/ 44px（md）/ 52px（lg）

### Card
- bg-surface, border 1px border-color, radius-medium
- padding: 24px, shadow: 0 2px 8px rgba(0,0,0,0.08)

### Input
- height: 44px, border 1px, radius-small
- focus: border-primary + ring 2px primary/20
```

### 3. 產出 CSS 變數

```css
:root {
  --color-primary: #XXXXXX;
  --color-secondary: #XXXXXX;
  --color-bg: #XXXXXX;
  --color-surface: #XXXXXX;
  --color-text: #XXXXXX;
  --font-heading: '{font}', sans-serif;
  --font-body: '{font}', sans-serif;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;
  --space-unit: 4px;
}
```

### 4. 套用到所有 UI 產出

後續所有前端 code 必須引用設計系統變數，禁止 hardcode 色碼。

---

## 產業預設

| 產業 | 主色調 | 風格 |
|------|--------|------|
| 遊戲（捕魚） | 深藍 + 金色 | 暗黑科技、霓虹 |
| SaaS | 藍/紫 + 白 | 乾淨、專業 |
| 電商 | 橘/紅 + 白 | 活潑、促銷感 |
| 內部工具 | 灰 + 藍 | 中性、資訊密度高 |
| 金融 | 深藍 + 綠 | 信任、穩重 |

---

## 與 ark-superpowers 整合

在 ② Spec 階段：
- 前端需求 → 先觸發本 Skill 建立設計系統
- 設計系統存入 `docs/design-system.md`
- ④ Execute 階段所有 UI code 引用此系統

---

## 品質檢查

- [ ] 色彩對比度 ≥ 4.5:1（WCAG AA）
- [ ] 字型大小 ≥ 14px（正文）
- [ ] 互動元素 ≥ 44px 觸控區域
- [ ] 暗色/亮色模式都定義（如需要）
- [ ] 無 hardcode 色碼（全用 CSS 變數）

## 注意事項

- 設計系統建立一次，全專案共用
- 修改設計系統需要全域影響評估
- 不要在沒有設計系統的情況下寫 UI code
- 遊戲 UI 可能需要更自由的設計（但仍需色彩規範）
