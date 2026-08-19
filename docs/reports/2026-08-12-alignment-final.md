---
title: "ark-agent-skills 對齊執行報告（v1.1）"
type: review
subject: "ark-agent-skills"
date: 2026-08-12
author: admin
source_skill: ark-md-report
verdict: needs-work
confidence: high
findings: { p0: 0, p1: 0, p2: 0 }
tags: [skill-review, alignment, metadata]
sources:
  - ark-skills-align v1.1/scripts/audit_skills.py（稽核）
  - ark-skills-align v1.1/scripts/backfill_metadata.py --dry-run（歸屬檢查）
  - ark-skills-align v1.1/references/taxonomy.md（歸屬表）
---

# ark-agent-skills 對齊執行報告

## 結論

**稽核層面已對齊（P0/P1/P2/P3 全 0，退出碼 0）；
但 `taxonomy.md` 歸屬表落後實際 13 個 skill —— 需要你裁決後才能收尾。**

**未執行任何結構性改動。** `docs/alignment/` 仍不存在，
skill 第一原則是「指令文件是 source of truth，文件沒有的決策不執行，先回報」。

## 依 workflow 逐步執行結果

| 步驟 | 內容 | 結果 |
|---|---|---|
| 0 | 取得輸入 · 找 Directive | ⚠️ `docs/alignment/` **不存在** |
| 1 | 基線稽核 | ✅ P0/P1/P2/P3 = **0**，exit 0 |
| 2 | 依 Phase 執行 Directive | ⛔ **阻塞** —— 無 Directive |
| 3 | Phase 收尾 | — 無 Phase 可收 |
| 4 | 最終報告 | ✅ 本文件 |

> 「0 findings」已驗過不是空掃：`active_skills=65`、`deprecated_stubs=4`。

## 🟠 稽核抓不到、但 `backfill --dry-run` 抓到的落差

`audit_skills.py` 只驗 frontmatter 本身合不合規，**不驗「有沒有被寫進歸屬表」**。
跑 `backfill_metadata.py --dry-run` 得到 **59 OK / 7 UNMAPPED**。

進一步比對 `taxonomy.md` 歸屬表與實際 frontmatter：

| category | 實際 | 歸屬表 | 表頭宣稱 | 歸屬表缺漏 |
|---|---:|---:|---|---|
| `pipeline` | 22 | 15 | 14–15 | agent-cli · api-doc-sync · data-contract · eval-runner · ingest-guard · llm-cli · telegram-sender |
| `document` | 11 | 9 | 7–8 | markdown-formatter · news-daily · release-notes |
| `view` | 8 | 7 | 7 | data-dashboard · theme-factory |
| `scaffolder` | 9 | 9 | 8 | chatbot-generator |
| `process` | 9 | 9 | 9 | — |
| `domain` | 4 | 4 | 4 | — |
| `ops` | 3 | 3 | 3 | — |
| **合計** | **66** | **56** | — | **13** |

**表頭宣稱的數字也全部落後**（`pipeline（14–15）` 實際 22、`document（7–8）` 實際 11）。

### 歸屬表有、但實際不符的 3 項

| skill | 歸屬表列在 | 實際 | 判讀 |
|---|---|---|---|
| `ark-report-template` | `document` | 已 stub（無 `SKILL.md`） | 🟢 純落後，應從表中移除 |
| `ark-llm-cli` | `scaffolder` | `category: pipeline` ＋ **`status: deprecated`** | 🟢 降級中，應從表中移除 |
| `ark-news-daily` | `view` | `category: document` | 🔴 **需裁決** —— 且它稽核前是 `pipeline`，一天內出現三個值 |

## 🔴 順帶發現：`status: deprecated` 是第二種「半降級」樣態

`ark-llm-cli` **`SKILL.md` 完整存在、`category` 正常**，只有 `status: deprecated`。

這與 08-12 早上的 `ark-report-template`／`ark-postmortem`（完全 stub、無 `SKILL.md`）
**是不同樣態**。任何「複製 skill」的工具若只判斷「有沒有 `SKILL.md`」，
會把它整包裝走且完全無感 —— 檔案齊全、複製成功、audit 不報錯。

> **判斷「能不能用」不能只看檔案在不在。**
> fish 的 `sync_skills.py` 首版就只認第一種，已補上 `status != active` 的判斷並實測擋下。

## 需要你裁決

**① `ark-news-daily` 歸哪一類？**
歸屬表 `view` ／ 現行 frontmatter `document` ／ 稽核前 `pipeline`。
它產出每日新聞 md ＋ HTML，三種說法都講得通 —— 這是分類決策，不該由我代決。

**② 歸屬表要不要由 frontmatter 生成？**
README 已經改成「由 frontmatter 產生，不手寫」。
`taxonomy.md` 的歸屬表是同一類問題 —— 手寫必然再次落後。

| 選項 | 說明 |
|---|---|
| A | 歸屬表改為腳本生成（與 README 同一機制），表頭數字自動帶入 |
| B | 維持手寫，這次補上 13 個並更新表頭數字 |
| C | 廢掉歸屬表，`taxonomy.md` 只留受控詞彙與 outputs 規格，歸屬以 frontmatter 為唯一真相 |

> 傾向 **C** —— 歸屬表的資訊 100% 可從 frontmatter 導出，留著就是第二份真相。
> 但它同時承載 `D-2 後`／`D-8 後` 這類 directive 意圖註記，廢掉會失去那段脈絡，
> 需要先確認那些註記是否已完成。

## 仍缺的東西

**Alignment Directive。** `taxonomy.md` 內文持續引用 `D-2`、`D-8` 等編號，
代表 directive 確實存在但不在 repo 內。目前稽核已清零故不影響現況，
但下次任何合併／移除／降級都需要它。

## repo 現況

- 本地 HEAD `da53bd1`，**領先 GitHub remote 2 commits**（remote 仍在 `c4304be`）
- **73 個未提交變更** —— 本報告的稽核對象是工作區狀態，不是任何一個 commit
- 建議：commit ＋ push 後再跑一次稽核作為**正式基線**，
  否則下次比對沒有可回溯的參考點
