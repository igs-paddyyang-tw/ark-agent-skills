# intake/design.md — design 訪談題庫（ADR-005）

對應 spec 的 FR/NFR/C，產出設計決策與架構。不確定的架構級決策 → 開 `ADR-NNN` 而非腦補。

| # | 章節鍵 | 問題 | 產出 |
|---|--------|------|------|
| 1 | overview | 這份設計要落地 spec 的哪些需求？一段話總覽方案 | 概述 |
| 2 | context | 現況/限制/證據來源是什麼？ | 背景 |
| 3 | adr | 有哪些需要在選項間拍板的架構級決策（≥2 選項、含負面後果）？ | ADR-NNN（獨立檔） |
| 4 | architecture | 模組怎麼切、資料怎麼流、元件有哪些？ | CMP-x / API-x |
| 5 | failure | 每個故障場景的影響範圍與降級行為？ | 故障隔離 |

> 架構級決策（涉及 ≥2 個 CMP 或有 CF- 機檢規則）走 `build_docs.py adr` 建獨立檔，
> design 內只留 `DD-x`（非架構級設計決策）+ 連結引用 ADR-NNN（不內嵌 ADR 標題）。
