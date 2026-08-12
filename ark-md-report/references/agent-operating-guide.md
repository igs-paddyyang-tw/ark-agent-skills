# 三件套運作說明（Agent Operating Guide）

> Content 軌（ark-md-report）＋ View 軌（ark-html-report）＋ 庫（ark-wiki-engine）的統一運作契約。
> 本文件的 prompt block 可直接貼入各 agent 的 SOUL.md / BRAIN.md steering 區。

## 一、職責分工（一張表記住）

| | ark-md-report | ark-html-report | ark-wiki-engine |
|---|---|---|---|
| 角色 | Content 軌：分析結論的唯一事實來源 | View 軌：人類視圖 | 庫：長期知識的儲存/索引/檢索 |
| 產出 | 時點快照 MD（immutable） | 單檔 HTML（可重渲染） | wiki 頁面（seedling→mature 演化） |
| 受眾 | agent / 日報 / wiki ingest | 人 | agent 與人 |
| 誰讀誰 | — | 讀 MD 渲染 | 以報告為 source 蒸餾 synthesis 頁 |

## 二、路由決策樹（lead-agent 用）

```
收到任務
├─ 要「分析並下結論」（review/競品/事故/決策/數據）
│    → ark-md-report 產 Content 軌
│         └─ 有人類受眾？ → ark-html-report 渲染 + report_pair.py stamp
├─ 只要「排版給人看」且結論已存在於某 MD
│    → ark-html-report（渲染模式，只裁剪不改寫）
├─ 要「查知識/找過往結論」
│    → wiki-engine query / hybrid_search（wiki 無命中 → 查 docs/reports/_index.md）
└─ 要「沉澱為長期知識」
     → wiki-engine 以報告為 source 蒸餾（LLM 路徑，走審核）；禁止直接複製報告進 wiki/
```

## 三、四條鐵律（貼入所有相關 agent 的 SOUL.md）

```
[ARK:REPORT-RULES]
1. MD-first：任何分析結論先落 Content 軌 MD（ark-md-report 契約），HTML 只是視圖。
   沒有 MD 的 HTML 報告 = 違規產出。
2. 只裁剪不改寫：渲染 View 軌時禁止改寫 finding 措辭、禁止新增 MD 沒有的結論或數據；
   省略必註明「其餘 N 項見 {md-path}」；HTML 頁尾必含 Content 軌路徑。
3. 受控詞彙：severity 只有 P0-P3、confidence 只有 high/medium/low、verdict 依 type 枚舉、
   tags 只用 wiki 受控詞彙表 —— 新概念寫進報告的「詞彙表建議」章節等人工審核，不自創。
4. 報告 immutable：發布後不改內容；有新發現產新報告並以 related_reports 串接；
   ID（F/A/E/D/O-x）永不重排、不回收。
[/ARK:REPORT-RULES]
```

## 四、Deterministic 守門（兩層信任模型的落地）

Agent 宣告「報告完成」前，以下指令必須全綠 —— 這是不可跳過的機器關卡，
LLM 自評「我覺得格式對了」不算數：

```bash
# 1. 契約 lint（frontmatter/枚舉/ID 連續/統計一致/禁詞/必要章節）
python scripts/report_lint.py {report.md} [--wiki-schema knowledge/{proj}/schema.md]

# 2. 有渲染 HTML 時：寫入戳記 + 驗證配對
python scripts/report_pair.py stamp {report.md} {report.html}
python scripts/report_pair.py check {report.md}

# 3. 註冊：索引 + 日報 log line + wiki source 建議
python scripts/report_register.py {report.md} [--wiki knowledge/{proj}]
```

CI / pre-commit 建議掛：`report_lint.py docs/reports/**/*.md` 與 `report_pair.py scan docs/reports/`。

## 五、各 Agent 提詞片段

### insight-agent（產分析報告的主力）

```
[ARK:AGENT-NOTES insight-agent]
產出任何分析結論時：
- 使用 ark-md-report skill，先定 type（review/competitive/incident/decision/data）
- 寫作前讀 ai-writing-rules.md，重點：結論先行、chunk 自足（主詞寫全名、
  章節標題含檢索關鍵詞）、每個 P0/P1 finding 必附 Evidence 與 confidence
- 完成後跑 report_lint.py，FAIL 就修到過，不得帶 FAIL 交付
- 交付訊息格式：「報告已落盤 {path}｜verdict: {verdict}｜P0:{n} P1:{n}｜lint: PASS」
[/ARK:AGENT-NOTES]
```

### report-agent（渲染與日報）

```
[ARK:AGENT-NOTES report-agent]
- 渲染請求：讀 Content 軌 MD → 依 ark-md-report/references/html-mapping.md 映射 →
  ark-html-report 產 HTML → report_pair.py stamp → check 必須 OK
- 風格預設依報告 type（review→terminal / decision→boardroom / data→midnight /
  competitive→editorial），使用者指定優先
- 日報素材：只從 docs/reports/log.md 解析（欄序契約：date|type|subject|verdict|p0|p1|p2|score|path），
  不重新解讀報告內文；需要細節時引用 {path}#F-x
- 禁止：從 HTML 反向摘錄內容（HTML 是視圖不是來源）
[/ARK:AGENT-NOTES]
```

### dev-agent（消費 findings 修東西）

```
[ARK:AGENT-NOTES dev-agent]
- 接到修復任務時，以報告的 F-x / A-x 為工作單位，commit message 引用
  「fix: {A-x} ({report-path}#{F-x})」
- 修復完成不改原報告 —— 修復狀態記在新的 review 報告或 plan 的 AC，
  原報告是歷史快照
[/ARK:AGENT-NOTES]
```

### grill-me 銜接（拷問後落盤）

```
[ARK:AGENT-NOTES grill-me-postprocess]
拷問結束產出決策摘要時：
- 使用 ark-md-report 的 decision 型（Decisions 表 D-x + 拷問題號依據、
  Open Questions O-x + 阻塞關係）
- frontmatter loop_stage: post-grill-me
- 下游 superpowers 寫 spec 時 related_reports 指回本摘要，spec 章節可引用 D-x
[/ARK:AGENT-NOTES]
```

## 六、目錄與命名約定

```
docs/reports/
├── _index.md                    # report_register 自動重建，勿手編
├── log.md                       # append-only，CollectorRunner 解析
├── review/2026-08-11-{slug}.md          # Content 軌
├── review/2026-08-11-{slug}.html        # View 軌（同目錄同名，pair 檢查依此）
├── decision/…  incident/…  competitive/…  data/…
└── html/                        # 無對應 MD 的獨立 View 報告（應盡量少）
```

- 檔名：`YYYY-MM-DD-kebab-slug.md`（中文標題留 frontmatter title）
- `subject` 是跨報告聚合的 join key：repo 相對路徑或產品正式名，全庫拼法一致

## 七、與 wiki 的邊界（最常犯的三個錯）

1. ❌ 把報告複製進 `wiki/` 目錄 → ✅ 報告留在 docs/reports/，wiki 頁 frontmatter `sources` 指向它
2. ❌ 報告的 tags 自創新詞 → ✅ 用受控詞彙表既有 tag ＋「詞彙表建議」章節提案
3. ❌ 更新舊報告內容以反映新狀況 → ✅ 產新報告 + related_reports 串接；wiki synthesis 頁才是「持續更新」的地方

## 八、資源參考

| 資源 | 路徑 | 用途 |
|------|------|------|
| frontmatter 契約 | ark-md-report/references/frontmatter-contract.md | 欄位與枚舉的唯一定義 |
| 五型結構 | ark-md-report/references/report-types.md | 各類型章節模板 |
| AI 寫作規則 | ark-md-report/references/ai-writing-rules.md | chunk 自足/受控詞彙/證據三元組 |
| 渲染映射 | ark-md-report/references/html-mapping.md | MD 結構 → HTML 元件 |
| token 契約 | ark-html-report/references/styles.md 末節 | 呈現層公共變數介面 |
| 本文件 | docs/agent-operating-guide.md | agent 提詞與管線順序 |

擴充契約（新增 type、新增枚舉值）時：先改 frontmatter-contract.md → 同步 report_lint.py 的枚舉常數 → 跑既有報告全庫 lint 確認不誤殺 —— 契約文件與 lint 腳本不同步，就是這套系統自己的 drift。
