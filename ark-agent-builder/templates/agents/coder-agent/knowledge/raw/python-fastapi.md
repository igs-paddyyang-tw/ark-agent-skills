---
title: "Python + FastAPI 開發慣例"
type: concept
tags: [python, fastapi, coding]
created: 2026-07-02
---
# 開發慣例
- from __future__ import annotations
- 型別標註：str | None（不用 Optional）
- async/await 所有 I/O
- Path 物件取代字串路徑
- encoding="utf-8" 明確指定
- logging.getLogger(__name__)
