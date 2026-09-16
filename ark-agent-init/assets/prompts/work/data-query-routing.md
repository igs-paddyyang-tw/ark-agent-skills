---
name: data-query-routing
description: 查數據/知識庫時的口徑路由 —— 結構化數據走 SQL、問答走 agent-chat，別誤用 kb-chat 算數
layer: work
roles: [qa-manager, math-designer, game-analyst, data-analyst]
tools_required: []
inputs: [query]
outputs:
  format: none
  contract: none
example: true
---

## 任務

收到「查數據」需求時，先判斷類型再選路徑 —— **不要一律丟 kb-chat**（它是 RAG 撈文件，不會算數字）：

1. **結構化數據**（營收 / KPI / 儲值 / DAU / 留存）
   → `route_query.py`（先查口徑定義）→ 產 SQL → `ark-db-query` 執行 BQ
   → 🔴 不要直接 kb-chat 問數字：它只會 RAG 撈文件、不會算
2. **WeKnora 問答 / 推理** → 預設 **agent-chat**（agent 自找 KB，多步）
3. **查特定自建 KB 文件內容** → `knowledge-chat --kb-id`（RAG + citation）
4. `kb-chat` 主要用途是「查/寫自建知識庫內容」，**不是算數據的預設**

## 輸出樣板

```
查詢：<原始需求>
類型：<結構化數據 | 問答推理 | 查 KB 文件>
路徑：<route_query→SQL→BQ | agent-chat | knowledge-chat --kb-id>
理由：<為何走這條，一句話>
```

## 範例

### 輸入
「上個月金猴爺的營收多少」

### 期望輸出
查詢：上個月金猴爺營收
類型：結構化數據（營收）
路徑：route_query.py 查營收口徑 → 產 SQL → ark-db-query 執行 BQ
理由：營收要「算」不是「撈文件」，kb-chat 只會 RAG 回相關段落不會加總
