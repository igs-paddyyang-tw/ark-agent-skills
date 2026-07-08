---
name: ark-quality-check
description: |
  品質檢查與測試：Linter → 測試 → 覆蓋率 → 安全掃描 → 報告。
  觸發：當使用者提到 測試、test、review、品質、QA、安全。
---

# 品質檢查 Skill

## 步驟
1. 執行 Linter（ruff / eslint）
2. 執行單元測試（pytest -v）
3. 檢查覆蓋率（目標 > 80%）
4. 安全掃描（依賴漏洞、密碼洩露）
5. 產出品質報告

## 輸出格式
```
🧪 品質報告
├── Lint: ✅ 0 errors
├── Tests: ✅ 12/12 passed
├── Coverage: 85%
├── Security: ✅ 無漏洞
└── 結論: 可合併
```
