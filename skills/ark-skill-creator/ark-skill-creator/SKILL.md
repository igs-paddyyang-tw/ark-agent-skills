---
name: ark-skill-creator
description: |
  建立新 Skill、修改和改善既有 Skill、測量 Skill 效能。
  使用此 Skill 當使用者想要從零建立 Skill、編輯或優化既有 Skill、
  執行評估測試 Skill、基準測試 Skill 效能、
  或優化 Skill 的 description 以提升觸發準確度。
---

# Skill 建立器

建立和迭代改善 Skill 的工作流。

## 核心流程

1. 決定 Skill 要做什麼以及大致如何做
2. 撰寫 Skill 草稿
3. 建立測試提示詞並執行測試
4. 評估結果（質化 + 量化）
5. 根據回饋重寫 Skill
6. 重複直到滿意
7. 擴大測試集再次驗證

## 建立 Skill

### 捕捉意圖

理解使用者的意圖：
1. 這個 Skill 應該讓 AI 能做什麼？
2. 什麼時候應該觸發？（什麼使用者語句/情境）
3. 期望的輸出格式是什麼？
4. 是否需要設定測試案例？

### 訪談與研究

主動詢問邊界案例、輸入/輸出格式、範例檔案、成功標準和依賴。

### 撰寫 SKILL.md

填入以下元件：
- **name**：Skill 識別碼
- **description**：何時觸發、做什麼。這是主要觸發機制——包含 Skill 的功能和使用情境。讓 description 稍微「積極」一些，避免觸發不足。
- **SKILL.md 本體**：指令內容

### Skill 撰寫指南

#### Skill 結構

```
skill-name/
├── SKILL.md（必要）
│   ├── YAML frontmatter（name、description 必要）
│   └── Markdown 指令
└── 附帶資源（選用）
    ├── scripts/    — 可執行程式碼
    ├── references/ — 按需載入的文件
    └── assets/     — 輸出用的檔案（範本、圖示、字型）
```

#### 漸進式揭露

Skill 使用三層載入系統：
1. **後設資料**（name + description）— 永遠在 context 中（~100 字）
2. **SKILL.md 本體** — Skill 觸發時載入（理想 <500 行）
3. **附帶資源** — 按需載入（無限制）

**關鍵模式**：
- SKILL.md 保持在 500 行以內；接近上限時加入額外層級
- 從 SKILL.md 清楚指向參考檔案
- 大型參考檔案（>300 行）包含目錄

#### 撰寫風格

- 用命令式語氣撰寫指令
- 解釋「為什麼」而非堆疊「必須」
- 善用範例模式展示輸入/輸出
- 讓 Skill 通用化，不要過度擬合特定範例

---

## 測試案例

撰寫 Skill 草稿後，建立 2-3 個真實的測試提示詞。

儲存至 `evals/evals.json`：

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "使用者的任務提示詞",
      "expected_output": "期望結果描述",
      "files": []
    }
  ]
}
```

## 執行與評估測試

### 步驟 1：同時啟動所有測試（有 Skill vs 無 Skill）

對每個測試案例，同時啟動兩個子代理——一個有 Skill，一個沒有。

### 步驟 2：測試進行中，草擬斷言

利用等待時間草擬量化斷言。好的斷言是客觀可驗證的。

### 步驟 3：完成後記錄時間資料

記錄 `total_tokens` 和 `duration_ms` 到 `timing.json`。

### 步驟 4：評分、彙總、啟動檢視器

1. 評分每次執行
2. 彙總為基準測試
3. 分析師檢視——找出統計數據可能隱藏的模式
4. 啟動檢視器讓使用者審查

### 步驟 5：讀取回饋

讀取 `feedback.json`，空回饋表示使用者認為沒問題。聚焦在有具體抱怨的測試案例。

---

## 改善 Skill

### 改善思維

1. **從回饋中泛化**：避免過度擬合特定範例
2. **保持精簡**：移除沒有貢獻的內容
3. **解釋為什麼**：解釋原因比堆疊 MUST/NEVER 更有效
4. **尋找重複工作**：如果所有測試都獨立寫了類似的輔助腳本，把它打包進 `scripts/`

### 迭代循環

1. 改善 Skill
2. 重新執行所有測試到新的 `iteration-N+1/` 目錄
3. 啟動檢視器（含 `--previous-workspace`）
4. 等待使用者審查
5. 讀取回饋，再次改善

持續直到使用者滿意或回饋全為空。

---

## Description 優化

description 是決定 Skill 是否被觸發的主要機制。

### 步驟 1：產生觸發評估查詢

建立 20 個評估查詢——混合應觸發和不應觸發的。
查詢必須真實、具體、有細節。

### 步驟 2：與使用者審查

使用 HTML 範本讓使用者審查和編輯評估集。

### 步驟 3：執行優化循環

```bash
python -m scripts.run_loop \
  --eval-set <path> \
  --skill-path <path> \
  --max-iterations 5
```

### 步驟 4：套用結果

取 `best_description` 更新 SKILL.md frontmatter。

## 注意事項

- Skill 不得包含惡意程式碼或安全風險
- 主觀輸出（寫作風格、設計）適合質化評估，不要強加量化斷言
- 測試查詢要夠實質，讓 AI 真正需要參考 Skill
- 簡單的一步驟查詢不會觸發 Skill，因為 AI 可以直接處理
