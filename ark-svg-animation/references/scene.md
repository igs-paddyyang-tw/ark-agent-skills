# scene —— 關鍵字／參考圖 → 原創遊戲背景（0.11.0）

> 用途：每款遊戲要有題材感的主背景（aidev 回饋：通用 `bg` 沒題材感）。所有形狀都是程序產生的原創剪影；
> 參考圖（含網路找的）**只取顏色**。

## 1. 關鍵字直接產

```js
asset('scene', { keywords: '沙漠 宮殿 夜晚 神燈' })            // 直式 720×1280
asset('scene', { keywords: 'tropical beach palm sunset', w: 1280, h: 720 })
asset('scene', { keywords: '賭城 夜', seed: 3 })               // seed 換星星／窗燈／燈籠的排列
// meta.recipe：{ mood, elements, landmarks, unknown }  —— unknown＝沒認得的詞，照著補同義詞或改用 elements
```

| 類型 | 關鍵字（中英皆可，節錄） |
|---|---|
| 氛圍（擇一，依序優先） | 深海／海底 → underwater、太空／星球 → space、火山 → volcano、雪／聖誕 → snow、東方／燈籠／新年 → oriental、叢林／森林 → jungle、糖果 → candy、黃昏／夕陽 → dusk、夜／月 → night、其他 → day |
| 地標（最多 2 個，第一個置中） | 宮殿／神燈、金字塔／埃及、神殿／遺跡、城堡、寶塔／和風、賭城／城市、房子／農場 |
| 地形與植物 | 沙漠（沙丘）、山脈、湖／海面、棕櫚／綠洲、樹／森林（雪景自動改松樹）、珊瑚、海草、火山 |
| 天空與粒子 | 月、太陽、星、雲、星球、光束、燈籠、泡泡、雪花、螢火蟲、寶藏（金光） |

- 每種氛圍有預設元素（例：night＝月＋星；underwater＝光束＋海草＋珊瑚＋泡泡）
- 要精準控制就直接給 `elements: [...]`（可用值見 `SCENE_ELEMENTS`），氛圍仍由 keywords 決定
- 上下暗角預設開（UI 疊上去看得清楚，色取 theme）；`vignette: false` 關掉
- texture 用漸層天空；flat（PixiJS Graphics）天空改 10 段色帶、光暈改同心層（有階梯感，屬預期）

## 2. 參考圖取色（含網路找的素材）

```bash
node scripts/palette.mjs --image ref.jpg [--k 8] [--json]
# → colors（依佔比）＋ roles（skyTop／skyBottom／glow／far／mid／near／ground／accent／particle／orb）
```
```js
asset('scene', { keywords: '沙漠 宮殿 夜晚', palette: roles })            // roles 物件
asset('scene', { keywords: '深海', palette: ['#06243f', '#0f5c8a', '#ff7aa8'] })  // 或色碼陣列（依亮度自動分派）
asset('scene', { keywords: '深海', palette: { accent: '#ff3b8a' } })    // 或只覆寫幾個角色
```

### 網路找素材的流程（界線）

1. 搜尋參考（例：Wikimedia Commons、各遊戲的公開宣傳圖都可以**看**），只用來決定：關鍵字（有什麼元素）＋顏色
2. 下載**縮圖**到一個新的暫存資料夾 → `palette.mjs` 取色 → **立刻刪圖**（不進 repo、不進 artifacts）
3. 用取得的 roles＋關鍵字產 scene；需要時在報告記錄參考來源網址（不寫進 SVG）
4. 🔴 不描形、不臨摹、不把參考圖貼進成品；公司素材同樣只能取色。顏色本身不受著作權保護，形狀一律由本 skill 程序產生

> 取色只影響氛圍；角色依亮度分派，不懂語意（例：沙子的顏色可能被分到天空下緣）。要精準就傳物件覆寫指定角色。
