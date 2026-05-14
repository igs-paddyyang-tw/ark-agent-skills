---
name: generate-uml
description: |
  產出 Mermaid 格式的 UML 圖表，用於系統設計文件。
  支援序列圖、類別圖、ERD、流程圖、元件圖。
  使用此 Skill 當使用者提及 UML、序列圖、類別圖、ERD、流程圖、
  架構圖、Mermaid、畫圖、系統互動圖、資料模型圖。
---

# Skill: generate-uml

## 說明

產出 Mermaid 格式的 UML 圖表，用於系統設計文件。

## 支援圖表類型

| 類型 | 用途 | Mermaid 語法 |
|------|------|-------------|
| 序列圖 | API 流程、元件互動 | `sequenceDiagram` |
| 類別圖 | Domain Model、介面定義 | `classDiagram` |
| ERD | 資料庫 Schema | `erDiagram` |
| 流程圖 | 業務流程、決策樹 | `flowchart` |
| 元件圖 | 系統架構總覽 | `graph` |

## 使用方式

當需要產出設計圖時，依以下規則選擇圖表類型：

1. **描述 API 互動流程** → 序列圖
2. **描述資料模型關係** → ERD
3. **描述系統元件與依賴** → 元件圖（flowchart LR）
4. **描述業務邏輯分支** → 流程圖
5. **描述類別/介面繼承** → 類別圖

## 輸出格式

```markdown
## {圖表標題}

```mermaid
{diagram_content}
```

### 說明
- {圖表重點解讀}
```

## 範例：微服務序列圖

```mermaid
sequenceDiagram
    participant C as Client (React)
    participant G as API Gateway
    participant U as User Service (Go)
    participant R as Report Service (Python)
    participant DB as PostgreSQL
    participant MQ as RabbitMQ

    C->>G: POST /api/v1/reports/generate
    G->>U: Verify Token
    U-->>G: OK
    G->>R: GenerateReport(params)
    R->>DB: Query data
    DB-->>R: Result set
    R->>MQ: Publish report.generated
    R-->>G: 202 Accepted {job_id}
    G-->>C: 202 {job_id}
```

## 品質要求

- 參與者命名：`{簡稱} as {全名} ({技術})`
- 訊息標註：含 HTTP Method 或 gRPC method
- 非同步用虛線箭頭 `-->>`
- 複雜流程用 `alt/opt/loop` 區塊
