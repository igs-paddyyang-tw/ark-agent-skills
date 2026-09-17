# ark-skills-align — 維運手冊（ops-playbook）

> SKILL.md 只留「怎麼用」的精要;這裡收「為什麼這樣設計」的敘事與踩坑（2026-09-14~17 累積）。
> 通用判準（共用工作樹 D、看結果 E、反證新檢查 A）在根 `AGENTS.md`，本檔不重複。

## 為什麼變更廣播不進排程（pre-push 而非 cron）

殘留只在一個時刻產生:**上游移除/改名/升版 skill 的那一刻**。排程掃出來的東西沒有收件人，
而「沒人讀的紅燈」正是那 241 處累積起來的原因。所以走 `pre-push`:只在推送含移除/major bump 時
檢查，分兩級——消費端 **sync 矩陣**還列著就擋（改另一 repo 一行即可）;只有**已部署複本**就警告不擋。

🔴 **上游做移除/升版，就由上游負責掃消費端。** 消費端各自的 `--check` 在別的 repo/別台機器，
「消費端自己會檢查」在多 repo 情境等於沒有檢查。

## 移除/改名的三段判準（只做第①段會靜默掉能力）

| 段 | 問什麼 | 依據 |
|:--:|---|---|
| ① | 該不該刪 | 上游 git 歷史有過＝殘留;沒有過＝**專案自建，不可動** |
| ② | 接手者是誰 | `metadata.replaces` → 移除 commit 箭頭/併入宣告 → 推不出來就**明說不確定** |
| ③ | **這個 agent 該不該有接手者** | 接手者是 scaffolder 而這 agent 是職人/管家 → 是刪不是換 |

🔴 第②段**不猜**:批次移除 commit 同行並列多個名字，靠「同行出現」推斷會得到錯的接手者。
猜錯的接手者比「不知道」更糟。自己做的整併回頭補 `replaces:`（唯一權威）。

四個掃描面:角色矩陣（sync MATRIX）· 已部署複本（`**/.kiro/skills/`）· 人格清單（SOUL 條列）·
蒸餾來源（distill-sources）。專案自建（LOCAL_ONLY）不算懸空。消費端根不存在時明說跳過，不假裝通過。

## 邊界宣告:逐案補，不設規則（2026-09-14 定）

`description` 的「不適用於…請用 ark-X」是路由用的（agent 選 skill 只讀 description）。
**刻意不做成守門規則**——多數 skill 沒有可混淆的鄰居，強制只會產生填充文字稀釋真正的邊界。
判準:**指名「會被誤觸的那一個」，指不出來就不要寫。**
⚠️ 在「不適用於」句裡寫別人的獨占詞（派工/寫 spec/覆蓋率）一樣會被 audit 判 P1——
agent 路由讀整段不分正反，換個說法即可。

## 多 session 同時作業協定（2026-09-14 實測）

| 撞到什麼 | 做法 |
|---|---|
| add 後被清 index，commit 變空 | 只用 pathspec commit（stage+commit 原子），禁 `git add -A` |
| commit && push 串接:commit 失敗 push 照跑推別人的 | commit 與 push 分開看 rc;push 前確認 ahead 只有自己那幾個 |
| reset 排除別人的檔案，清掉對方在飛的工作 | 只退自己的:`git reset -- <自己的檔案>` |
| 主樹有別人未提交又落後遠端 | 獨立 worktree cherry-pick 後推，主樹不動 |

🔴 別靠「機器上只有一個 peer」推論 commit 是誰做的——author 是同一人類帳號無資訊量;
看它留下的工作面（報告/commit 觸及目錄）。

## 版本對齊（v2）的判準

- **release train 是對齊單位**:團隊對齊一個列車號比對齊 20 個 skill 範圍可操作;個別 skill 只能例外 pin（附 reason）
- **lock 本機不進 git**:同一 repo 多機各跑一版，lock 描述「這台機器現在裝了什麼」;matrix（git）是「期望」
- **apply 永不無人值守**:manager 總機 `<專案>-agent`（dir="."）可 plan/verify;apply 需人私訊該 manager 確認（C-5）
- **base tier 同版強制**:Loop 五件套契約耦合，跨 agent major 不一致 = P0（AL-301）;上游給預設，部署可覆寫
- **heartbeat 去重**:同版無變化只寫 /api/health，不發 TG——避免頻道噪音讓人對版本訊號脫敏
