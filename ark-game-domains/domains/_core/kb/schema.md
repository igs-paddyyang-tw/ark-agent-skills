---
domain: game-core
contract: "1"
---
# game-core 受控詞彙（core tags）

pack 只能新增 tag，不能重定義下列 core tags。

| tag | 定義 |
|-----|------|
| game-loop | 主流程與狀態轉換 |
| trigger | 進入特殊機制的條件 |
| reward | 獎勵給付方式 |
| bonus | 任何獨立於主玩法的獎勵段落 |
| multiplier | 倍率機制 |
| jackpot | 累積或固定大獎 |
| ui | 介面元件與互動 |
| animation | 動畫與回饋 |
| math | 數學模型相關（觀察不到時只能 UNKNOWN） |
| project | 專案級決策與經驗 |
| buy-feature | 付費直入特殊機制 |
| autoplay | 自動進行 |
| history-display | 歷史結果顯示 |
| wheel-bonus | 轉盤類 bonus |
| pick-bonus | 選擇類 bonus |

## alias（同名同義表）
- free-spins → free-spin
- auto → autoplay
