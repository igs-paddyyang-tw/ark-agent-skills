# Gaming Dashboard Preset — 博奕遊戲面板

> 從 ark-data-dashboard 萃取的博奕遊戲領域模型與面板規格。
> 使用 ark-html-dashboard 產出博奕相關 dashboard 時載入此 preset。

## 觸發條件

以下關鍵字觸發此 preset：
- 「遊戲面板」、「game dashboard」、「博奕分析」
- 「老虎機資訊」、「遊戲資料視覺化」
- 「遊戲卡片」、「遊戲統計」、「slot 分析」

## 標準化資料模型 — GameInfo

```python
class GameInfo:
    name: str
    provider: str
    game_type: str = "slot"         # slot / poker / baccarat / roulette
    icon: str = ""
    url: str = ""
    stars: int = 0
    rtp: float | None = None
    volatility: str | None = None   # low / medium / high / very_high
    mechanics: list[str] = []
    theme: str | None = None
    layout: str | None = None       # "5x3", "6x4 Megaways"
    max_multiplier: float | None = None
    confidence: float = 0.0         # 解析信心度 0-1
```

## 遊戲卡片規格

### 基本卡片

```
┌──────────────────────────────────────────┐
│ [icon 52x52]  Name                 [🔍]  │
│               Provider                    │
│               ★★★★☆                      │
└──────────────────────────────────────────┘
```

### 展開後（含數值規格）

```
┌──────────────────────────────────────────┐
│ [icon 56x56]  Name                        │
│               Provider                    │
│ ┌──────┐ ┌──────┐ ┌──────┐               │
│ │ RTP  │ │ 波動率│ │ 倍率 │               │
│ │96.5% │ │ high │ │15000x│               │
│ └──────┘ └──────┘ └──────┘               │
│ [Free Spins] [Tumble] [Multiplier]       │
└──────────────────────────────────────────┘
```

## 支援遊戲類型

| 類型 | game_type | 特有欄位 |
|------|-----------|---------|
| 老虎機 | `slot` | rtp、volatility、mechanics、layout |
| 撲克 | `poker` | hand_types、betting_structure |
| 百家樂 | `baccarat` | house_edge、side_bets |

## 推薦圖表

| 場景 | 圖表類型 | 說明 |
|------|---------|------|
| 廠商分佈 | bar chart | 各 provider 遊戲數量 |
| RTP 分佈 | histogram | RTP 值分佈區間 |
| 波動率佔比 | pie/doughnut | low/medium/high/very_high 比例 |
| 星等趨勢 | line chart | 按時間或廠商的平均星等 |

## 風格建議

- **預設 theme**: `dark`（遊戲數據場景開發者習慣暗色）
- **業務報告場景**: 可切 `light`
- CSS class 命名：`.game-grid` `.game-card` `.mech-card` `.stats-panel`

## 注意事項

- GameInfo 為通用模型，不同遊戲類型共用相同欄位
- 正則提取可能因網站格式變更而需調整
- HTTP 請求必須帶瀏覽器 User-Agent headers
