# dev-spec 六檔 ↔ 機率企畫 13 步流程（slot）
| STEP | 內容 | 對接檔 | 邊界 |
|------|------|--------|------|
| 00（隱含）| 競品研究 | 整條鏈取代 | — |
| 01 | 規劃建立架構（4.5→2 天目標）| game-spec.md, feature-spec.md, state-machine.md | 架構輸入 |
| 02 | 建 EXCEL 表（5→3 天）| config-spec.yaml → ark-xlsx-tool | **只給結構，parameters.value 一律 null** |
| 03 | 架構流程圖（<20 分）| state-machine.md | 直接可用 |
| 04 | 寫快測（5→2 天）| qa-checklist.md | case 來源 |
| 05–09 | 對 Chance / 調整 | 不對接 | Math 為 Out of Scope |
| 12–13 | 定版報告 / 送審 | game-spec.v1.md 章節 | 另議 |
