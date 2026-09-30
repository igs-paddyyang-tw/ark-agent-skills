# 與 ark-agent-init 的接力（整合待辦）

本 skill 產契約，ark-agent-init 組裝。要讓接力生效，init 端需要三個小改動：

| # | 改動 | 位置 | 說明 |
|---|------|------|------|
| 1 | `build_kiro.py --profile <yaml>` | `ark-agent-init/scripts/build_kiro.py::_write_soul` | 有 profile 時呼叫 `render_profile.py` 取 `SOUL.fragment.md`（含身分卡＋人格段）**併入 `SOUL.md`**（inclusion: always）取代 `_fallback_soul()`；`AGENTS.fragment` 併 root `AGENTS.md`、`schema.fragment` 併 `knowledge/<agent>/schema.md`；**三個 fragment 併入後刪除，不落 steering/**。不另產 IDENTITY.md（identity 已在 SOUL 身分卡）|
| 2 | SOUL 模板移出工具段 | `ark-agent-init/assets/steering/SOUL-*.md` | 刪「🧰 MCP Tools」「⚙️ Tool Settings」——已在 AGENTS.md/TEAM.md；同時修 `output/` → `artifacts/`（SOUL-worker.md、BRAIN.md） |
| 3 | 角色判斷表加一列 | `ark-agent-init/SKILL.md` §角色判斷 | 「指定未知角色 → 先轉 ark-agent-role-profile 訪談，再上網補技術棧」 |

> 🔴 **steering/ 只有 6 個大分類**：`SOUL` / `AGENTS`（= repo root SSOT，steering/ 不另產）/ `CODE` /
> `MEMORY` / `USER` / `TEAM`。render 出的 `*.fragment.md` 是 `inclusion: manual` 組裝素材，
> init 併入主檔後**必須刪除**，不得留在 steering/（否則重複注入）。小寫提詞（非標準檔）一律進 `.kiro/prompts/`。

README 分類表：新增一列 `ark-agent-role-profile`（category: process），
或跑 `ark-skills-align` 的 README 同步流程。

角色一覽永遠由 `profile_lint.py --list-roles` 導出，**不要**手寫進 role-templates.md。
