# 與 ark-agent-init 的接力（整合待辦）

本 skill 產契約，ark-agent-init 組裝。要讓接力生效，init 端需要三個小改動：

| # | 改動 | 位置 | 說明 |
|---|------|------|------|
| 1 | `build_kiro.py --profile <yaml>` | `ark-agent-init/scripts/build_kiro.py::_write_soul` | 有 profile 時呼叫 `render_profile.py` 取 `SOUL.fragment.md` 取代 `_fallback_soul()`；`IDENTITY.md` 直接落 steering/ |
| 2 | SOUL 模板移出工具段 | `ark-agent-init/assets/steering/SOUL-*.md` | 刪「🧰 MCP Tools」「⚙️ Tool Settings」——已在 AGENTS.md/TEAM.md；同時修 `output/` → `artifacts/`（SOUL-worker.md、BRAIN.md） |
| 3 | 角色判斷表加一列 | `ark-agent-init/SKILL.md` §角色判斷 | 「指定未知角色 → 先轉 ark-agent-role-profile 訪談，再上網補技術棧」 |

README 分類表：新增一列 `ark-agent-role-profile`（category: process），
或跑 `ark-skills-align` 的 README 同步流程。

角色一覽永遠由 `profile_lint.py --list-roles` 導出，**不要**手寫進 role-templates.md。
