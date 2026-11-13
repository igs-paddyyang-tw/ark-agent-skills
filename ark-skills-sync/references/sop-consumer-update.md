# SOP A —— 專案更新 skills（往下對齊）

> 規範見 SKILL.md「規範」。本頁是步驟。

## 1. 看現況（唯讀）

```bash
S=.kiro/skills/ark-skills-sync/scripts      # 沒裝本 skill：用上游 clone 的 ark-skills-sync/scripts
python3 $S/skills_sync.py status
```

上游自動解析（`upstream.py`）：`--upstream` → `$ARK_SKILLS_UPSTREAM`（別名 `$ARK_AGENT_SKILLS_DIR`）→ manifest `upstream.path`
→ `~/kiro-cli/github/shared/ark-agent-skills` → GitHub 公開 repo clone 到 `~/.cache/ark-agent-skills`（**完整歷史**，STALE／LOCAL 判定要用）。

| 欄位 | 意思 | 處置 |
|---|---|---|
| 缺少 | manifest 要、沒裝 | `update --apply` 會補 |
| 空殼／壞掉 | 同名目錄缺 `SKILL.md`（例：只剩 `__pycache__`） | `update --apply` 會補（舊版 mirror_sync 會略過 → 假綠燈） |
| 舊名 | 上游已併入他處的 stub | 見 `sop-install-remove.md` |
| STALE | 本地內容曾存在於上游歷史 = 過期 | `update --apply` 對齊 |
| LOCAL | 上游從未有過的內容 = 本地改過 | **不自動處理**：先 diff（下方第 3 步） |

## 2. 更新

```bash
python3 $S/skills_sync.py plan              # 預覽
python3 $S/skills_sync.py update --apply    # 拉上游 → 補缺／空殼 → mirror_sync 對齊 STALE（逐個 target、不越界 projects/*）
```

- targets 預設 `.` 與 `agents/*`（manifest `targets` 可改）；`projects/*` 永遠不掃（那是別的 repo）
- 結果以**重掃**為準，最後一次 status 要全 ✅ 或只剩已知 LOCAL

## 3. LOCAL 怎麼判

| 改動性質 | 處置 |
|---|---|
| 本專案特有設定（topic 名、字數限制、agent 名、主機） | 留本地，在 commit 訊息註明 |
| 通用修正 | 走 `sop-contribute-upstream.md` 回貢；上游收下後再 update，LOCAL 會變 SAME |
| 只是上游歷史以前的舊版（無版號、舊措辭） | `mirror_sync.py apply … --accept-upstream <skill> --yes` |

## 4. 驗證與提交

- 反證：故意改一個複本檔 → `status` 必須報 LOCAL；還原 → 消失
- 有常駐 daemon：閒置時重啟，`/api/health` 無 degraded
- 提交：`git add --all -- ':(glob)agents/*/.kiro/skills/**' .kiro/skills .kiro/skills-manifest.yaml`，
  `git diff --cached --name-only` 只有 skills 路徑才 commit；commit 與 push 分開下
