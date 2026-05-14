# Power-Engineer-Skills 框架對照表

將 power-engineer-skills 框架的四大模組映射到 ark-superpowers 的文件產出功能。

---

## 框架模組 → Skill 功能

| Superpowers 模組 | 核心能力 | 對應文件類型 | 對應章節 |
|------------------|----------|--------------|----------|
| System Design & Architecture | 擴展性、可用性、分散式系統、元件選擇 | Design + ADR | 系統架構、架構決策、技術棧選擇 |
| Software Engineering Best Practices | 測試策略、CI/CD、可觀測性、安全性 | Execution Plan | 驗證標準、可觀測性、安全性 |
| Product & Business Mindset | 使用者需求、北極星指標、業務價值 | Spec | 動機、使用者故事、成功指標 |
| Leadership & Communication | 團隊協作、決策推動、技術文件 | 全部 | 溝通計畫、Review Checklist |

---

## 詳細映射

### System Design & Architecture

| 框架知識點 | 文件中的體現 |
|------------|--------------|
| CAP / BASE 理論 | Design → 架構決策背景 |
| Load Balancer 選擇 | Design → 技術棧選擇 |
| Cache 策略 | ADR → 選項比較 |
| Database Sharding | Design → 數據流 |
| 故障隔離 | Design → 故障隔離與降級策略 |
| 服務發現 | Design → 系統架構圖 |

### Software Engineering Best Practices

| 框架知識點 | 文件中的體現 |
|------------|--------------|
| 測試金字塔 | Plan → 驗證標準（單元/整合/E2E） |
| CI/CD 流程 | Plan → 驗證方式 |
| 可觀測性三支柱 | Design → Observability 章節 |
| 安全性最佳實踐 | Design → Security 章節 |
| 漸進式交付 | Plan → 里程碑分階段 |
| 回滾策略 | Plan → 回滾計畫 |

### Product & Business Mindset

| 框架知識點 | 文件中的體現 |
|------------|--------------|
| 使用者需求分析 | Spec → 使用者故事 |
| 北極星指標 | Spec → 成功指標 |
| 非功能性需求 | Spec → NFR 表格 |
| 業務約束 | Spec → 約束條件 |
| MVP 定義 | Spec → 目標與非目標 |

### Leadership & Communication

| 框架知識點 | 文件中的體現 |
|------------|--------------|
| 決策推動 | ADR → 決策 + 理由 |
| 技術文件撰寫 | 所有模板的結構化格式 |
| 團隊溝通 | Plan → 溝通計畫 |
| 風險管理 | Plan → 風險管理表格 |
| Code Review | Review Checklist |

---

## 外部參考資源

| 資源 | GitHub | 用途 |
|------|--------|------|
| Architecture Decision Records | joelparkerhenderson/architecture-decision-record | ADR 格式（MADR） |
| System Design Primer | donnemartin/system-design-primer | 設計檢查清單 |
| Google Style Guide | google/styleguide | 文件撰寫規範 |
| Node Best Practices | goldbergyoni/nodebestpractices | 工程驗證指標 |
| Rust RFCs | rust-lang/rfcs | RFC 流程參考 |
| Awesome CTO | onurakpolat/awesome-cto | 技術領導力資源 |

---

## 使用建議

1. **新專案啟動**：Spec → Design → Plan 依序產出
2. **技術選型**：單獨產出 ADR
3. **快速溝通**：使用 One Pager 模式
4. **正式提案**：完整版 + RFC 分支流程
5. **事後記錄**：補寫 ADR 記錄已做的決策（status: accepted）
