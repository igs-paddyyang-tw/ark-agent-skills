---
title: "RRF 融合"
type: concept
status: developing
trust: deterministic
approved: true
tags: [search]
created: 2026-05-02
updated: 2026-08-02
---
# RRF 融合

Reciprocal Rank Fusion：score = sum(1 / (k + rank))，k 常取 60。
用於合併多層檢索結果，見 [[bm25-scoring]]
