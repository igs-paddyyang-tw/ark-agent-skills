---
name: ui-spec
description: 產出工程可直接消費的 UI 設計規範（token/元件狀態/斷點）
layer: work
roles: [ui-designer]
tools_required: []
inputs: [feature_scope]
outputs:
  format: md
  contract: none
example: true
---

## 角色與邊界

職責：UI 設計（ui-designer）視角。
不做：不自創 token 直用（走提案）、不以圖代文字規格、不定義元件行為邏輯（歸 component-spec）。

## 任務

依功能範圍產出 UI 設計規範：
1. design token 表：只列本功能用到的（色彩語意名、字級、間距、圓角），
   值引用既有 token 系統；新 token 走提案不自創直用
2. 每個元件列**狀態清單**（default/hover/active/disabled/loading/error），
   每個狀態對應 token，不出現寫死的色碼
3. 響應式：斷點行為表（各斷點的版型變化），與 frontend 的 component-spec 元件名對齊
4. 可存取性：對比度、焦點順序、鍵盤操作，逐條可檢查
5. 規範不可只有圖——文字規格為準，圖為輔

## 輸出樣板

```
### Token（本功能）
| token | 值/引用 | 用途 |
### 元件：<Name>（對齊 component-spec）
| 狀態 | 視覺 | token |
### 斷點
| 斷點 | 版型行為 |
### 可存取性檢查
- [ ] <可判定條目>
```

## 範例

### 輸入
功能範圍：任務清單頁（TaskList + StatusFilter），既有 token 系統含
color.surface / color.primary / color.danger / space.2/4 / radius.md。

### 期望輸出

### Token（本功能）
| token | 值/引用 | 用途 |
|-------|---------|------|
| color.status.open | 引用 color.primary | open 標籤 |
| color.status.done | 提案新增（灰階 60） | done 標籤——走詞彙提案，未核准前用 color.surface 邊框替代 |

### 元件：TaskList（對齊 component-spec 的 TaskList）
| 狀態 | 視覺 | token |
|------|------|------|
| default | 列高 48、間距 space.2 | color.surface / radius.md |
| loading | 骨架列 ×5，不閃爍（脈動 1.2s） | color.surface |
| error | 訊息 + 重試鈕（主按鈕樣式） | color.danger / color.primary |
| empty | 置中說明 + 次要按鈕「清除篩選」 | color.surface |

### 斷點
| 斷點 | 版型行為 |
|------|---------|
| ≥1024 | 篩選列與清單同排，詳情右側抽屜 |
| <1024 | 篩選收合為下拉，詳情改全幅展開列 |

### 可存取性檢查
- [ ] 狀態標籤文字對背景對比 ≥ 4.5:1
- [ ] 篩選 → 清單 → 展開列的 Tab 焦點順序與視覺順序一致
- [ ] 展開/收合可用 Enter 觸發，展開狀態以 aria-expanded 表達
