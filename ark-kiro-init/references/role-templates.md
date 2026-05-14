# 已知角色模板索引

## 內建角色

| 角色 | role-id | 預設技術棧 | 領域規範 | prompts |
|------|---------|-----------|---------|---------|
| 全端 + SA/SD | architect | TS/Python/Go | api-contract.md | analyze-req, scaffold-api |
| 前端工程師 | frontend | TypeScript/React | ui_standards.md | component-spec, page-layout |
| 後端工程師（Python） | backend-py | Python/FastAPI | api-contract.md | endpoint-spec, db-migration |
| 後端工程師（Go） | backend-go | Go/Gin | api-contract.md | handler-spec, proto-design |
| DevOps | devops | Docker/Terraform/CI | infra_standards.md | deploy-checklist, pipeline-spec |
| 資料工程師 | data-eng | Python/Spark/SQL | data_standards.md | etl-spec, schema-design |
| ML 工程師 | ml-eng | Python/PyTorch | model_lifecycle.md | experiment-spec, model-card |
| 遊戲開發 | gamedev | TS(PixiJS)/Go | game_protocol.md | feature-spec, balance-check |
| QA 工程師 | qa | Python/Playwright | test_standards.md | test-plan, bug-report |
| 技術寫作 | tech-writer | Markdown/Mermaid | doc_standards.md | api-doc, tutorial |

## 自訂角色

不在上表的角色，觸發網路搜尋流程。

## 角色組合

可指定多角色合併，例如：
- 「全端 + DevOps」→ 合併兩者的 steering
- 「後端 + 資料工程」→ 合併技術棧

合併規則：
1. agents.json 取主要角色
2. steering 全部保留（不衝突）
3. prompts 合併
4. mcp.json 合併 servers
