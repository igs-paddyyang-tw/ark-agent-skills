# 記憶架構（四層分工）— 新建規範 + 既有部署遷移

> **定版門檻：ark_team_agent ≥ 1.11.0**（Paddy 2026-10-08 拍板：以 1.11.0 為記憶規範壓版；含 `memory-distill` 支援）。
> 來源：paddy-bot `docs/one-pagers/2026-10-08-memory-migration-playbook.md`，本檔整理成 ark-agent-init 的權威參考。
> 新建 workspace 照 §2 直接產新架構；既有部署照 §4 遷移。

## 1. 為什麼（一句話）

`.kiro/steering/MEMORY.md` 是 **always-on 注入**。被當事件流水堆大（實測 paddy 73 KB）會吃掉一大截 context，
而真正該常駐的判準反而被淹沒。**把 MEMORY.md 改回「導覽」，事件搬到不注入的地方，持久事實交給排程蒸餾。**

根因在範本：舊範本寫「**每完成一個段落更新 MEMORY.md**」—— 等於要求 agent 把流水寫進常駐檔。本 skill 2.2.0 起全面移除這句。

## 2. 四層分工（新建 workspace 的標準）

| 層 | 落點 | 誰寫 | 進 context | 內容 |
|---|---|---|---|---|
| 判準 | `.kiro/steering/BRAIN.md` | ✋ 人 | ✅ 常駐 | 怎麼判斷、紅線、讀寫順序 |
| 導覽 + 里程碑 | `.kiro/steering/MEMORY.md` | ✋ 人 | ✅ 常駐 | 「記憶住在哪」表 + 一行里程碑索引 + 常青段（專案快照／定版結構／技術決策） |
| 持久事實 | `memory/memory.md` | 🤖 `memory-distill` | 🔸 可選 | 四分節：環境慣例／工具怪癖／人與偏好／進行中長期事項，≤ 2000 tokens |
| 事件流水 | `memory/daily/YYYY-MM-DD.md` | 🤖 bot 自動／✋ team 手寫 | ❌ | 每次任務的做了什麼／決定／踩坑，≤ 150 字 |
| 舊事件 | `memory/archive/YYYY-MM.md` | 🤖 `_builtin:memory-consolidate` | ❌ 按需 | > 14 天的 daily 與 MEMORY.md 日期分節（非破壞搬移） |

**單一權威**：記憶規則只寫在根 `AGENTS.md`「記憶怎麼用」一節；`BRAIN.md`、`MEMORY.md`、各 `SOUL.md` 只引用，不另立規則。

### bot 與 team 部署的差異

| | bot（ark_bot_agent） | team（ark_team_agent） |
|---|---|---|
| `memory/daily/` | 套件 `write_daily_log` **自動寫**（含機密遮蔽） | **無自動寫入端** → agent 收尾時手寫，否則蒸餾沒原料 |
| `memory/recent.md` | 套件產生（今＋昨 daily 合併） | **不會有**，不要手寫 |
| 蒸餾 | 依部署排程 | `scheduler.yaml` 的 `memory-distill` prompt job（§3） |

### build_kiro.py 產出（2.2.0 起）

- 每個 agent 工作目錄建 `memory/daily/`、`memory/archive/`（`.gitkeep`）與 `memory/memory.md` 四分節骨架（`assets/memory/memory.md`）
- `steering/MEMORY.md` 用導覽骨架（`assets/steering/MEMORY-template.md`），不含「每完成一個段落」
- 冪等：已存在的檔不覆寫

## 3. 蒸餾排程（`scheduler.yaml`）

```yaml
  - name: memory-distill
    target: <admin 或 manager instance>
    cron: "20 3 * * *"           # 每日 03:20，早於週日 03:30 的機械歸檔
    enabled: true
    prompt: |
      🧠 記憶蒸餾保鮮（每日）。只處理你自己的記憶，並 broadcast_all 請其他 agent 各自蒸餾。
      你的步驟：① 讀 memory/memory.md（不存在視為空）② 讀近 7 天 memory/daily/*.md
      ③ 判斷「下個月還有用的持久事實」（✅環境慣例/工具怪癖/人與偏好/長期事項；
      ❌臨時進度/一次性操作/已解決問題——那些留 daily）④ 四分節覆寫 memory/memory.md，≤2000 tokens
      ⑤ 近 7 天無新增就不動，回報「無新增」。
      然後 broadcast_all：「請讀自己近 7 天 memory/daily/，把持久事實蒸餾進自己的
      memory/memory.md（四分節、≤2000 tokens），臨時進度留 daily。沒新增就不動。」
      規則：繁中、reply 只回一句摘要（≤30字）、不貼 memory.md 原文。
```

## 4. 既有部署遷移（順序不可逆）

### 前提檢查

| 檢查 | 指令 | 要看到 |
|---|---|---|
| 套件版本 | `curl -s localhost:<health_port>/api/health` | ark_team_agent **≥ 1.11.0** |
| MEMORY.md 多大 | `wc -c .kiro/steering/MEMORY.md` | > 20 KB 才值得全做；< 10 KB 只做 ④ 規範收斂 |
| 歸檔落點 | `ls memory/archive/` | 是 `memory/archive/`（不是 `knowledge/raw/`） |
| 已有蒸餾？ | `grep memory-distill scheduler.yaml` | 沒有 → 步驟 ① 要補 |

### ① 先接上蒸餾（否則瘦身後 agent 失憶）

`scheduler.yaml` 補 §3 的 `memory-distill` job。

### ② 各 agent 建 `memory/memory.md` 骨架（讓蒸餾首次有目標）

```bash
for d in agents/*/ ./; do
  mkdir -p "$d/memory/daily" "$d/memory/archive"
  [ -f "$d/memory/memory.md" ] || cp .kiro/skills/ark-agent-init/assets/memory/memory.md "$d/memory/memory.md"
done
```

### ③ MEMORY.md 瘦身（非破壞搬事件、保留常青段）

```bash
cp .kiro/steering/MEMORY.md output/MEMORY.md.pre-redesign-$(date +%Y%m%d).bak
```

```python
"""scripts/_migrate_memory.py（跑一次即可，跑完刪）"""
import re, pathlib
mem = pathlib.Path(".kiro/steering/MEMORY.md")
text = mem.read_text(encoding="utf-8")
parts = re.split(r'(?m)(?=^## )', text)
date_re = re.compile(r'^## (?:✅ |🧭 )?(\d{4})-(\d{2})-\d{2}')
dated = {}
for s in parts[1:]:
    m = date_re.match(s)
    if m:
        dated.setdefault(f"{m.group(1)}-{m.group(2)}", []).append(s)
for mth, lst in sorted(dated.items()):            # append 到 archive（冪等：已含就跳過）
    t = pathlib.Path(f"memory/archive/{mth}.md")
    head = "" if t.exists() else f"# 記憶歸檔 {mth}\n\n> 由記憶架構遷移手動搬移。append-only。\n\n"
    before = t.read_text(encoding="utf-8") if t.exists() else ""
    add = "".join(lst)
    if add.strip() and add.strip() in before:
        print(f"{mth}: 已存在，跳過"); continue
    with t.open("a", encoding="utf-8") as f:
        f.write(head + add)
    print(f"{mth}: +{len(add.encode())} bytes → {t} ({len(before.encode())}→{t.stat().st_size})")
```

> 🔴 **核對**：archive 新大小 = 原大小 + 新增內容的 **UTF-8 byte 數**（中文 3 bytes/字，不是字元數）。對不上就是搬壞了 → 停，從備份還原。

重寫 MEMORY.md 為 `assets/steering/MEMORY-template.md` 的結構：
**保留**導覽表 + 一行里程碑索引 + 常青段原文（專案狀態／定版結構／技術決策／版本歷史／環境定位）+ 歸檔指標；
**刪除**所有 `## YYYY-MM-DD` 事件分節的細節（已在 archive）。

### ④ 規範收斂到單一權威（本地檔要手改）

- 根 `AGENTS.md`「記憶怎麼用」：MEMORY.md 角色改「導覽 + 判準級精華」、加 🔴 單一權威聲明、daily 標「bot 自動／team 手寫」、memory.md 標 `memory-distill`、歸檔路徑 `memory/archive/`；**移除所有「每完成一個段落更新 MEMORY.md」**
- `BRAIN.md`：事件沿革改走 `memory/daily/`，標單一權威是 AGENTS.md（範本見 `assets/steering/BRAIN.md`「寫」節）
- 各 `agents/*/.kiro/steering/SOUL.md`、`CLAUDE.md`：有「每完成一個段落更新」→ 改「事件 → daily，規則見 AGENTS.md」

> ⚠️ `AGENTS.md`／`MEMORY.md`／`SOUL.md` 的套件 policy 是 `once` → **升級 wheel 救不了既有部署**，本地檔一定要手改；
> 套件範本只影響**新**團隊。

## 5. 驗證

```bash
grep -cE "^## (✅ |🧭 )?[0-9]{4}-" .kiro/steering/MEMORY.md   # 事件分節 → 0（或 ≤ 2）
wc -c .kiro/steering/MEMORY.md                                # 顯著變小（目標 < 20 KB）
ls memory/archive/                                            # 事件在 archive、內容沒丟
python .kiro/skills/ark-agent-init/scripts/build_kiro.py --validate .   # 2.2.0 起會警告 §6 三項
# 隔天：看 03:20 的 log 與 memory/memory.md 的 mtime，確認蒸餾有跑
```

## 6. `build_kiro.py --validate` 的記憶守門（2.2.0 起，皆為 ⚠️ 警告）

| 警告 | 判準 | 處置 |
|---|---|---|
| 缺 `memory/` 骨架 | agent 工作目錄沒有 `memory/daily/` 或 `memory/memory.md` | 照 §4 ② 補 |
| MEMORY.md 過大 | > 20 KB | 照 §4 ③ 瘦身 |
| MEMORY.md 堆事件流水 | `## YYYY-MM-DD` 日期分節 > 5 個 | 搬 archive，留一行里程碑 |
| 舊規範殘留 | steering 內含「每完成一個段落」 | 照 §4 ④ 改寫 |

## 7. 風險與邊界

| 風險 | 處置 |
|---|---|
| 瘦身後 agent 失憶 | **先做 ① 再做 ③**（memory.md 要先能保鮮），順序不可逆 |
| team 側 daily 沒人寫 | team 無自動寫入端 → 收尾手寫 daily，否則蒸餾無料 |
| 搬移搞丟內容 | 位元組核對 + 原始備份 + 每個標題在 archive 只出現一次（防重複 append） |
| 蒸餾出錯誤事實 | daily 被污染會沉澱錯誤 → `memory/memory.md` 定期人工抽查 |
| policy=once | 範本改了既有部署拿不到 → 本地檔手動改 |

**一句話**：先讓 `memory.md` 的蒸餾鏈接上，再把 `MEMORY.md` 從流水帳改回導覽圖 —— 事件去 daily／archive（不注入），判準去 BRAIN，里程碑一行留 MEMORY，持久事實交給排程蒸餾。
