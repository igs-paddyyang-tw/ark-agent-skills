# Mermaid 圖表指引

## 目錄

1. [選型決策表](#選型決策表)
2. [通用規則](#通用規則)
3. [常用圖表語法](#常用圖表語法)
4. [平台相容性](#平台相容性)

---

## 選型決策表

| 你要表達什麼 | 用哪種圖 | 關鍵字 |
|------------|---------|--------|
| 步驟流程、決策邏輯 | `flowchart` | 流程、判斷、分支 |
| 元件互動、API 呼叫 | `sequenceDiagram` | 請求、回應、時序 |
| 資料模型、表關係 | `erDiagram` | Entity、關聯、FK |
| 時間軸、里程碑 | `timeline` | 日期、版本、歷史 |
| 專案排程 | `gantt` | 時間軸 + 任務 |
| 概念分類、心智圖 | `mindmap` | 階層、分支、分類 |
| 系統架構、元件圖 | `graph LR` | 服務、連接、部署 |
| 狀態變遷 | `stateDiagram-v2` | 狀態、轉換、事件 |
| 類別關係、繼承 | `classDiagram` | OOP、介面、繼承 |
| 圓餅圖 | `pie` | 佔比、分佈 |
| Git 分支策略 | `gitGraph` | branch、commit、merge |

> [!TIP]
> 不確定用哪種？預設 `flowchart TD`（垂直流程）最萬用。

---

## 通用規則

### 必做

- 圖表前後空行
- 節點 ID 用 `snake_case`
- 標籤用中文（面向讀者）
- 保持簡潔：單張圖 < 15 個節點

### 禁止

- ❌ `%%{init}` 指令（GitHub dark mode 會壞）
- ❌ 行內 `style` 屬性（用 `classDef` 替代）
- ❌ 超過 20 個節點的單張圖（拆分）

### 樣式建議

```mermaid
%%  用 classDef 定義樣式
flowchart LR
    classDef primary fill:#e1f5fe,stroke:#0288d1
    classDef danger fill:#ffebee,stroke:#c62828

    A[正常節點]:::primary --> B[警示節點]:::danger
```

---

## 常用圖表語法

### Flowchart（流程圖）

```mermaid
flowchart TD
    start([開始]) --> input[/輸入資料/]
    input --> check{驗證通過？}
    check -->|是| process[處理]
    check -->|否| error[回傳錯誤]
    process --> output[/輸出結果/]
    output --> finish([結束])
```

**節點形狀速查**：

| 語法 | 形狀 | 用途 |
|------|------|------|
| `[文字]` | 矩形 | 一般步驟 |
| `([文字])` | 圓角 | 開始/結束 |
| `{文字}` | 菱形 | 判斷 |
| `[/文字/]` | 平行四邊形 | 輸入/輸出 |
| `[[文字]]` | 雙框 | 子流程 |
| `((文字))` | 圓形 | 連接點 |

**方向**：`TD`（上到下）、`LR`（左到右）、`BT`（下到上）、`RL`（右到左）

---

### Sequence Diagram（序列圖）

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant DB as Database

    C->>S: POST /api/users
    activate S
    S->>DB: INSERT INTO users
    DB-->>S: OK
    S-->>C: 201 Created
    deactivate S
```

**箭頭類型**：

| 語法 | 意義 |
|------|------|
| `->>` | 同步請求（實線） |
| `-->>` | 回應（虛線） |
| `--)` | 非同步訊息 |
| `--x` | 失敗/拒絕 |

**區塊**：

```
alt 條件 A
    步驟
else 條件 B
    步驟
end

loop 每 5 秒
    步驟
end

opt 可選
    步驟
end
```

---

### ER Diagram（實體關係圖）

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : "is in"

    USER {
        int id PK
        string name
        string email UK
    }
    ORDER {
        int id PK
        int user_id FK
        datetime created_at
    }
```

**關係符號**：

| 語法 | 意義 |
|------|------|
| `\|\|--\|\|` | 一對一 |
| `\|\|--o{` | 一對多 |
| `}o--o{` | 多對多 |

---

### Timeline（時間軸）

```mermaid
timeline
    title 產品路線圖
    section Q1
        1月 : MVP 上線
        3月 : 第一批使用者
    section Q2
        4月 : 功能迭代
        6月 : 公開發佈
```

---

### Mindmap（心智圖）

```mermaid
mindmap
    root((專案))
        前端
            React
            Next.js
        後端
            Go API
            Python 報表
        基礎設施
            Docker
            AWS
```

---

### State Diagram（狀態圖）

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Review : 提交
    Review --> Approved : 通過
    Review --> Draft : 退回
    Approved --> Published : 發佈
    Published --> [*]
```

---

### Gantt（甘特圖）

```mermaid
gantt
    title 開發排程
    dateFormat YYYY-MM-DD
    section 設計
        需求分析    :a1, 2026-01-01, 7d
        系統設計    :a2, after a1, 5d
    section 開發
        核心模組    :b1, after a2, 14d
        整合測試    :b2, after b1, 7d
```

---

## 平台相容性

| 平台 | 支援度 | 備註 |
|------|--------|------|
| GitHub | ✅ 完整 | 原生支援所有類型 |
| GitLab | ✅ 完整 | 原生支援 |
| VS Code | ✅ 需套件 | Markdown Preview Mermaid |
| Notion | ⚠️ 部分 | 需用 code block 嵌入 |
| Obsidian | ✅ 完整 | 原生支援 |
| HackMD | ✅ 完整 | 原生支援 |

> [!IMPORTANT]
> 如果目標平台不確定，使用 `flowchart` + `sequenceDiagram` + `erDiagram` 三種最安全。
