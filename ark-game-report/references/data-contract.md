# 資料契約

## A. 標準資料集（data_dir 下的 CSV，UTF-8）

只有 `game_user_daily.csv` 是必要的；其他缺了，對應區塊會降級並在報告註明（gr_probe 會列出）。

| 檔案 | 粒度 | 必要欄位 | 選配欄位 | 用在 |
|------|------|---------|---------|------|
| `game_user_daily.csv` | 本機 × 玩家 × 日 | `d`（YYYY-MM-DD）、`uid`、`bet`、`spins` | `win`；`trig_<特色名稱>`（觸發次數）；分層欄位（例如 `vip`、`market`、`reg_days`）| 全部 |
| `slot_daily.csv` | 切分 × 日 | `view`、`d`、`slot_bet`、`slot_players` | `game_rank` | Q1 佔比、試玩率、排名 |
| `slot_users.csv` | 期間內有玩虎機的玩家 | `uid` | 分層欄位（和 game_user_daily 同名）| Q2 對照、Q4 試玩率 |
| `erosion.csv` | 機台 | `game`、`pre_bet`、`post_bet` | — | Q6 |
| `hours.csv` | 時段 | `bucket`、`bet` | — | 健康觀察 |
| `benchmark.csv` | 指標 × 天 | `metric`、`day`、`p30`、`p50`、`p60` | `view` | 燈號基準 |

規則：

- **本機要合併**：本機的所有子 ID 要合併成一列（玩家 × 日）。
- **slot_daily 的 view 要對得上**：`view` 值必須和 report.yaml `views[].name` 一致。
- **erosion 的兩個特殊列**：
  - `__TARGET__`：本機本身。
  - `__ALL_SLOTS__`：全虎機總量，前後窗口都要有。
- **分層欄位**：欄名寫在 report.yaml 的 `views[].column`、`composition[].column`。數值型用 `buckets`，類別型用 `categories`。
- **觸發欄位命名**：`trig_` 加上 report.yaml `spec.triggers` 的鍵名，例如 `trig_Free Game`。

## B. report.json（render 的輸入）

gr_build 產生；也可以由任何系統直接產生後交給 gr_render。結構：

```jsonc
{
  "meta": {"game_name", "game_id", "launch_date", "data_through", "stage", "benchmark_label"},  // 前四個與 stage 必填
  "verdict": {"headline", "lights": {"Q1".."Q6","H": "g|y|r|na"}, "next": [..]},
  "views": {
    "<切分名>": {
      "verdict": {...},                                            // 可覆寫全域 verdict
      "kpi": [{"label","value","note"}],
      "share": {"days", "game", "bench_p30", "bench_p50", "bench_p60"},
      "composition": [{"title","groups","game","all","base_label"}],
      "retention": {"days", "game", "bench", "cohorts": [{"date","users","values"}]},
      "depth": {"columns", "rows"},
      "rtp": {"days", "actual_cum", "target", "lo", "hi"},
      "triggers": [{"name","spec","actual","deviation","status"}],
      "sources": [{"name","delta","note"}],
      "increment": [{"label","value","note"}],
      "health": {"tiles": [{"label","value","note"}], "hours": {"labels","values"}}
    }
  },
  "definitions": [["名詞","定義"]],
  "footnote": "限制與降級說明",
  "capability": {"Q1": "ok|partial|skip", ...}
}
```

一致性規則：

- 各序列長度要等於 `days`。
- 世代熱圖每列的欄數要等於 `retention.days`。
- 組成的 `game`、`all` 各自加總要等於 1（容許 ±0.02）。

`gr_render --check` 會驗。
