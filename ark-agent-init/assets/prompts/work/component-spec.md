---
name: component-spec
description: 依功能規格產出前端元件規格（props/狀態/事件/三態/AC）
layer: work
roles: [frontend, fullstack-coder]
tools_required: []
inputs: [spec_path]
outputs:
  format: md
  contract: ac-table
example: true
---

## 角色與邊界

職責：前端工程（frontend）視角。
不做：不臆測 API 回應欄位、不越過端點表直呼內部服務、不產出實作碼（規格而已）。

## 任務

依功能規格拆解前端元件並產出元件規格：
1. 元件樹：頁面 → 容器 → 元件，每個元件一行（名稱｜職責｜父子關係）
2. 每個互動元件列 props / 內部狀態 / 對外事件，型別明確
3. 三態必列：載入中 / 錯誤 / 空資料，各自的呈現與可重試行為
4. API 依賴只引用端點表的 path，不臆測回應欄位；缺的列「待規格補」
5. 每個元件附 AC（AC-UI-{元件代號}-{序號}），可被 ark-code-spec-validator 解析

## 輸出樣板

```
### 元件：<Name>
職責：<一句話>
props：| 名稱 | 型別 | 必要 | 說明 |
狀態：| 名稱 | 型別 | 初值 | 誰改它 |
事件：| 名稱 | payload | 觸發時機 |
三態：載入=<...>｜錯誤=<...+重試>｜空=<...>
API：<METHOD /path>（來源：端點表）

| AC-ID | Given | When | Then |
|-------|-------|------|------|
| AC-UI-<X>-1 | <前置> | <操作> | <可驗證結果> |
```

## 範例

### 輸入
規格：後台工具的「任務清單」頁——顯示任務、可依狀態篩選、點列展開詳情；
端點表已有 `GET /tasks?status=`。

### 期望輸出

### 元件：TaskList
職責：顯示任務清單並支援狀態篩選
props：
| 名稱 | 型別 | 必要 | 說明 |
|------|------|------|------|
| initialStatus | 'all'\|'open'\|'done' | 否 | 預設篩選，缺省 'all' |

狀態：
| 名稱 | 型別 | 初值 | 誰改它 |
|------|------|------|--------|
| tasks | Task[] | [] | fetch 成功後 |
| status | string | props.initialStatus | StatusFilter onChange |
| expandedId | string\|null | null | 列點擊 |

事件：
| 名稱 | payload | 觸發時機 |
|------|---------|---------|
| onTaskOpen | taskId | 展開詳情時（供父層記遙測） |

三態：載入=骨架列×5｜錯誤=訊息+重試鈕（重呼同參數）｜空=「無符合任務」+清除篩選鈕
API：GET /tasks?status=（來源：端點表）

| AC-ID | Given | When | Then |
|-------|-------|------|------|
| AC-UI-TL-1 | 任務 12 筆、status=open 佔 5 | 選擇篩選 open | 清單僅顯示 5 筆且 URL query 同步 status=open |
| AC-UI-TL-2 | API 回 500 | 進入頁面 | 顯示錯誤態與重試鈕，點擊後重新請求同參數 |
| AC-UI-TL-3 | 已展開任務 A | 點擊任務 B | A 收合、B 展開，onTaskOpen 收到 B 的 id |
