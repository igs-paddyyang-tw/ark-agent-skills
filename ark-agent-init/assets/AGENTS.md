# {project} — Ark Agent 共用規範

> **本檔是單一來源（SSOT）**：Kiro（`.kiro/steering/` 自動載入，或 symlink 指回本檔）、Claude Code（`CLAUDE.md` 以 `@AGENTS.md` 匯入）、
> Codex（原生讀取）讀的都是這一份。工具專屬差異只寫在文末「各工具入口」。
> 由 ark-agent-init 產生（已存在不覆寫）；子 agent 工作目錄根的 AGENTS.md 是本檔複本 —— 規範改這裡再重新分配。
> 所有回覆使用**繁體中文**。

## 這個 workspace 是什麼

- **{project}**：{agent_type} 型 Ark Agent。入口 agent：`{entry}`（{entry_desc}）。
- 編制（以 `{roster_file}` 為準）：{roster}
- IDE 型工具（Claude Code、Kiro IDE、Codex）在同一目錄工作時，**共用 memory／docs／knowledge／skills**；交接寫成 `docs/plans/<topic>-plan.md`。

## Ark Agent 五層架構

> 每個 Ark Agent 都由這五層構成；完整定義與 team／bot 目錄對照見
> `.kiro/skills/ark-agent-init/references/five-layer-architecture.md`。判讀順序與紅線在 `.kiro/steering/BRAIN.md`。

| 層 | 回答的問題 | 位置 | 誰寫／權限 |
|---|---|---|---|
| 🧠 大腦 | 我是誰、怎麼判斷、紅線在哪 | 本檔（規範）＋ `.kiro/steering/`：`SOUL.md`（人格）· `BRAIN.md`（判準＋角色知識）· `USER.md` · `CODE.md` · `MEMORY.md`（導覽） | 人寫；agent 唯讀 |
| 📝 記憶 | 之前發生過什麼 | `memory/daily/`（事件流水）→ `memory/memory.md`（蒸餾）→ `memory/archive/` | 自動＋IDE 收尾手寫 |
| 📚 知識庫 | 事實、規格、領域資料 | `knowledge/shared/`（共用）＋私有櫃（根 agent `knowledge/<instance>/`、子 agent `<wd>/knowledge/`）；raw → ingest → wiki | 只交 raw，wiki 由 ingest 產 |
| 🖐️ 技能 | 怎麼做一件標準的事（跨專案共用） | `.kiro/skills/`（上游 ark-agent-skills 複本） | 上游維護；修改只能提案回上游 |
| 🔌 腳本 | 本專案額外要接什麼（綁資料、主機、帳號） | `scripts/`、專案自己的模組、MCP | 本專案直接維護 |

- **技能 vs 腳本**：換一個專案還用得上 → 技能；綁本專案資料、主機、帳號 → 腳本。skill 目錄裡的 `scripts/` 屬技能層。
- **產出**放 `artifacts/`（team）／`output/`（bot），不進記憶也不進知識庫。
- **紅線**：對話紀錄與 agent 回覆不進 `knowledge/`；根層 `knowledge/` 不放 `raw/`、`wiki/`；技能只能提案回上游；不在記憶寫秘密。

## 開場與收尾

- **開場**：讀 `.kiro/steering/BRAIN.md`、`MEMORY.md`（Kiro／Claude 會自動載入），再讀 `memory/daily/` 最新 1～2 天
- **收尾**：完成一件事寫 `memory/daily/今天.md`（`## HH:MM [<來源>] <標題>` ＋ 3～6 行）；判準級結論才在 `MEMORY.md` 加一行

## 回覆使用者規則

- **結論先行、繁體中文、精簡**；不貼 raw stdout／stack trace，先分類再說重點
- 需要使用者決策時用編號選項：`1️⃣ {A}  2️⃣ {B}  3️⃣ {C}`，不用開放式問句；簡單確認直接執行回報
- 回報格式：`✅ 工作成果`／`📚 學習結果`／`⚠️ 阻礙`／`📋 下一步`

## 開發流程（SDD + Skill-Driven）

① 找 Skill → ② 找知識庫 → ③ 建規格書 → ④ 開發 → ⑤ 驗證 → ⑥ 歸檔
需求不清 → `ark-grill-me`；規格／設計 → `ark-superpowers`；依規格執行 → `ark-spec-executor`；
驗證 → `ark-code-spec-validator`（code）／`ark-prompt-spec-validator`（提詞）；查知識 → `ark-wiki-engine`；報告 → `ark-md-report`／`ark-html-report`

## 記憶怎麼用

| 落點 | 角色 | 規則 |
|---|---|---|
| `.kiro/steering/MEMORY.md` | 記憶導覽＋判準級里程碑＋常青段 | 每次注入，保持 < 20 KB；只加「下週還要常駐讀到的判準」一行 |
| `memory/memory.md` | 持久事實四分節 | 排程自動蒸餾，**不手寫** |
| `memory/daily/YYYY-MM-DD.md` | 事件流水的正式落點 | 完成一件事就寫 |
| `memory/archive/` | 舊事件 | 按需查 |

## 知識庫規則

- 素材放該櫃 `raw/`（只新增不修改）→ `ark-wiki-engine` ingest 產 wiki；**wiki 禁手寫**
- 修改 wiki 後同步該櫃 `index.md`＋`log.md`（append-only）；所有 wiki 頁有 frontmatter

## Git：共用工作樹

- 只用 pathspec commit（`git commit -m … -- <檔案>`），禁 `git add -A`；commit 與 push 分開下、各看 rc
- push 前確認 ahead 只有自己的 commit；主樹有別人的未提交變更 → 開獨立 worktree 做
- 看 rc 不接 pipe（`cmd | tail` 會吃掉非 0 的 rc）

## 新加的檢查要先反證

故意製造違規 → 必須紅；還原 → 必須綠。命中 0 或範圍是空的，要明說跳過，不能看起來像通過。

## 禁止事項與失敗模式

- 🚫 沒有規格書就寫 code（一次性 bug fix 除外）；🚫 貼 raw stdout／stack trace
- 同一類錯誤連續 2 次 → 停止，換根本不同的方法；不對同一錯誤做 3 次以上 incremental patch

## 各工具入口（同一份規範，各工具怎麼讀到）

| 工具 | 讀到本檔的方式 | 專屬注意事項 |
|---|---|---|
| **Kiro CLI／IDE** | `.kiro/steering/` 依 `inclusion` 自動載入；要讓 Kiro 讀本檔，在 steering 放指回本檔的 symlink（不放實體複本） | 寫檔用 `fs_write`（必填 `command`＋**絕對路徑** `path`）、查目錄用 `fs_read`；`TEAM.md` 是 `inclusion: manual`，用 `/context add .kiro/steering/TEAM.md` 載入 |
| **Claude Code** | `CLAUDE.md` 第一行 `@AGENTS.md` 匯入（另匯入 BRAIN／MEMORY） | Claude 專屬內容只寫在 CLAUDE.md；不在 CLAUDE.md 重寫本檔規則 |
| **Codex** | 原生讀 `AGENTS.md`（專案根往下每層一份） | **不支援匯入** —— 本檔要自成一體；合計上限 32 KiB；**不建 `CODEX.md`**（同層有 AGENTS.md 時讀不到）；BRAIN／MEMORY 不會自動載入，開場照上方自己讀 |
| **其他**（Gemini 等） | 設定改讀 `AGENTS.md`（Gemini：`context.fileName`） | — |

> 團隊模式（ark_team_agent daemon）：回覆使用者一律用 MCP `reply(text)`；跨 agent 通訊與派工工具見 `.kiro/steering/TEAM.md`。
