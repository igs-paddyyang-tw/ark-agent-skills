# 角色預設組合

## 預設組合

### 最小團隊（2 人）
| 角色 | instance_name | role | emoji | 描述 |
|------|--------------|------|-------|------|
| Tech Lead | pm-agent | leader | 🔱 | 架構規劃、任務拆解、品質把關 |
| Developer | dev-agent | worker | 🧑‍💻 | 編寫程式碼、實現功能、重構 |

### 標準團隊（3 人）— 預設
| 角色 | instance_name | role | emoji | 描述 |
|------|--------------|------|-------|------|
| Tech Lead | pm-agent | leader | 🔱 | 架構規劃、任務拆解、品質把關 |
| Developer | dev-agent | worker | 🧑‍💻 | 編寫程式碼、實現功能、重構 |
| QA Engineer | qa-agent | worker | 🧪 | 測試策略、自動化測試、Code Review |

### 全端團隊（4 人）
| 角色 | instance_name | role | emoji | 描述 |
|------|--------------|------|-------|------|
| Tech Lead | pm-agent | leader | 🔱 | 架構規劃、任務拆解、品質把關 |
| Frontend | frontend-agent | worker | 👁️ | 前端開發、UI/UX、動畫 |
| Backend | backend-agent | worker | 🐛 | 後端開發、API、資料庫 |
| DevOps | devops-agent | worker | ⚙️ | CI/CD、部署、基礎設施 |

### 遊戲團隊（5 人）
| 角色 | instance_name | role | emoji | 描述 |
|------|--------------|------|-------|------|
| Tech Lead | pm-agent | leader | 🔱 | 架構規劃、任務拆解、品質把關 |
| Game Dev | gamedev-agent | worker | 🎮 | 遊戲系統、前後端整合 |
| Frontend | frontend-agent | worker | 👁️ | 前端渲染、動畫、UI |
| Backend | backend-agent | worker | 🐛 | 後端邏輯、WebSocket、API |
| QA | qa-agent | worker | 🔍 | 功能測試、自動化、Bug 回報 |

### 完整團隊（6 人）
| 角色 | instance_name | role | emoji | 描述 |
|------|--------------|------|-------|------|
| Tech Lead | pm-agent | leader | 🔱 | 架構規劃、任務拆解、品質把關 |
| Developer | dev-agent | worker | 🧑‍💻 | 編寫程式碼、實現功能 |
| QA | qa-agent | worker | 🧪 | 測試策略、自動化測試 |
| DevOps | devops-agent | worker | ⚙️ | CI/CD、部署、監控 |
| Designer | design-agent | worker | 🧠 | 企劃、規格、市場研究 |
| Analyst | analyst-agent | worker | 📈 | 數據分析、報告、模擬 |

## 自訂角色

使用者可指定不在預設表的角色，命名規則：
- 輸入：任意文字（如「資料工程師」「ML Engineer」）
- 轉換：kebab-case + `-agent` 後綴
- 範例：「資料工程師」→ `data-engineer-agent`
- emoji：使用者指定或自動分配（🔧）
- description：使用者提供或從角色名推斷
