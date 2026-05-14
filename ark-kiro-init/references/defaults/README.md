# 預設角色模板：全端工程師 + SA/SD

## 參考來源

預設角色的模板直接參考 `D:\kiro-cli\.kiro\` 下的實際檔案：

| 檔案 | 路徑 |
|------|------|
| Agent 定義 | `.kiro/agents/architect.json` |
| 角色 Steering | `.kiro/steering/persona_architect.md` |
| 技術棧 | `.kiro/steering/tech_stack.md` |
| API 契約 | `.kiro/steering/api_contract.md` |
| 目錄結構 | `.kiro/steering/project_structure.md` |
| 需求分析 Prompt | `.kiro/prompts/analyze-req.md` |
| API 骨架 Prompt | `.kiro/prompts/scaffold-api.md` |
| UML 技能 | `.kiro/skills/generate-uml/instructions.md` |
| MCP 設定 | `.kiro/settings/mcp.json` |

## 產出時的替換規則

複製模板到目標目錄時，以下內容保持不變（通用）：
- tech_stack.md 的語言規範
- api_contract.md 的契約標準
- project_structure.md 的目錄約定

以下內容需依專案調整（產出後提示使用者）：
- agents.json 的 `mcp_servers`（依實際可用工具）
- settings/mcp.json 的環境變數（`${DATABASE_URL}` 等）
- persona 的 Memory/Experience（依團隊經驗）
