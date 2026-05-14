# 標準化遊戲資料模型

## GameInfo — 通用博奕遊戲資訊

```python
class GameInfo(BaseModel):
    name: str                       # 遊戲名稱
    provider: str                   # 遊戲廠商
    game_type: str = "slot"         # slot / poker / baccarat / roulette
    icon: str = ""                  # 遊戲圖示 URL
    url: str = ""                   # 遊戲詳情頁 URL
    stars: int = 0                  # 星星評分 0-5
    rtp: float | None = None        # Return to Player %
    volatility: str | None = None   # low / medium / high / very_high
    mechanics: list[str] = []       # 核心玩法
    theme: str | None = None        # 遊戲主題
    layout: str | None = None       # 版面配置 "5x3"
    max_multiplier: float | None = None  # 最大倍率
    confidence: float = 0.0         # 解析信心度 0-1
```

## 設計原則

- 所有遊戲類型共用相同模型，不需要子類別
- 選填欄位用 `None` 表示「未知」
- `game_type` 用於前端渲染時選擇不同的卡片樣式
- `confidence` 由解析器自動計算，非人工填寫
- `model_dump()` → `GameInfo(**dict)` round-trip 保證
