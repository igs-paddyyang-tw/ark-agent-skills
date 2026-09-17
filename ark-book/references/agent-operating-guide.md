# Agent 操作指南（提詞片段與路由）

給 team agent（leader / worker）在運作時決定「這件事該不該寫成書、怎麼寫、寫完交給誰」。

## 路由：報告、wiki 頁、還是書？

```
收到「整理／教學／文件化」類任務
├─ 有明確分析對象、要給結論（verdict）、時點快照 ────────▶ ark-md-report
├─ 是一個持續演化的概念條目、給 AI 查 ───────────────────▶ ark-wiki-engine（wiki 頁）
├─ 要教會人做一件事、會被反覆閱讀、有先後順序 ──────────▶ ark-book（本 skill）
│    ├─ 目標不清楚讀者是誰 ──▶ 先 ark-grill-me
│    └─ 只有一章的量（< 3 個能力）──▶ 先寫成 wiki 頁，累積到 3 章以上再成書
└─ 只是要一頁給主管看的總結 ─────────────────────────────▶ ark-html-report
```

判斷句：「這東西三個月後還會有人照著做嗎？」是 → 書；「這東西是某個時間點的判斷嗎？」是 → 報告。

## 觸發詞（獨占，與其他 skill 不重疊）

- 寫一本書、做教材、教學文件、新人手冊、onboarding 教程、教學網站
- 「把 X 的用法寫成教學」「整理成可以放進圖書館的書」「給成員學的知識庫」

近似但**不是**本 skill：
- 「分析報告」「review 報告」「決策摘要」→ ark-md-report
- 「投影片」「簡報」→ pptx / deck
- 「建 wiki」「知識庫引擎」→ ark-wiki-engine
- 「HTML 報告」「網頁版報告」→ ark-html-report

## 提詞片段

### Leader：指派寫書任務

```
任務：用 ark-book 把「{主題}」寫成一本書，目錄先給我審。
讀者：{audience 一句話}。
讀完要會：{outcomes 2–5 條，動詞開頭}。
素材：{sources 路徑清單}；素材不足的地方標 confidence: low，不要硬寫。
不教：{scope_out}。
交付：books/{slug}/ 全部章節 lint PASS、site/index.html、catalog 已登錄。
每章交付前跑 references/teaching-engine.md 的自評清單，把不合格項列出來給我。
```

### Worker：寫章節前的自我提醒

```
寫 {NN}-{slug}.md 之前：
1. 先寫 punchline，寫不出一句就回去看素材
2. 「這章要解決的問題」用讀者自己的專案名與指令，以「怎麼辦？」收尾
3. 每個術語：先例子 → 命名 → 規則 → 第二個例子
4. 至少一個 [!ASK]、一個 [!MYTH]、一個可執行的 [!TRY]
5. 寫完跑 book_lint.py，FAIL 就修；再過一次自評清單
```

### Reviewer：審一章

```
只回答四個問題，每題給證據（引用章內原句）：
1. 把所有「X 是…」開頭的句子刪掉，剩下的能教會人嗎？
2. 有沒有一條「因為…所以…」貫穿全章？
3. 動手做照著執行會成功嗎？成功的樣子有寫嗎？
4. punchline 一週後記得嗎？跟回顧第一句一致嗎？
任一題答否 → 退回，附該題證據。
```

### Librarian（登錄與上架）

```
python scripts/book_lint.py books/{slug}/ && \
python scripts/book_build.py books/{slug}/ && \
python scripts/book_build.py books/{slug}/ --check && \
python scripts/book_register.py books/{slug}/
回報格式：書已落盤 books/{slug}/｜{N} 章｜lint: PASS｜site: …｜catalog: 已登錄
任一步 exit 1 → 停下回報那一步的輸出，不要繼續。
```

## 與閉環 B 的接點

在「grill → superpowers → spec-executor → validator → wiki → report」的任務迴圈裡，書出現在兩個位置：

1. **輸入端**：任務開始前，agent 先查 catalog.json 有沒有一本書已經教過這件事（`tags` 命中）——有就先讀那本書的對應章節，不重新摸索
2. **輸出端**：任務結束後，若 validator 的 Drift Report 顯示「同一個坑第三次」，leader 開一個寫書任務，把坑變成一章

## 禁止

- 不把報告改幾個字就當書：報告有 verdict，書有 punchline，兩者不能互換
- 不在書裡下未經驗證的操作指令：動手做的指令必須實跑過或標 `confidence: low`
- 不對特定人事物做負面評價（與 hung-yi-lee-skill 本人硬規則一致）：批評做法與取捨
- 不繞過 lint：LLM 自評「格式應該對了」不算通過
