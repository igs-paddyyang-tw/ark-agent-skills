# 角色 Skills 對照表（v2.2 — 抽出為 YAML 單一來源）

> 🔴 **機器解析單一來源已抽為 `assets/role-skills-map.yaml`**（skills-align v2 ADR-003）。
> 本 md 只留說明;`base_skills` / `role_skills` / `tiers` 清單一律讀那份 yaml，不在此重複維護
> （兩套並存必漂移）。各專案 `scripts/sync_skills.py` 的 `MATRIX` 以 yaml 為基礎。

## 安裝清單（權威在 `assets/role-skills-map.yaml`）

- **base_skills**（tier `base`）:全員必裝，Loop 五件套 + 產出/驗證能力（8 個）。契約耦合，全隊同版。
- **role_skills**（tier `role`）:角色差異（admin/leader/ai-dev/coder/qa/devops/designer/analyst）。走範圍。
- **domain**（`local_only`）:各專案 MATRIX 自補的領域 skill，不比對上游。

完整清單與 tier 對照見 `assets/role-skills-map.yaml`。
- 未列出的角色（含自訂）:只裝 base_skills，其餘由專案 MATRIX 指定
- Skill 名必須存在於上游庫;安裝前以 `{name}/SKILL.md` 存在性驗證，缺失即報錯（不靜默略過）

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
- sync_skills.py 的角色→skill 矩陣即本檔的 `role_skills:` 錨點（唯一真相）；各 team repo 自建 sync 腳本依此矩陣
