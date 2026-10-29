# {project} — Claude Code 入口

@AGENTS.md
@.kiro/steering/BRAIN.md
@.kiro/steering/MEMORY.md

---

> 🔴 **規範的單一來源是上面匯入的 `AGENTS.md`**（Ark Agent 五層架構、記憶、知識庫、Git……）。
> 本檔只放 **Claude Code 專屬**的內容；要改共用規則請改 AGENTS.md，不要在這裡重寫一份 —— 兩處各寫一份必然漂移。
> 由 ark-agent-init 產生（已存在不覆寫）。

## Claude Code 專屬

- 身份：在本 workspace 協助 `{entry}`；**不載入 `SOUL.md`**（那是 agent 的人格），以 IDE 協作者身分工作
- daily 收尾手寫：`## HH:MM [claude-code] <標題>` ＋ 3～6 行（含 commit）
- 跨 session 記憶（`~/.claude/projects/.../memory/`）只放「關於使用者與怎麼工作」，不重複 repo 已記的事實
- skills：`.claude/skills` 可 symlink 到 `.kiro/skills`（同一份）
- 指令模板：`.kiro/prompts/*.md` 對應 `.claude/commands/*.md`（需 YAML frontmatter、佔位符用 `$ARGUMENTS`）

<!-- 在這裡往下加本專案的 Claude 專屬補充 -->
