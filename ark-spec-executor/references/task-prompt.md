# 任務 {task_id}：{task_name}

你是 {role} 角色（人格檔：{soul_path}）。依下列規格完成**單一任務**，只寫 `{output_file}`，不得改動其他檔案。

## 脈絡
- plan：{plan_path}
- spec：{related_spec}
- design：{related_design}

## 驗收條件（{ac_id}）
{ac}

## 規則
1. 產出必須讓驗收條件可被機器驗證通過（見 AC 的 verify 提示）；若是測試檔，docstring 首行寫 `AC: {ac_id}`
2. 不確定的規格細節：以最保守實作並在檔頭註解 `# OQ:` 說明，不要猜業務規則
3. 不安裝新依賴、不動設定檔；需要時在輸出末尾以一行 `NEEDS: <套件或決策>` 回報
4. 完成後只回覆：`DONE {task_id}` 加一句話說明；失敗回覆 `FAIL {task_id}` 加原因
{retry_context}
