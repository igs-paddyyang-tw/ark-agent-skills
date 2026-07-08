---
name: ark-report-generation
description: |
  報告產出與彙整：收集數據 → 套模板 → 渲染圖表 → 品質檢查 → 輸出。
  觸發：當使用者提到 報告、日報、weekly、月報、HTML、摘要。
---

# 報告產出 Skill

## 步驟
1. 收集各 Agent 的產出數據
2. 選擇模板（日報 / 週報 / 專題）
3. 套用模板（Jinja2 / Markdown）
4. 渲染圖表（Chart.js / 表格）
5. 品質檢查（完整性、格式）
6. 輸出檔案（.md / .html）

## 輸出格式
- Markdown（內部分享）
- HTML（外部展示，暗色科技風）
- 每份報告必須有「一句話結論」
