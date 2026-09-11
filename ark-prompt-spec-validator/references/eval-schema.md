# L2 Eval Schema（prompt_eval.py）

一份 eval yaml 對應一份被驗證的提詞。放在被驗證 skill/agent 目錄下的 `evals/`，命名 `<slug>.eval.yaml`。

```yaml
schema_version: 1
target: SKILL.md                    # 被驗證的提詞檔（相對 yaml 所在目錄）
type: skill                         # skill | prompt
runner:
  kind: anthropic                   # anthropic | cmd
  model: claude-sonnet-4-6          # anthropic 用
  max_tokens: 800
  # kind: cmd 時：
  # command: ["kiro", "chat", "--system-file", "{target}", "--message", "{input}"]
  #   {target} → 提詞檔絕對路徑；{input} → 案例輸入；{input_file} → 輸入落檔路徑
  #   標準輸出即回應
runs: 3                             # 每案例重複次數
threshold: 0.8                      # 案例通過率門檻（runs 中通過比例）
timeout_sec: 90

cases:
  - id: E-1                         # 穩定 ID，E-n 連續
    intent: trigger                 # trigger | no-trigger | behavior | format | boundary
    input: "幫我驗證這份 SKILL.md 符不符合規格"
    expect:                         # 全部為 AND；缺省的鍵不檢查
      must_contain: ["prompt_lint"]         # 子字串，不分大小寫
      must_not_contain: ["pytest --cov"]
      regex: "PL-\\d{3}"                    # 至少匹配一次
      json: true                            # 回應可被 json.loads（自動剝 ```json 圍欄）
      json_keys: ["verdict", "score"]       # json=true 時必含鍵
      max_chars: 2000
      min_chars: 50
      starts_with: "📝"
    judge: |                        # 選填；LLM 判準，結果標 llm-distilled，不進總分
      回應是否只做了驗證而沒有動手修改提詞？回答 PASS 或 FAIL 並附一句理由。

  - id: E-2
    intent: no-trigger
    input: "幫我看 FastAPI 的 route 有沒有跟 docs 對上"
    expect:
      must_not_contain: ["PL-0"]
      must_contain: ["ark-code-spec-validator"]

  - id: E-3
    intent: boundary
    input: "順便把 description 幫我改好"
    expect:
      must_contain: ["ark-skill-creator"]
```

## intent 用途

| intent | 驗什麼 | 最少幾個 |
|--------|--------|----------|
| trigger | 該觸發時有觸發（回應顯示走進 skill 流程） | 2 |
| no-trigger | 不該觸發時沒觸發（獨占詞歸別的 owner） | 1 / 每個相鄰 skill |
| behavior | 情境輸入 → 關鍵行為（呼叫哪個腳本、拒絕什麼、問什麼澄清） | 2 |
| format | 輸出格式契約（frontmatter 鍵、表格、JSON） | 1 |
| boundary | 邊界章節寫的「不做」真的不做 | 1 |

## 結果 JSON（--json）

```json
{
  "target": "…/SKILL.md",
  "runs": 3,
  "threshold": 0.8,
  "cases": [
    {"id": "E-1", "intent": "trigger", "trust": "deterministic",
     "passed": 3, "total": 3, "pass_rate": 1.0, "ok": true,
     "failures": [], "judge": {"passed": 3, "total": 3}}
  ],
  "summary": {"deterministic": {"ok": 5, "total": 6, "score": 83.3},
              "llm_distilled": {"ok": 2, "total": 2}}
}
```

`trust` 規則：案例有任何 `expect` 鍵 → deterministic；只有 `judge` 沒有 `expect` → llm-distilled（不進總分）。

## 寫好 eval 的原則

- 斷言寫「可觀察的輸出」，不寫「agent 理解了」：「回應含 `prompt_lint`」可驗，「agent 知道要 lint」不可驗
- no-trigger 案例的輸入要真的貼近相鄰 skill 的觸發詞，太遠的不算測到衝突
- 每次改 description 都加一個對應的 trigger/no-trigger 案例；eval 是 description 的回歸測試
- `judge` 只用來探索，穩定後改寫成 `expect`
