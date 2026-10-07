# fish-game primer（給 agent）
- 連續即時遊戲，**沒有回合**；資訊在擊殺瞬間（分數彈出）。
- 倍率**可觀察**（彈出分 ÷ 砲注），命中率**不可觀察**（永遠 UNKNOWN）。
- 多人房他人擊殺不算本玩家 evidence；ROI 需綁座位。
- motion 永遠很高，settle 類偵測無效；靠 roi_change / flash / scene_change。
