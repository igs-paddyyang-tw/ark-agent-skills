# 角色 Skills 對照表（v2.1 — 契約化）

> **機器解析錨點**：下方 `base_skills:` / `role_skills:` YAML block 是**唯一清單來源**。
> 各專案的 `scripts/sync_skills.py` 的 `MATRIX` 應以此為基礎（base_skills 全員裝，
> role_skills 依角色加），不要另立一份平行清單 —— 兩套並存必漂移。
> 領域專屬的 worker skill 由各專案在自己的 MATRIX 補（本表的 role_skills 只給通用起點）。

## 安裝清單（機器解析錨點：`base_skills:` / `role_skills:`）

```yaml
# 全員必裝：Loop 五件套（需求→文件→執行→驗證→知識）+ 基本產出/驗證能力
base_skills:
  - ark-grill-me              # 需求澄清（反詰）
  - ark-superpowers           # 規格/設計/計畫
  - ark-spec-executor         # 依規格執行
  - ark-code-spec-validator   # 驗 code ↔ spec
  - ark-wiki-engine           # 知識查詢（wiki_query）
  - ark-prompt-spec-validator # 驗 prompt/AI內文 ↔ spec
  - ark-md-report             # Markdown 報告產出
  - ark-html-report           # HTML 報告產出

role_skills:
  admin:    [ark-planning-with-files, ark-env-doctor, ark-dashboard-health, ark-cost-tracker]
  leader:   [ark-project-planning, ark-uml-generator, ark-doc-coauthoring]
  ai-dev:   [ark-skill-creator, ark-mcp-builder, ark-llm-tools]
  coder:    [ark-skill-creator, ark-code-review]
  qa:       [ark-code-review, ark-test-runner]
  devops:   [ark-docker-deploy, ark-env-doctor]
  designer: [ark-frontend-design, ark-canvas-design, ark-ui-design-system]
  analyst:  [ark-kpi-calculator, ark-chart-generator, ark-etl-pipeline]
```

- 未列出的角色（含自訂角色）：只裝 `base_skills`，其餘由使用者/專案 MATRIX 指定
- Skill 名稱必須存在於上游庫；安裝前以 `{name}/SKILL.md` 存在性驗證，缺失即報錯（不靜默略過）

## 角色邊界原則

> 🔴 **只裝該角色該裝的** —— skill 會進 agent 的 context window，
> 全員裝同一批只是稀釋注意力。`base_skills` 是「每個 agent 都需要的通用底座」，
> `role_skills` 才是角色差異。領域專屬（如市場情報的 `ark-web-scraper`）由專案 MATRIX 補。

## 安裝機制（sync_skills.py）

由專案的 `scripts/sync_skills.py` 從上游複製（不是 build_kiro 直接裝）：

```bash
python3 scripts/sync_skills.py            # 依 base_skills + MATRIX 從上游複製
python3 scripts/sync_skills.py --check    # 驗一致（doctor/CI 用）
```

- 上游庫：`~/kiro-cli/.kiro/skills`（`git clone igs-paddyyang-tw/ark-agent-skills`）
- skill 是**複本非 symlink**（symlink 跨機斷鏈）→ 靠 sync 重建 → gitignore 排除
- 前提：team.yaml `kiro_files.skills.policy: skip`（否則套件 `_deploy_skills` 推翻矩陣）
- 完整範例：`ark-agent-team-builder/examples/market-team/scripts/sync_skills.py`
