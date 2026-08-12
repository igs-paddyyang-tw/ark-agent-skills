# View 軌渲染映射（MD → ark-html-report 元件）

當報告需要給人看時，依此表把 Content 軌 MD 渲染成 HTML。
**鐵律：渲染只做視圖裁剪與排版，禁止改寫 finding 內容、禁止新增 MD 沒有的結論**（composer 不改寫原則）。

## 風格選擇

| 報告 type | 建議風格 | 理由 |
|-----------|----------|------|
| review | terminal | 技術受眾、程式碼路徑密集 |
| competitive | editorial 或 boardroom | 長文閱讀 / 給主管 |
| incident | midnight 或 terminal | 值班/工程受眾 |
| decision | boardroom | 決策留存、對上溝通 |
| data | midnight | 數據密集 |

使用者指定則以指定為準。

## 結構映射

| MD 結構 | HTML 元件（ark-html-report） | 裁剪規則 |
|---------|------------------------------|----------|
| frontmatter title / subject / date / verdict | 封面標頭 report-header + verdict badge | verdict 枚舉 → badge 色：sound/decided/resolved/confirmed=ok、needs-work/mitigated/partially=warn、broken/open/blocked/rejected=danger |
| frontmatter findings 統計 + score | KPI 卡片列 | p0/p1/p2 各一卡；score 有才顯示，附 score_version |
| ## Verdict | 摘要 summary 區塊 | 全文保留，不縮寫 |
| ## Findings 表 | 資料表格 + severity badge 欄 | P0/P1 全列；P2/P3 可折疊或「其餘 N 項見 MD」——省略必須明示數量與去處 |
| ## Evidence | callout（info） | 預設只渲染 P0 對應的 E-x，其餘註明「完整證據見 MD」 |
| ## Actions 表 | 卡片網格（P0 對應項用 card-accent） | 全列 |
| ## 時間軸（incident） | timeline 元件 | 全列 |
| ## 比較矩陣（competitive） | 比較表格 compare（我方欄 hl） | 全列 |
| ## Decisions（decision） | 資料表格 + 狀態 badge | 全列；blocked 項連結對應 O-x |
| ## Open Questions | callout（warning）逐項 | 全列 —— 未決事項不許在人類視圖消失 |
| ## 邊界聲明 | callout（info）置於頁尾前 | 全列 —— 這是最不能裁掉的章節 |
| 頁尾 | report-footer | 註明「Content 軌來源：{md-path}」與渲染日期 |

## 裁剪原則

- 人類視圖可以**少**（折疊 P2、省略部分 Evidence），不可以**多**（新增 MD 沒有的圖表結論、改寫措辭強化語氣）
- 任何省略必留指路：「其餘 N 項見 {md-path}」
- 圖表只能從 MD 已有的表格數據產生；為了視覺效果自造數據 = 兩軌漂移
- HTML 頁尾必含 Content 軌路徑 —— 人看到 HTML 永遠找得回 source of truth
