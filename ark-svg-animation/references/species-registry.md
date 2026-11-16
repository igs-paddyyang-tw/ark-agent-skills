# 物種登錄表（`scripts/species.mjs`）

```js
NAME: { archetype, size?, params?, palette?, variants?, accessory? }
```

| 欄位 | 說明 |
|---|---|
| `archetype` | 13 種體型之一（`RIGS` 的鍵）；拼錯 → `verify_svg --strict` 報「未登錄或體型名稱不存在」 |
| `size` | 相對大小建議（preview、沒有自己級距的使用方用）；遊戲通常用自己的賠率級距 |
| `params` | 覆寫該體型的參數（見 `archetypes.md`） |
| `palette` | `{ main, dark, light }`（`#rrggbb`）；只給有辨識特徵的物種，其餘由名字種子配色。`gold` 變體會蓋過它 |
| `variants` | 預設變體（`boss`、`gold`…） |
| `accessory` | 蟹的配件：`bomb`／`electrode`／`drill`／`wheel` |

## 名稱解析（`classify`）

1. 去前綴 `SINGLE_`／`LINE_`（魚潮成員沿用本體）
2. `TWIST_`／`TWISTER_` → 本體＋`twister` 變體
3. 查登錄表；查不到用規則：`*_CRAB` → crab（依前綴配配件）、`*SHARK`／`*WHALE` → shark；都不是 → `fusiform`＋`fallback: true`

## 新增物種

1. 在 `species.mjs` 加一行
2. `node verify_svg.mjs --strict`（確定性、安全、體積、接縫、登錄）
3. `node svg_anim.mjs preview --out p.html --names NEW_FISH` 看造型
4. 升 `VERSION`（造型改變）、記 CHANGELOG
