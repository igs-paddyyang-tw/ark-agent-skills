# SOP —— 啟動檢查（skills doctor）契約

ark-agent-os 套件在服務啟動（與排程）時呼叫**套件內建版**的本腳本 —— 檢查工具不能被它要檢查的複本拖垮。

```bash
python3 <套件>/templates/skills/ark-skills-sync/scripts/skills_sync.py doctor \
    --root <部署根> --bundle <套件>/templates/skills \
    --require '*=<內建清單>' --require '.=ark-skills-sync' --require 'agents/admin-agent=ark-skills-sync' \
    [--repair] [--upstream auto] --json
```

## 狀態（C-4）

| 狀態 | 定義 | `--repair` |
|---|---|---|
| MISSING | `--require` 或 manifest 要、目錄不存在 | 內建有 → 從內建補 |
| BROKEN | 目錄在但缺 `SKILL.md`／frontmatter 沒有 name | 內建有 → 從內建補（覆蓋同名檔、不刪多餘檔） |
| RESIDUE | 本地複本自己標 deprecated（離線可判） | 不動，回報 |
| STALE／LOCAL | 僅 `--upstream auto|<來源>` 且連得到時比對 | 不動，回報 |

- **repair 只碰 MISSING／BROKEN**，其餘一律不動（反證測試：客製檔案 repair 後不變）
- 上游連不到 → `upstream: "unreachable：…"`，**不算失敗**；預設 `--upstream off`（啟動不碰網路）
- 掃到 0 個 skills 目錄 → `ok: false` 並寫 `note`，不能看起來像通過

## 輸出（JSON）

```json
{"root": "...", "upstream": "off|<head>|unreachable：…", "ok": true, "note": "",
 "summary": {"missing": 0, "broken": 0, "residue": 0, "stale": 0, "local": 0, "repaired": 0},
 "targets": [{"target": ".", "installed": 49, "missing": [], "broken": [], "residue": [], "repaired": [], "stale": [], "local": []}]}
```

套件寫到 `state/skills-doctor.json`，`/api/health.skills` 直接引用；`missing + broken > 0` 時 health degraded 加 `skills`。
exit：0 ok／1 有缺或壞／2 參數錯。
