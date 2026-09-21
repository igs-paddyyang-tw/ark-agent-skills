# 座標基準（唯一規則：裝置 wm size）

| 東西 | 尺寸 | 能不能拿它的座標去 tap |
|---|---|---|
| `screenshot` 原圖 | = `wm size`（例 720x1280） | ✅ 這是唯一基準 |
| `thumb --width 540` 縮圖 | 540x960（.meta.json 有 scale=1.3333） | ❌ 要先 `to-device X Y --basis 540x960` 或 `tap X Y --basis 540x960` |
| `crop --zoom 3` 放大圖 | 任意 | ❌ 只給人 / OCR 看 |
| gamepack `buttons.xy` / `rois` / `screens.region` | 以 `game.yaml.resolution` 為準 | ✅ runner 開跑前比對 wm size，不符 BAD_INPUT |
| macro `tap: [x,y]` | 以 macro `resolution` 為準 | ✅ lint 比對 pack 解析度；超界 → MC-COORD |
| getevent 原始值 | 觸控面板 ABS 範圍（`getevent -p` 的 max） | ❌ `record` 已自動換算成 wm size |

橫直向：BlueStacks 直版 720x1280 與橫版 1280x720 是兩套座標；pack 的 `orientation` 只是備註，決定權在 `wm size`。同一款遊戲若兩種方向都要測，開兩個 pack（或 machines 分開）。
