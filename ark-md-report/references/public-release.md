# 公開版發佈：內部報告 → 對外可看的公開版

> 1.2.0 起收進本技能（來源：fish-bot、slot-bot 各自的報告發佈流程，2026-11-03 起實際跑過多輪）。
> 適用：報告要放到不用登入就看得到的地方（作品集網站、對外分享連結）。內部完整版不動，公開版另存。

## 流程

```
內部完整版 MD（report_lint PASS）
  → 去敏腳本（專案自寫，用 public_edit.must）→ 公開版 MD（另存，不覆蓋內部版）
  → build_report_html.py --public → 公開版 HTML（mermaid 預渲染＋後處理）
  → public_scan.py --rules <專案規則>  → 0 命中才可放
  → 放到發佈位置；上架紀錄留一行（見下）
```

## 1. 要拿掉的五類

| 類別 | 例 | 處置 |
|---|---|---|
| 上游缺陷細節 | 缺陷登記表逐條、可被利用的失效方式 | 改成一句原則（「只修資產受損類；逐條內容不公開」） |
| 營運數值差異 | 某功能 RTP 會低於現況 | 刪 |
| 正式環境細節 | 資料庫集合名稱與版本、主機、部署機 | 改「正式環境資料庫對接待完成」 |
| 內部識別 | repo／分支名、commit 編號、本機路徑、帳號 | 刪或改泛稱 |
| 審查評等 | verdict、Findings、Evidence、Actions | 改成一張「剩餘工作（公開摘要）」表 |

保留：套件路徑、文件名、決策編號、測試名、技術做法 —— 這些是要展示的內容。

## 2. 去敏：`public_edit.py`

替換清單依報告內容寫，**放在專案自己的腳本**；共用的只有紀律：

```python
import sys; sys.path.insert(0, "<ark-md-report>/scripts")
from public_edit import must, must_all, strip_frontmatter

fm, body = strip_frontmatter(text)
body = must(body, "（特殊魚批 4 完成、commit a8748b8）", "（特殊魚批 4 完成）")
body = must_all(body, [("Golden Hoyeah 老虎機", "老虎機"), ("釘 commit", "釘版本")])
```

`must()` 要求目標**剛好出現一次**，否則拋 `EditMiss`。報告文字改了以後，舊的替換對不上會直接報錯，
不會像 `str.replace` 一樣靜默跳過、把敏感字串留在公開版。

## 3. 產生 HTML：`build_report_html.py`

```bash
python build_report_html.py public/<報告>.md public/<報告>.html \
  --asof "資料截至 2026-11-06" --kick "<專案> ・ 技術分析報告" \
  --public --back "/showcase/team/<專案>|← 回到 <專案> 案例" \
  --playwright <含 node_modules/playwright-core 的資料夾>
```

- 只裁剪不改寫：內容全來自 MD；mermaid 區塊渲染成內嵌 SVG（產出離線可看圖）
- 渲染時需要網路（mermaid、中文字型）、node、playwright-core 與本機 chromium（`~/.cache/ms-playwright`）
- 自動後處理：SVG 數字取 1 位小數（浮點長尾會被當成 commit 編號）、補 mermaid 標籤 CSS（避免框內字被截）、
  刪未引用的 `<symbol>`（sequenceDiagram 內嵌圖示的路徑會被 IP 規則命中）
- 不含 mermaid 的報告不需要 `--playwright`
- 版面與圖卡設計需求請改用 ark-html-report；本腳本只做「長文報告」一種版型

## 4. 掃描：`public_scan.py`

```bash
python public_scan.py public/ --rules scripts/report_tools/public_rules.json
```

| 規則層 | 內容 | 放哪 |
|---|---|---|
| 通用（內建） | 疑似 commit 編號、IP、本機家目錄路徑、金鑰與 token、email、審查報告評等值 | 本技能 |
| 專案（`--rules`） | 內部 repo／分支／主機名、正式資料庫名、缺陷編號格式、營運數值說法 | **專案 repo**（這些詞本身就是內部資訊，不放進共用技能） |

專案規則檔：

```json
{"rules": [
  {"name": "內部 repo", "pattern": "(?i)slot-server|fish_go"},
  {"name": "缺陷編號", "pattern": "AB-[0-9]+"}
]}
```

- 回傳碼：0＝全部 0 命中；1＝有命中或掃到 0 個檔案；2＝規則檔錯誤
- 🔴 **第一輪就 0 命中要當成可疑**：用 grep 抽查 commit、資料庫名、缺陷編號是否真的不在了
- 新的敏感詞一發現就加進專案規則；**不放寬規則**來讓掃描變綠（命中是誤判時，改產生端，例如 SVG 取小數）
- 「verdict」這個詞本身不算命中（介紹報告契約時會寫到），只有 `verdict: <枚舉值>` 才算

## 5. 上架紀錄

上架時在 commit 訊息與每日紀錄留一行，讓收集進度的一方（例如作品集維護者）不用猜：

```
上架：<檔名>｜里程碑：<階段>／<一句話>｜決策：D-xxx、D-yyy｜類型：stage|tech
```

## 6. 踩過的坑

| 坑 | 怎麼避 |
|---|---|
| `str.replace` 找不到目標時靜默無動作 | 一律 `must()` |
| SVG 浮點座標 `25.040000000000003` 被當成 commit 編號 | 產生端取小數 1 位（`build_report_html` 已內建） |
| mermaid 框內文字被截斷 | 渲染前先載入中文字型；後處理補標籤 CSS（已內建） |
| sequenceDiagram 內嵌圖示被 IP 規則命中 | 刪未引用的 `<symbol>`（已內建），不放寬掃描規則 |
| 公開版只靠人眼檢查 | 一定跑 `public_scan.py`，第一輪就抓到漏網過 |
| `report_lint` 不帶 `--wiki-schema` 時不驗 tags | 一律帶 schema |
