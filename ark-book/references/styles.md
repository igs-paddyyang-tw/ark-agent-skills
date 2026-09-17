# 風格系統（styles）

一本書一種風格，在 `book.yaml` 的 `style:` 指定（或 `book_build.py --style X` 覆蓋）。
每種風格 = `assets/styles/{name}.css` 一個檔，登錄在 `assets/styles/_manifest.json`。
`python scripts/book_build.py --list-styles` 列出全部。

風格只換皮：章節結構、教學元件、戳記、catalog 契約完全不變。同一本書可以 `--out` 到不同檔案比較風格再定案。

## 六種預設

靈感來自日本遊戲素材的六種視覺語言（熱血勝負／IP 人物／二次元收藏／霓虹獎勵／實機玩法／高對比短句），
每種只借「一個母題」，其餘克制——素材分析的結論是「一個清楚的焦點＋一種主要動勢＋短句」，書也一樣。

| style | 標籤 | 底色 | 靈感 | 母題（只有這一個地方大膽） | 適合的書 |
|---|---|---|---|---|---|
| `library` | 圖書館 | 泛黃書頁 | 圖書館：橡木書架、黃銅標籤 | 書脊目錄，當前章抽出 | 方法論、長讀、要沉浸的內容 |
| `felt` | 牌桌 | 深綠絨布 + 象牙牌 | 麻雀格闘：深綠牌桌、金光、黃白粗字黑厚描邊、斜切 | punchline 是斜切的「ツモ」橫幅；章節像一張牌 | 規格、契約、守門類——「本格」的硬內容 |
| `neon` | 霓虹 | 深紫（dark） | Huuuge Casino：紫藍桃紅、金屬金字、霓虹輪廓 | 金屬漸層章名 + 霓虹發光 callout；punchline 是跑馬燈牌 | 成果展示、案例書、「做出來了」 |
| `shonen` | 熱血 | 白 + 能量色 | 七龍珠 Dokkan：黃字多層黑描邊、放射線、名場面放大 | 章名壓在斜切能量帶上、章首放射線；每章一種能量色 | 快速上手、衝刺教程、要人立刻動手 |
| `manga` | 收藏 | 奶白 + 網點 | 二次元收藏：對白框、角色卡、稀有度 | callout 是對白框；難度徽章帶 ★ | 新人手冊、輕鬆入門、降低防備心 |
| `console` | 實機 | 深藍黑（dark） | 實機畫面與易懂玩法：HUD、進度條、等寬字 | 每個 section 是 HUD 面板（角括）；章號顯示 STAGE | 腳本與工具操作手冊、指令密集 |

### 怎麼選

- 讀者要「坐下來讀懂一套方法」→ `library`
- 內容是「規則、契約、守門，不照做會出事」→ `felt`
- 要給主管或其他團隊看「我們做到了什麼」→ `neon`
- 短書、目標是「30 分鐘內動手做出第一個」→ `shonen`
- 讀者是新人、內容是「別怕，很簡單」→ `manga`
- 一半以上篇幅是指令與輸出 → `console`

同一本書的所有章節用同一風格；不同書可以不同，圖書館書架上才看得出類型。
`shonen` 的每章能量色與 `felt`/`library` 的書脊色都取自 `book.yaml` 的 `cover.spine_color` 循環，不用另外設。

## 新增一種風格（三步）

1. **複製一個最接近的 css** 到 `assets/styles/{name}.css`。
   `:root{}` 必須完整供應 ark-html-report token 契約的全部變數（`--bg` `--surface` `--surface-2` `--border` `--text` `--text-2` `--text-3` `--accent` `--accent-soft` `--ok` `--warn` `--danger` `--info` `--c1`~`--c6` `--font-display` `--font-body` `--font-mono` `--radius` `--radius-sm` `--shadow` `--maxw`），
   外加 ark-book 擴充的四個（`--oak` `--oak-dark` `--brass` `--brass-2`，書脊與頁尾用）。缺一個變數，該元素會退回瀏覽器預設色。
2. **母題覆寫全部用 `body[data-style="{name}"]` 前綴**，只覆寫模板既有的 class（`.shelf` `.spine` `.ch-head` `.punchline` `.section` `.callout.*` `.nav` `.progress` `.cover`），不新增 HTML 結構——`book_build.py` 不會為某個風格多產標籤。
3. **在 `_manifest.json` 登錄**：`name`（= 檔名）、`label`、`dark`（true 會加 `<body data-theme="dark">`，Chart／消費端據此換 grid 色）、`inspiration`、`use_for`、`motif`。登錄後 `--list-styles` 可見、lint 接受 `book.yaml style:` 使用它。

自檢：`book_build.py books/{slug}/ --style {name} --out /tmp/{name}.html`，開啟後看六件事——
封面、書脊目錄選中態、punchline、四種 callout（ask／myth／try／tip）、code block、重點回顧第一張卡。
另用 390px 寬看一次：不能有橫向捲動。

## 外部風格

`--style editorial --styles-ref /path/ark-html-report/references/styles.md` 可直接借 ark-html-report 的五種 token（boardroom／terminal／midnight／editorial／paperprint），只有 token、沒有母題覆寫，適合要跟報告視覺一致的場合。

## 圖書館網站怎麼用這些風格

`catalog.json` 每本書的 `style` 欄位由 `book_register.py` 從 book.yaml 帶入。圖書館書架可以依 style 換書脊質感（牌桌書用象牙牌、霓虹書發光），也可以不理它，統一用 `cover.spine_color`——契約兩個欄位都保證有。
