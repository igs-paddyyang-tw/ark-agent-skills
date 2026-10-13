---
# server/handoff.md — ⑥ Game Server 工程交付單（樣板）
# ps_layout L-SERVER 會比對下列 sha 與現檔實算值；交付件來源變了就重出本檔。
kind: server-handoff
contract: "1"
game: {{GAME}}
slug: {{SLUG}}
prob_spec_version: "{{PROB_SPEC_VERSION}}"   # 對應 prob/prob-spec.md 的 version
config_path: "quicktest/config/a-standard.json"
config_sha256_16: "{{CONFIG_SHA16}}"          # = C.sha16(quicktest/config/a-standard.json)
rtp_report_sha256_16: "{{RTP_REPORT_SHA16}}"  # = C.sha16(quicktest/qt-report/rtp-report.json)
handoff_date: {{DATE}}
status: draft                                  # draft / delivered
---

# {{GAME}}｜Game Server 交付單

> 🔴 **邊界（SOUL hard_stop）**：團隊交付的是本 handoff 單，**不直接改 server code**。
> 工程端據此把定版設定檔與機率邏輯落到真實 server；本單只對帳「交付了什麼、以哪版為準」。

## 1. 交付基準（三份對齊的 sha）

| 項目 | 檔案 | sha256_16 | 說明 |
|---|---|---|---|
| 設定檔 | `quicktest/config/a-standard.json` | `{{CONFIG_SHA16}}` | 引擎輸入面，A 版定案 |
| 機率規格書 | `prob/prob-spec.md`（{{PROB_SPEC_VERSION}}）| — | 三方對話面 |
| 快測報告 | `quicktest/qt-report/rtp-report.json` | `{{RTP_REPORT_SHA16}}` | verdict confirmed |

## 2. K 卡 → Go 映射注意事項

> 把機率手法落到 server 時，容易踩的對應坑（每條標 prob-spec 章節 ↔ server 落點）。

| 手法 / 機制 | prob-spec 章節 | server 落點 | 注意 |
|---|---|---|---|
| （例）輪帶組切換 | §4 參數表 | ReelSet 載入 | 權重索引從 0 或 1 起算要對齊 |
| （例）FG 觸發 | §2 數據資料 | FreeGame trigger | 近失帶長度別用 B 版欄 |

## 3. 上線對帳欄位（server 回填）

| 指標 | 快測值（本單）| 上線實測 | 差異 | 判定 |
|---|---|---|---|---|
| Total RTP | {{RTP_TOTAL}} | | | |
| FG 觸發率 | | | | |
| 最大倍數 | | | | |

## 4. 已知差異 / 待工程確認

- （列出 config-diff 或 paramcheck 尚未收斂、需工程端在 server 情境確認的項目）

## 5. 版本與回溯

- 本單對應 commit / 版本：
- 上一版 handoff（若有）：`docs/_retired/` 或 git 歷史
