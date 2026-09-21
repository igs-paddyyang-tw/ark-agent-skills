# 效能：從「每步 8–18 秒」到「每步 < 1 秒」

實測分層（BlueStacks Pie64 720x1280，Windows）：adb 本身 ~1.3s 基準；Python 冷啟 ~2.1s（疑防毒即時掃描）；5 次獨立 adb shell 3.39s vs 1 次串 5 指令 0.76s；截圖 1–3s；一步一截圖給 LLM 看 數秒–十數秒。

| 根因 | 對策 | 指令 / 設定 |
|---|---|---|
| R1 每步一個 Python 進程 | 單進程批次 | `ark_mobile_adb.py batch --file steps.txt`（多行子命令一個進程）；`shell-chain "cmd1" "cmd2"`（一次 adb shell 串多指令）；`aiqa_macro.py replay`（整支腳本一個進程） |
| R2 每步一次視覺分析 | 執行期零 LLM | macro：checkpoint 用模板比對 / 找色（毫秒級）；LLM 只在 aiqa_run 的 read / ask 與建表期 |
| R3 座標與截圖尺寸耦合 | 唯一基準 wm size | `thumb` 寫 .meta.json；`to-device`；`tap --basis`；pack / macro 解析度不符拒跑 |
| R4 Unity 無 UI 樹 | 座標表 + 模板錨點 | gamepack `buttons` / `screens`；`locate` 命中優先、xy 退路 |
| R5 連線不穩 + 固定 sleep | 自動重連 + 智慧等待 | `.ark-mobile.json` 加 `"connect": "127.0.0.1:5555"` → adb offline 時 CLI 自動 reconnect 一次再重試；`wait-stable` / `wait-pixel` / `wait_screen` 取代 sleep |
| R6 Python 冷啟異常慢 | 防毒排除 + 少開進程 | Defender 排除 Python 安裝目錄、platform-tools、專案目錄；用 batch / macro 讓一輪只付一次冷啟 |

截圖策略：`screenshot` 走 screencap → pull（二進位安全）；縮圖只在要給人 / AI 看時 `thumb --width 540`；macro 只在 checkpoint / shot / ocr 時截圖，其餘步驟不截。

量測方法：`replay` 的 summary.json 有 `elapsed_s` / `steps` / `shots`；同一流程「視覺驅動」與「macro 重放」各跑三次取中位數，寫進 pack 的 `machine.yaml` 備註做為加速比紀錄。
