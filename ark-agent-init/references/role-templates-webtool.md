# Web 工具開發團隊角色包（role-templates-webtool，v1.0）

> **定位**：通用 Web 工具／內部後台／webbot 應用開發團隊的能力包。
> 骨架產出走 `ark-webapp-generator`（獨立應用）或 `ark-agent-bot-builder`（套件消費端），
> 本包只管角色定位、交付物、prompts 配方。與 `role-skills-map.yaml` base_skills 疊加；
> SOUL 權威在 ark-agent-role-profile；ID = base_role。格式與 gamedev / aitool 包同構，
> 提詞遵循 prompt-schema-v1（frontmatter + 任務／輸出樣板／範例 三段）。

---

## 角色 × 提詞落地清單（與 role-prompts-map 同 commit）

```yaml
# 併入 role_prompts.work。🔴 新提詞檔（component-spec / db-migration / ui-spec）
# 必須與本 diff 同 commit 落在 assets/prompts/work/，validate 缺檔 exit≠0。
role_prompts_work_additions:
  architect:       [analyze-req, scaffold-api]        # 既有，不動
  frontend:        [component-spec]                    # 新
  backend:         [scaffold-api, db-migration]        # scaffold-api 沿用（frontmatter roles 加 backend）
  fullstack-coder: [analyze-req, component-spec]       # 既有 + 新
  ui-designer:     [ui-spec]                           # 新
  qa:              [test-plan]                         # 既有，不動
  data-analyst:    [data-query-routing]                # 既有，不動
# devops: [deploy-checklist] —— ⬚ 待補。deploy-checklist 提詞尚未落檔
#   （原設計與 aitool 包共用一份資產，但 aitool 包與該提詞目前皆不存在）。
#   為避免觸發 validate 幻覺索引守門（列了卻缺檔 → exit≠0），暫不列入 role-prompts-map；
#   待 deploy-checklist.md 落 assets/prompts/work/ 後再與 map 同 commit 補上。
```

## 角色一覽

| 角色 | role-id | profile | 交付物落點 | 提詞 |
|------|---------|---------|-----------|------|
| 規格架構（SA/SD） | architect | ⬚ 待補 | artifacts/specs/ | analyze-req, scaffold-api |
| 前端工程 | frontend | ⬚ 待補 | artifacts/ui/ | component-spec |
| 後端工程 | backend | ⬚ 待補 | artifacts/api/ | scaffold-api, db-migration |
| 全端工程 | fullstack-coder | ✅ | artifacts/features/ | analyze-req, component-spec |
| UI 設計 | ui-designer | ⬚ 待補 | artifacts/design/ | ui-spec |
| QA | qa | ✅ | artifacts/test-plans/ | test-plan |
| DevOps | devops | ✅ | artifacts/infra/ | deploy-checklist（⬚ 待補檔） |
| 數據分析 | data-analyst | ✅ | artifacts/analysis/ | data-query-routing |

## 各角色定義（待補 profile 的四個，生成基底）

### architect（規格架構）
- **定位**：需求 → 可實作規格的唯一出口：使用者故事、AC、API 契約、資料模型
- **核心能力**：需求澄清（ark-grill-me 配合）、API-first 設計、狀態機與邊界條件、規格可驗證性
- **profile 生成基底**：以 fullstack-coder 為底，stance 換「規格沒有 AC 就還不是規格」、
  hard_stop「不可在規格未定案時開工實作」；escalates_to: leader-agent

### frontend（前端工程）
- **定位**：把規格變成可用介面：元件、狀態管理、與 API 對接、可存取性
- **核心能力**：元件化拆解、狀態/事件邊界、載入與錯誤三態、效能預算（首屏/互動延遲）
- **profile 生成基底**：fullstack-coder 為底，scope.does 收斂到 UI 層；
  hard_stop「不可繞過 API 契約直呼內部服務」「mock 資料不可進 main」

### backend（後端工程）
- **定位**：API 與資料層權威：端點實作、schema 遷移、交易一致性、權限邊界
- **核心能力**：RESTful/錯誤碼紀律、遷移可回滾、輸入驗證 fail-closed、n+1 與索引意識
- **profile 生成基底**：fullstack-coder 為底；hard_stop「無回滾腳本的遷移不上」
  「任何寫入端點必過權限檢查，無例外清單」

### ui-designer（UI 設計）
- **定位**：design token、版型與互動規範的擁有者；工程可直接消費的設計交付
- **核心能力**：token 系統（色彩/字級/間距）、元件規範、響應式斷點、與 frontend 的交接格式
- **profile 生成基底**：game-designer 為底改域（把「玩家爽點」換成「使用者完成任務的阻力」）；
  hard_stop「規範不可只有圖——每個元件附狀態清單與 token 對照」

## 團隊編制對照（bot-builder 六角色 → 本包 base_role）

| bot-builder 編制 | base_role | 說明 |
|------------------|-----------|------|
| manager 總管 | bot-manager | |
| planner 企劃 | architect | web 工具的「企劃」就是規格擁有者 |
| developer 工程師 | fullstack-coder（或 frontend+backend 拆編） | 唯一業務邏輯寫手 |
| consultant 顧問 | data-analyst | 只讀不寫 |
| admin 管家 | admin | |
| leader 隊長 | leader | |

## 邊界聲明

- 骨架與 runtime 歸 ark-webapp-generator / ark-agent-bot-builder，本包不重複其架構決策
- 提詞的行為驗證歸 ark-prompt-spec-validator L2；本包確保 L1 可 lint
- AI 提詞共通規則沿用 gamedev 包文末六條（兩包共用，抽出時一起改指向）
