---
title: "ark-agent-skills 全庫對齊稽核（基線 → v1.1 清零）"
type: review
subject: "ark-agent-skills"
date: 2026-08-12
author: admin
source_skill: ark-md-report
verdict: sound
confidence: high
findings: { p0: 0, p1: 0, p2: 0 }
tags: [skill-review, alignment, metadata]
sources:
  - ark-agent-skills/（65 active skill + 4 deprecated stub）
  - ark-skills-align v1.1/scripts/audit_skills.py
  - ark-skills-align v1.1/references/taxonomy.md
---

# ark-agent-skills 全庫對齊稽核

## 結論

**通過。** `ark-skills-align` **v1.1** 稽核 **P0/P1/P2/P3 全為 0，退出碼 0（放行）**。

| | v1.0 稽核 | v1.1 稽核 |
|---|---:|---:|
| P0 | 0 | 0 |
| P1 | **54** | **0** |
| P2 | **13** | **0** |
| 退出碼 | 1（未放行） | **0（放行）** |
| active skill | 66 | 65 |
| deprecated stub | 3 | **4** |

> ⚠️ **「0 findings」先驗過不是空掃** —— `active_skills=65`、`deprecated_stubs=4`，
> 掃描範圍正常。0 findings 最危險的解讀是「什麼都沒檢查到」，
> 所以任何歸零結果都要先確認分母。

## 清零的兩個來源（缺一不可）

### ① v1.1 反轉了命名決策

v1.0 的受控詞彙是**短名**，但 66 個 skill 的 frontmatter 多數是**長名** ——
41 個 `invalid-category` 全部出自這一個落差。

**v1.1 改以長名為 canonical**，短名降為 legacy alias：

```python
CATEGORY_CODES = {"process", "scaffolder", "pipeline", "view", "document", "domain", "ops"}
LEGACY_CATEGORY_ALIASES = {          # 舊值 → canonical，觸發 P3（過渡期容忍）
    "proc": "process", "scaffold": "scaffolder", "present": "view",
    "doc": "document", "sop": "domain",
    "presentation-content": "document",   # md-report 舊值，語意歸 Content 軌文件
}
```

同時把「`category: deprecated`」明確定為錯誤（P1 `category-is-status`）——
**deprecated 是 status 不是 category**，正是基線稽核指出的狀態表達不一致。

### ② repo 內容同步修正

抽查證實不只是稽核放寬，檔案本身也改了：

| skill | 基線 | 現況 |
|---|---|---|
| `ark-md-report` | `presentation-content` | `document` |
| `ark-theme-factory` | `deprecated` | `view` ＋ `status: active` |
| `ark-markdown-formatter` | `deprecated` | `document` ＋ `status: active` |
| （一個 skill） | active | 轉為 deprecated stub（66→65、3→4） |

**兩者缺一都不會歸零**：只改稽核 → `presentation-content` 仍在但被 alias 吸收（降 P3 不是 0）；
只改內容 → 長名仍不在 v1.0 的受控詞彙裡。

## 基線稽核提出的兩個待決問題 —— 皆已由 v1.1 回答

| 問題 | v1.1 的答案 |
|---|---|
| 短名還是長名為權威？ | **長名**（短名降為 legacy alias，過渡期報 P3） |
| `presentation-content`（`ark-md-report`）歸哪類？ | **`document`** |
| （附帶）`category: deprecated` 怎麼處理？ | 定為 **P1 錯誤**，改用 `status: deprecated` ＋ stub 格式 |

## 觸發詞衝突（基線 9 項）—— 現況為 0

基線列出 9 項獨占觸發詞誤用（`爬蟲`／`截圖`／`產 spec`／`博奕` 等）。
v1.1 稽核已無此類 finding，代表 description 也一併整理過。

> 這類改動有觸發風險，skill 原則要求「description 改動獨立 commit
> 且逐 skill 附 3 個觸發測試 prompt」—— **本報告未驗證那些測試是否有做**，
> 只確認稽核規則不再命中。

## 仍未取得的東西

**Alignment Directive 仍不在 repo 內。** `taxonomy.md` 內文持續引用 `D-2`、`D-8` 等編號，
但 `docs/alignment/` 不存在。目前稽核既然已清零，**不影響現況**；
但下次要做結構性改動（合併／移除／降級）時仍需要它 ——
skill 第一原則是「文件沒有的決策不執行」。

## repo 現況

- 本地 HEAD `da53bd1`，**領先 GitHub remote 2 commits**（remote 仍在 `c4304be` 2026-08-11）
- **73 個未提交變更** —— 本次稽核對象是工作區狀態，不是任何一個 commit
- 建議：commit ＋ push 後再跑一次稽核作為正式基線
