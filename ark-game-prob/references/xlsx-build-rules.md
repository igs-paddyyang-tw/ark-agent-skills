# ark-game-prob Excel 產出規則（ps_xlsx / _xlsx_lib）

> 第三條 View 軌：md 給三方對話、html 給人看、**xlsx 給機率同仁操作與審核**。
> 吸收自 game-prob-table-excel（公版機率表規則），去遊戲化；開司 / 彌勒佛為 worked example。

## 黃金律（_xlsx_lib 以函式強制）

1. **零手抄**：所有值從 canonical JSON（prob-data.json / 設定檔 JSON / rtp-report.json / config-diff.json / lint-report.json）dump，不從 md 反解、不貼算好的結果。Go 硬編先 marshal 成 JSON。
2. **派生＝活公式**：Σ=`SUM()`、顆數=`COUNTIF()`、轉置=`VLOOKUP()`、偏差=`RTP/golden-1`、檢核=`IF` 鏈，全部是公式字串（`=` 開頭），不貼值。
3. **輸入／公式／參考三色分區**：輸入格淡藍（`IN`，人可改）、公式格灰（`FM`，鎖定）、參考值白。
4. **每頁一個總閘**：`gate_summary` 落 `X 不可交付：n` / `! 需簽核：n` / `OK 全部通過`；審核簿總覽彙總各頁。
5. **門檻放可調格不寫死**：警告／錯誤門檻、golden、售價都是輸入格，公式引用其位址（如 `$C$1`/`$E$1`）。
6. **權重和檢查**：每條權重列旁 Σ，Σ≠約定和（100/1000）→ `!`。
7. **_meta 戳記**：隱藏分頁記每個來源 path + sha16 + 產生時間；ps_lint PS-STALE 驗。
8. **文字型 `=` 開頭強制字串**：`gate_cell` 對 `=規格` 這種非公式文字設 `data_type="s"`，避免被當公式。
9. **null → 待決議**：參數表 null 顯「待決議」黃底（`PF`）；**檢核表輸入格 null 留空 + 淡藍底**（人填，非待決議）。

## kind（ps_xlsx --kind）

| kind | 產物 | 來源 | 重點 |
|------|------|------|------|
| probtable | prob-spec.xlsx | ProbSetting JSON（--config）| 參數表依 phase 分區、附-1 涵蓋率 |
| diff | prob-review.xlsx | config-diff.json | 規格⇄設定檔逐鍵、不一致總閘 |
| lint | prob-review.xlsx | lint-report.json | 守門規則×結果 |
| qtreport | prob-review.xlsx | rtp-report.json | golden 可調格 + 偏差/判定活公式 + 條件格式 |
| versions | prob-review.xlsx | 多份設定檔 JSON | 參數為列、版本為欄、差異標 ≠ |
| check | &lt;name&gt;.xlsx | references/checks/*.yaml | 輸入格留空 + 門檻可調 + IF 判定 + 總閘 |
| review / all | 上述彙總 | 多來源 | 審核簿總覽 |

## 檢核表 pattern（references/checks/*.yaml）

每張檢核表一份 YAML 規格：
```yaml
name: itemcard-linebet          # 輸出檔名
title: 道具卡 LineBet 偏差檢核
thresholds: {warn: 0.03, error: 0.1}   # 門檻 → 可調輸入格（公式引用其位址）
columns: [層級, 輸入, 參考, 偏差, 檢核]
rows:
  - [C, null, 100, "=IF(...)", "=IF(...)"]   # null=輸入格留空；活公式字串
```
- 輸入格人填 → 公式即時判定（未填 / 非整數 / 量級錯誤 / 未遞增 / 超門檻 / 警告 / OK）。
- 判定欄字首 `X`/`!`/`OK` → 條件格式紅/黃/綠（`add_verdict_cf`）。
- 總閘 `COUNTIF(...,"X*")` 統計。

## 驗證

公式真的算得出（三選一，由寬到嚴）：
- **邏輯單元驗證**（最低標，恆可做）：openpyxl 讀回驗公式字串格式、null 行為、門檻格位址、_meta 戳記。openpyxl 不算公式 → 只驗字串不驗值。
- **formulas 純 Python 重算**（免 soffice、免 sudo，`uv pip install formulas`）：`formulas.ExcelModel().loads(x).finish().calculate()` 真算每格，掃 0 個 `#REF!/#VALUE!/#DIV/0!/#NAME?`，並抽驗關鍵公式算出值（如偏差 `rtp/golden-1` 應等於預期）。test_ps_xlsx 的 `*_formulas_recalc_*` 走這條（importorskip，裝了才跑）。
- **LibreOffice 重算**（最接近使用者環境）：`soffice --headless --convert-to xlsx` → openpyxl `data_only=True` 讀，0 錯誤。

> 💡 formulas 已足以抓出 `#REF!`/`#DIV/0!`/門檻引錯格 等真錯誤；soffice 僅在要驗「機率同仁實際 Excel 環境的相容性」時才需要。
- **PS-XLSX**（ps_lint）：參數表 0 個字串型 `%`（應 dump 數值或活公式）；xlsx `_meta` sha 對來源（PS-STALE）。
