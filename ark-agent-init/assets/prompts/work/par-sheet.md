---
name: par-sheet
description: 產出 slot PAR sheet（符號/賠付/機率/RTP），附驗證方法
layer: work
roles: [math-designer]
tools_required: []
inputs: [game_spec]
outputs:
  format: data
  contract: md-report
example: true
---

## 任務

產出數值 PAR sheet：
1. 符號表 + 各連線賠付
2. 各符號出現機率（reel strip 或權重）
3. 算出理論 RTP，標貢獻分解（各獎項貢獻多少 %）
4. 附驗證方法（Monte Carlo 樣本數 + 收斂判準），不只給數字
5. RTP 未達目標區間就標紅，不硬湊

## 輸出樣板

```
## 符號賠付
| 符號 | 3連 | 4連 | 5連 |
## 機率
| 符號 | 權重 | 機率 |
## RTP
理論 RTP：<X.XX%>（目標 <區間>）
貢獻分解：<各獎項 %>
驗證：Monte Carlo n=<樣本>，收斂判準 <CI 寬度>
```

## 範例

### 輸入
規格：5x3 slot，目標 RTP 96%±0.5%，8 種符號

### 期望輸出
## RTP
理論 RTP：96.32%（目標 95.5%–96.5%）✅
貢獻分解：免費遊戲 38% · 一般連線 54% · scatter 8%
驗證：Monte Carlo n=1e8，95% CI 寬度 <0.05%，實測 96.30%（落理論 ±0.02%）
