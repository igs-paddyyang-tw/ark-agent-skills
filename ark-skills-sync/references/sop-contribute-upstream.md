# SOP B —— 回貢上游（往上）

| 步驟 | 做什麼 | 判準／指令 |
|---|---|---|
| 0 判斷 | 本地改動該不該回上游 | 只涉及本專案特有設定 → 留本地 LOCAL；其餘回上游 |
| 1 開工 | 上游 clone 開 worktree（主樹可能有別人 WIP） | `git -C ~/kiro-cli/github/shared/ark-agent-skills worktree add <暫存>/wt-<skill> origin/main` |
| 2 修改 | 改 skill、`metadata.version` 依 semver 升、`CHANGELOG.md` 加一段 | 版號沒升，消費端會判成同版不同內容 |
| 3 守門 | `audit_skills.py --repo <wt>` P0／P1＝0；有 `scripts/tests` 就 pytest | 新加的檢查要反證會紅 |
| 4 提交 | `feat(<skill>): <摘要>（x.y.z）`；pathspec commit | commit 與 push 分開看 rc |
| 5 推送 | 上游是 `igs-paddyyang-tw` 個人 repo：clone 設 `credential.helper ""` 再 `store --file=~/.git-credentials-igs` | gh 預設公司帳號會 403 |
| 6 列車 | 見 `sop-release-train.md` | — |
| 7 回收 | 原專案 `skills_sync.py update --apply`；原本的 LOCAL 應變 SAME | 仍是 LOCAL → 內容沒完全進上游 |

新 clone 記得裝 pre-push hook：`ln -s ../../scripts/hooks/pre-push .git/hooks/pre-push`。
