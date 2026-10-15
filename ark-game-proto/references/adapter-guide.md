# 寫一支 adapter（新遊戲）

adapter = 「這款玩法的參數表語意」。通用段（盤面、Pay table、Strip、§2 快測摘要）`proto_common` 已處理；adapter 只回答：
哪張表是輪帶組、FG / Bonus 怎麼觸發、FG 用哪個模型、模型參數在哪幾張表、規格書哪裡沒寫清楚。

## 步驟

1. **確認 md 格式**：`prob-spec.md` 由 ark-game-prob 1.4+ 產（附錄有 ```strip、§2 有「快測摘要」）。舊檔先 `ps_run` 重產。
2. **選模型**：既有 `collect-mult` / `coin-lock` 裝得下就用；裝不下見下方「加模型」。
3. **新增 `scripts/adapters/<slug>.py`**（檔名即 `--adapter` 名，也是 `cfg.art` 美術套名）：

```python
MODEL = "collect-mult"                       # 或 coin-lock / 新模型

def build(doc: dict, g: dict) -> dict:
    """§4 表格 → config 片段；回傳的鍵會覆蓋通用段（board / paytable 可自帶）。"""
    P = walk_tables(doc, "params")           # [{h3, tid, cap, t}]；tid = 「表 M-1」的 M-1
    ...
    return {"strips": ..., "reelsets": [...], "mg": {...}, "fg": {"model": MODEL, "trigger": {...}, "groups": [...], ...}, "gaps": GAPS}

def targets_extra(doc) -> dict: ...          # 選配：§2 該模型專屬的驗證目標
def go_rules(cfg, go) -> list[dict]: ...     # 選配：規格書 ⇄ Go 設定檔逐鍵對照 [{key, ok, spec, go}]；spec=None → 規格書缺
def go_fill(cfg, go) -> list[str]: ...       # 選配：規格書缺、Go 有的值補進 config（必標 *_src、必有對應 gap）
```

4. **寫 GAPS**：每一條「規格書沒寫、引擎必須推定」的規則一條：

| 欄 | 寫什麼 |
|---|---|
| `id` | `G-<n>` 或 `G-<GAME>-<n>` |
| `what` / `spec` | 缺什麼、規格書目前寫了什麼 |
| `assume` | 雛型採用的推定（要能一句話說清楚）|
| `check` | 用哪個數字回驗 |
| `auto` | 驗證台自動回驗種類：`fg_rate` / `fg_base` / `fg_groups` / `mg_rtp` / `trig_split` / `bonus_split` |
| `go` | Go 原始碼證據 `檔案:行 程式片段`（有讀過 Go 才填）|

5. **加美術套**：`src/art.js` 的 `SETS['<slug>']`，鍵 = 規格符號代碼；只做通用造型，不仿原廠美術與商標。
6. **golden + 測試**：`golden/<slug>/` 放 md、Go 設定檔、parity JSON、`game-config.json`；`tests/test_proto_build.py` 的 `CASES` 加一列。
7. **驗收**：`pytest -q scripts/tests`；`node scripts/tests/core_test.js golden/<slug>/game-config.json`；有 Go 引擎就跑 `go_parity.py`（0 差異）。

## 加一個玩法模型（slot-core.js）

```js
MODELS['<model>'] = {
  compile(cfg, C) {},                 // 把 cfg.fg 轉成執行期表（wtable）
  play(C, rng, res, rec) {},          // 數學：只用 rng；rec=true 時另記演出用時間軸（不得多吃 rng）
  present(C, fx, res) {},             // 演出抽選：只用 fx
  statsAdd(g, f) {}, groupReport(x, b) {},
};
EXACT_FG['<model>'] = (C, joint, base, opts) => ({ fg_avg, rtp_free, groups });   // L1；無解析解就固定 seed 直接抽樣
```

- `trigger()` 若規則不同，在 `trigger()` / `trigProb()` 加一個 `model` 分支（精算與抽樣兩邊都要）。
- **抽值順序照 Go 引擎**（逐行讀 Go 的呼叫順序）；否則逐局對照必然不一致。
- app.js：L1 / L2 / 單局軌跡 / 情境 / 演出場景依 `C.model` 分支（參考 `CL` 判斷）。
- `goparity/<model>_trace.go`：照既有兩支改 import 與 GameWorker 介面，輸出 `i set mg fg total group sp`（未提供的欄位填 -1 / 0）。
