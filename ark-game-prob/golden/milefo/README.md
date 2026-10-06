# golden/milefo — 彌勒佛 v3（1001A 版）golden case

來源：`彌勒佛機率表_v3_1001A版.xlsx`（機率人員公版；sha256_16 408fa27462d5b3a1，檔案本身不入庫）+ `output/games/milefo/quicktest/config/a-standard.json`。

| 檔 | 說明 |
|---|---|
| prob-data.json | ps_extract 產出（16 個參數區塊、9 個數據段、4 組輪帶）|
| prob-spec.md / .meta.json | ps_probspec xlsx 模式產出；verdict confirmed（10 億手 99.9395% vs golden 100.03%，−0.088 pp）|
| lint-report.json | ps_lint PASS（0 error）|
| config-diff.md | ps_diff 39 條規則：36 一致、3 不一致（ReviveThreshold 300 vs 200；復活保留權重索引起點）— 這三條是真實發現，不是測試資料 |

重產：`python scripts/ps_run.py --xlsx <xlsx> --out data/prob --slug milefo --game 彌勒佛 --config <a-standard.json> --diff-warn-only`
（本資料夾的 meta.sources 路徑已改成佔位，直接對它跑 ps_lint 會 PS-STALE；它是給人讀的範例，不是測試 fixture。）
