# 13 種體型（rig）

座標慣例：頭在 y=0、尾在 y=1、中線 x=0、身長＝1；動畫只用相位 t（0～1，t＝i/n），所有曲線以 2π 為週期（`verify_svg` 驗等速與週期）。
每支 rig 匯出：`defaults`、可選 `individual(rnd)`（個體差，只在 resolve 抽一次）、`body(p)`、`extent(p)`（含動畫外擴，所有格共用 viewBox）、`parts(t, p, c)`。

| 體型 | 主要參數 | 動畫曲線 |
|---|---|---|
| `fusiform` | `bodyW` `bodyLen` `tailW` `sway` `fin` `stripes` | 尾鰭 `sin(2πt)·sway`、胸鰭相位差 π/2 |
| `shark` | `bodyW` `sway` `fin` `tail` `snout` | 中線偏移 `sin(2πt)·sway·y²`（頭穩尾擺） |
| `crab` | `shellW` `shellH` `leg` `claw` `open` `accessory` | 步足三腳步態（相位差 π）、螯開合；轉輪一循環轉 60°（3 輻對稱） |
| `ray` | `wing` `flap` `tail` | 翼尖 y `0.42＋sin·flap`、x 微縮 |
| `flat` | `rx` `ry` `fringe` | 緣鰭半徑 `1＋k(1.2＋sin(3θ−2πt))`（行進波） |
| `puffer` | `r` `pulse` `spike` | 半徑 `r(1＋sin·pulse)`，刺跟著縮放 |
| `lobster` | `w` `sway` `ant` | 腹節 `sin(2πt−3y)·sway·y`、尾扇開合、觸角擺 |
| `cephalopod` | `head` `arm` `wave` | 8 觸手 `sin(2πt＋0.8i−0.9j)`（依序錯開＝行進波） |
| `jelly` | `bell` `len` `arc` | 傘體寬窄 `±12%`、觸手擺；`arc` 電弧亮度 `sin²` |
| `turtle` | `rx` `ry` `flip` | 前鰭角 `−0.5＋0.45 sin`、後鰭反相 |
| `snail` | `shell` `foot` | 腹足寬 `1＋0.08 sin`、觸角擺；殼固定 |
| `serpent` | `r` `amp` | 節鏈 `sin(2πt−5y)·amp·min(1,1.6y)`（Spine 部件魚的替代） |
| `token` | `r` `kind`（bison／monkey／wukong／cat） `bob` | 上下浮動 `sin·bob`、耳／角小擺 |

被捕（catch，所有體型共用）：3 格關鍵值〔閃白 0.6→0.25→0.1、旋轉 0→12°→−6°、縮放 1→1.05→0.8、透明度 1→1→0.4〕，格數不同時內插。
變體：`twister`（虛線旋風外圈）、`gold`（金色系）、`boss`（淡外圈）。
