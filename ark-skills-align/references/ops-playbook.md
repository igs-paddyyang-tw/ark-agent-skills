# Ops Playbook

## 常用指令

```bash
# 基線稽核（唯讀，任何時候可跑）
python scripts/audit_skills.py --repo <repo> --json audit.json

# schema v1 回填：先 dry-run 看 diff，再實跑
python scripts/backfill_metadata.py --repo <repo> --dry-run
python scripts/backfill_metadata.py --repo <repo>

# 全庫引用掃描（stub 化前必跑）
grep -rn "<skill-name>" <repo> --include="*.md" | grep -v "<skill-name>/"
```

## audit_config.yml 格式（擴充獨占觸發詞矩陣）

```yaml
exclusive_triggers:
  "覆蓋率": ark-test-runner
  "新詞": ark-owner-skill
```

腳本內建 Directive 第 3 節的完整矩陣；config 用於**新增**衝突對
（audit 抓到矩陣外的衝突 → 回報使用者定 owner → 寫入 config 並 commit 進 repo 的
`docs/alignment/audit_config.yml`，下次稽核自動生效）。

## 稽核規則 ↔ severity 對照

| rule | severity | 說明 |
|------|----------|------|
| frontmatter-parse / name-mismatch | P0 | 結構性錯誤，阻斷一切 |
| missing-category / invalid-category / missing-outputs | P1 | schema v1 未達標 |
| duplicate-description | P1 | 相似度 > 0.90，疑似重複 skill |
| trigger-conflict | P1 | 獨占詞出現在非 owner |
| invalid-output-entry / missing-schema-version / stub-format / readme-missing | P2 | 品質項，Phase 收尾清 |

## 判讀原則

- **腳本能自動修的只有 schema 回填**；duplicate 與 trigger-conflict 是結構決策，
  必須對應 Directive D-x 執行，audit 只負責抓不負責修
- backfill 後 audit 的 P1 應只剩 duplicate + trigger-conflict 類；若還有 schema 類
  P1。（註：`UNMAPPED` 已於 2026-08-12 決策 C 移除 —— frontmatter 為唯一真相，
  只有「category 缺失且推薦表也查不到」才回報 `NEEDS-CATEGORY`）→ 補 frontmatter 與
  backfill 腳本的 CATEGORY_MAP 後重跑
- 對 repo HEAD（2026-08-12）的實測基線：backfill 前 P1=123 / P2=67；
  backfill 後 P1=7 / P2=9。與此曲線偏差過大時先懷疑腳本或 repo 狀態
