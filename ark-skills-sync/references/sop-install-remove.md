# SOP —— 安裝需要的、移除不需要的與舊名殘留

## manifest（根目錄要哪些）

`<.kiro|.ark>/skills-manifest.yaml`（進版控）：

```yaml
upstream:                       # 可省略，用預設優先序
  path: ~/kiro-cli/github/shared/ark-agent-skills
  url: https://github.com/igs-paddyyang-tw/ark-agent-skills.git
targets: [".", "agents/*"]     # 要管的目錄；projects/ 底下是別的 repo，不要列
include_domains: [general]     # 根目錄依 domain 選（general／game…；all＝全部 active）
include: []                    # 額外指名
exclude: []                    # 明確不要
target_needs:                  # 某個目錄要明列清單時
  agents/qa-agent: [ark-quality-gates, ark-code-spec-validator]
```

沒有 manifest：所有目錄「以已安裝的為準」—— 只對齊，不增不刪。

## 安裝

```bash
python3 $S/skills_sync.py install ark-foo ark-bar --to agents/qa-agent
```

已併入他處的舊名會被拒絕，並提示接手者。

## 移除與舊名殘留（三段判準）

1. **有沒有接手者**：看 stub 的 description「已併入 X」或上游 CHANGELOG
2. **這個 agent 該不該有接手者**：職責相符 → `install` 接手者；不相符（接手者是產骨架的、這個 agent 是執行／維運），
   或舊名當初只是套件不分角色一起裝的 → **只刪不換**
3. **刪**：`skills_sync.py remove <舊名> --from <目錄>`（只 `git rm` 已進版控的；未追蹤的列出交人處理），
   腳本會列出 SOUL／矩陣／README 裡仍寫舊名的地方 → 改成接手者或拿掉

批次：`update --apply --prune`（刪舊名，以及根目錄 manifest 不需要的）。
全面盤點引用：`skills_sync.py residue`（轉呼上游 `scripts/check_consumers.py`）。
