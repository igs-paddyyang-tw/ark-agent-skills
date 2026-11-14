# 魚機快測契約 v1（`scripts/fish/qt_fish_run.py`，2.4.0）

> 技能不帶 Go 模擬器：每款魚機在自己的 go-server 寫 `cmd/fishsim`（走正式建桌路徑、虛擬時鐘、每幀開 N 發、依打法挑魚），
> 只要**命令列旗標**與**輸出 JSON** 照本契約，就能接 `qt_fish_run.py`。方法論見知識庫 `fish-quicktest-method`。

## qt-config.yaml（每款一份，建議放 `data/fish/<slug>/quicktest/`）

```yaml
tool: data/fish/<slug>/game/go-server/cmd/fishsim   # Go 套件目錄（會 go build）或已編譯執行檔；.py 用目前 Python 跑
config: data/fish/<slug>/game/go-server/configs/<slug>.json
bet: 1
per_frame: 8                     # 每幀開火數 → fishsim -per
runs:                            # 打法 × 種子；gate 只看 aim=random
  - { aim: random,   seeds: [1, 2, 3], shots: 20000000 }
  - { aim: gold,     seeds: [1],       shots: 20000000 }   # 最佳比值（附加獎勵率 ÷ 倍率最高）
  - { aim: cheapest, seeds: [1],       shots: 20000000 }
  - { aim: richest,  seeds: [1],       shots: 20000000 }
gate: { total: 0.96, tolerance: 0.005 }
# ── 選配 ──
slug: <slug>                     # 預設：qt-config 在 <slug>/quicktest/ 下取 <slug>，否則取所在目錄名
title: 貓魚傳說                  # 報告標題用，預設 slug
out_dir: data/fish/<slug>/quicktest/qt-report      # 預設 qt-config 同層 qt-report/
runs_dir: output/fish/<slug>/qt-runs               # 原始 JSON（不進 git）；預設 output/fish/<slug>/qt-runs
bonus_key: bead                  # 副玩法 RTP 鍵名（rtp.<bonus_key>），預設 bead
aim_deviation: 0.01              # 最偏打法偏離目標超過此值 → F-2 P2；總 RTP > 1 → P1
fields:                          # 設定檔 JSON 欄位名覆寫（以下為預設）
  { game_rate: game_rate, fish_list: fish_info, type: type, name: name, odds: odds, drop_ppm: drop_ppm }
```

- 路徑（`tool`／`config`／`out_dir`／`runs_dir`）相對 `--root`（預設目前目錄）；絕對路徑原樣。
- 命令列 `--out-dir`／`--runs-dir` 優先於 qt-config；`--shots` 覆寫每個 run 的發數（煙霧測試）。
- 未知欄位（如 `bead_policy`）原樣忽略，可當註記。

## fishsim 命令列

```
fishsim -config <設定檔.json> -shots <N> -seed <S> -aim <打法> -per <每幀發數> -bet <押注>
```

同一組旗標必須**可重現**（同 seed 同結果）；stdout 只輸出一個 JSON 物件，進度訊息走 stderr。

## fishsim 輸出 JSON

| 鍵 | 必填 | 型別 | 說明 |
|---|:-:|---|---|
| `rtp.fish` | ✅ | float | 打魚段 RTP |
| `rtp.total` | ✅ | float | 總 RTP（gate 判這個） |
| `rtp.<bonus_key>` | | float | 副玩法 RTP（例 `bead`）；沒有副玩法可省 |
| `per_fish.<type>.shots` | ✅ | int | 打這種魚的發數 |
| `per_fish.<type>.kills` | ✅ | int | 打死數（命中率實測＝kills ÷ shots） |
| `per_fish.<type>.rtp` | ✅ | float | 單魚 RTP（應接近 game_rate） |
| `per_fish.<type>.name` | | str | 缺則取設定檔 |
| `per_fish.<type>.beads` | | int | 附加獎勵掉落數（附加獎勵率實測＝beads ÷ kills）；有它且設定檔有 `drop_ppm` 才比對 |
| `aim`／`seed`／`shots` | | | 缺則用命令列值 |
| `analytic` | | `{fish, <bonus_key>, total}` | 解析近似（只當守門，F-x P3 對照） |
| `beads_per_1000` | | float | 每千發附加獎勵 |
| `triple_rate` | | float | 副玩法三同率等特徵率 |

`<type>` 為設定檔 `fish_info[].type` 的字串；不在設定檔的魚種 → exit 2。其餘鍵原樣保留進 `rtp-report.json`。

## 理論值（由設定檔算）

| 量 | 公式 | 區間 |
|---|---|---|
| 命中率 | `game_rate ÷ odds`（單人無緩衝池時成立） | 二項 95%：p ± 1.96·√(p(1−p)/shots) |
| 附加獎勵率 | `drop_ppm ÷ 1e6` | 二項 95%：p ± 1.96·√(p(1−p)/kills) |

## 產物（out_dir）

| 檔 | 內容 |
|---|---|
| `rtp-report.json` | `game`、`config{path, sha16, note}`、`qt_config`、`qt_config_sha16`、`target`、`params`、`analytic`、`gate{aim, seeds, totals, mean, seed_ci95, pass}`、`runs[]`（每 run 加 `within_gate`、每魚加 `hit_*`／`drop_*`／`shot_share`） |
| `<date>-quicktest-<slug>.md` | ark-md-report `type: data`（report_lint 必過） |
| `<date>-quicktest-<slug>.html` | 單檔 View 軌，report_pair 戳記 |

## Findings 與 exit

| ID | 規則 | 嚴重度 |
|---|---|---|
| F-1 | random 各種子總 RTP 都在 target ± tolerance | 過 P3／不過 P0 |
| F-2 | 打法敏感度：非 random 中偏離目標最大者；任一打法總 RTP > 1 | > 1 → P1；偏離 > `aim_deviation` → P2；否則 P3；沒跑偏打法 → P2 |
| F-3 | 命中率落在 95% 區間外格數 > run 數 ÷ 4 | P2，否則 P3 |
| F-4 | 附加獎勵率同上（有 beads 才出） | P2，否則 P3 |
| F-5 | 解析近似 vs 實測平均（有 analytic 才出） | P3 |

exit：0＝gate 過、3＝gate 不過、2＝輸入錯誤或執行失敗（tool／config 不存在、fishsim 失敗、輸出不合契約）。
verdict 只看 gate；F-2～F-5 交人判斷，不下設計結論。
