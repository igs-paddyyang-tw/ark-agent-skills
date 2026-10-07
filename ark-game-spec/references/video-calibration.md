# 偵測器校準指南

所有偵測器讀同一份 `frames/motion_timeline.json`（預設 4 fps、寬 160、灰階）：
`motion[i]` = 相鄰幀平均絕對差（0–1）、`brightness[i]` = 平均亮度、`hist_dist[i]` = 16-bin 直方圖 L1/2 距離、`roi[name].diff[i]` = ROI 像素差。

## 先看數字再調參
```bash
python - <<'PY'
import json; tl=json.load(open('artifacts/cva/<run>/frames/motion_timeline.json'))
for t,m,b,h in zip(tl['t'],tl['motion'],tl['brightness'],tl['hist_dist']):
    if m>0.03 or h>0.3: print(t,m,b,h)
PY
```

| 偵測器 | 預設 | 自適應（adaptive: true 預設） | 症狀 → 調法 |
|------|------|------|------|
| motion_settle | high 0.12 / low 0.02 | high = max(0.5·p90, min_high 0.02)；low = clamp(0.2·high, 1.5·p50, 0.6·high) | 停輪只抓到一半 → 降 `min_high`、縮 `min_spin_s`；轉場誤判成停輪 → 提高 `min_settle_s` |
| motion_burst | threshold 0.30 | thr = max(p97, min_threshold 0.05) | fish 特殊武器抓不到 → 降 `min_threshold` |
| still_hold | threshold 0.01 / min_s 2.0 | thr = clamp(0.3·p50 + 1e-4, ≥0.002) | fast 下注期抓不到 → 降 `min_s`（fixture 結果停留 2 s 需 1.5） |
| scene_change | threshold 0.5 | — | slot 每次停輪都被當轉場 → 提高到 0.6–0.7 |
| flash | threshold 0.35（相對亮度跳升） | — | big win 白閃抓不到 → 降；每次停輪都閃 → 升 |
| roi_change | pixel_delta 0.04 | — | HUD 數字區位置不對 → `--roi score=x,y,w,h` 覆寫 auto |
| periodic | every_s 5 | — | 純兜底，別靠它 |
| audio_peak | threshold 2.0（中位數倍數） | — | 需有 audio stream |

`adaptive: false` 可關掉自適應改用絕對值（pack extraction.yaml 內設）。

## 抽樣率
4 fps 抓得到 ≥ 0.25 s 的事件；單幀白閃（0.1 s）會漏。真實遊戲的閃光 / 停輪都 ≥ 0.3 s。需要更細時在 pack `extraction.timeline.fps` 設 8（timeline 成本線性增加）。

## 實況主疊層
`--crop x,y,w,h`（0–1 比例）在 timeline 階段裁掉；`crop.webcam_overlay: auto` 目前只是宣告，未自動偵測（manifest 會記 crop=null）。

## 判斷校準是否成功
用 `scripts/tests/make_fixture.py` 產已知事件影片跑一次，召回 ≥ 90%（±0.5 s）才算；真實影片以 pack `eval/answer-key.template.yaml` 標事件時間點做同樣驗證。
