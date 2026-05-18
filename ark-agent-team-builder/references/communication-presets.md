# 通訊策略預設組合

## 預設組合

### 嚴格模式（2-3 人團隊推薦）

所有通訊經 leader 中轉，worker 不可互發。

```yaml
communication:
  p2p:
    enabled: false
    cc_leader: true
    daily_limit_per_agent: 0
    max_rounds: 0
    emergency_mode: false
```

**適用：** 小團隊、需要 leader 完全掌控流程。

---

### 標準模式（4-6 人團隊推薦）

Worker 可互發，CC leader，3 輪後升級。

```yaml
communication:
  p2p:
    enabled: true
    cc_leader: true
    daily_limit_per_agent: 10
    max_rounds: 3
    emergency_mode: false
```

**適用：** 中型團隊、需要協作但保留監控。

---

### 開放模式（信任團隊）

Worker 自由通訊，不 CC leader，5 輪後升級。

```yaml
communication:
  p2p:
    enabled: true
    cc_leader: false
    daily_limit_per_agent: 20
    max_rounds: 5
    emergency_mode: false
```

**適用：** 成熟團隊、worker 有自主判斷力。

---

### 緊急模式（臨時啟用）

所有通訊強制經 leader，用於排查問題。

```yaml
communication:
  p2p:
    enabled: true
    cc_leader: true
    daily_limit_per_agent: 10
    max_rounds: 3
    emergency_mode: true    # ← 關鍵：強制所有通訊經 leader
```

**適用：** 出問題時臨時切換，排查後恢復。

---

## 欄位說明

| 欄位 | 型別 | 說明 |
|------|------|------|
| `enabled` | bool | true = worker 可互發 |
| `cc_leader` | bool | 每次 P2P 自動 CC leader（留痕） |
| `daily_limit_per_agent` | int | 每個 worker 每天最多 P2P 次數 |
| `max_rounds` | int | 同一對 agent 最多 N 輪來回，超過升級 leader |
| `emergency_mode` | bool | true = 所有通訊強制經 leader |

## 選擇建議

| 團隊規模 | 推薦模式 | 原因 |
|---------|---------|------|
| 2-3 人 | 嚴格 | leader 能直接管理，不需 P2P |
| 4-6 人 | 標準 | 需要協作但保留可見性 |
| 7+ 人 | 開放 | 減少 leader 瓶頸 |
| 出問題時 | 緊急 | 臨時收攏控制 |
