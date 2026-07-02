---
title: "系統架構概覽"
type: system
tags: [architecture, config]
created: 2026-07-02
---
# 系統架構
- agents/ 目錄下每個 Agent 有獨立 .kiro/ 配置
- /agents 指令叫出 Inline Button 切換
- 每次對話後自動寫入 memory
- knowledge/raw/ → ingest → knowledge/wiki/
