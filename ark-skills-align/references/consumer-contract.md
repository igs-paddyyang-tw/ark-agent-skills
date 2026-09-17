# consumer-contract.md — 消費端契約（skills-matrix.yaml + skills.lock.json）

消費端（team repo）對齊 skill 版本的兩份檔:matrix（宣告，git）+ lock（實際，本機不進 git）。
`align_sync.py` 讀 matrix、寫 lock。ADR-002/003。

## skills-matrix.yaml（唯一交接檔，git 版控）

```yaml
schema_version: "1.0"
upstream:
  repo: https://github.com/igs-paddyyang-tw/ark-agent-skills.git
  release: skills-2026.09-r1              # 對齊單位（C-2）；個別 skill 只能例外 pin
  manifest_url: https://raw.githubusercontent.com/igs-paddyyang-tw/ark-agent-skills/main/release/manifest.json
  index_url: https://raw.githubusercontent.com/igs-paddyyang-tw/ark-agent-skills/main/release/index.json
tiers:
  base:   { policy: same-version }        # 全隊同版；major 不一致 P0（AL-301）、minor P1（AL-302）
  role:   { policy: range, default: "^major" }
  domain: { policy: none }                # local_only，不比對上游
agents:
  <專案>-agent: { role: manager, wave: 1 }   # 總機，跑 align、確認 apply（非 admin-agent）
  ops-leader:   { role: leader,  wave: 2 }
  qa-worker:    { role: qa, wave: 3, extra: [ark-test-runner] }
pins:                                     # 例外必附 reason（AL-201 驗不可滿足）
  ark-weknora-cli: { version: "1.4.2", reason: "等 W2 傳輸層驗證", until: 2026-10-01 }
local_only: [ark-fish-daily-report]       # 專案自建，三段判準第①段「不可動」
```

## skills.lock.json（本機狀態，gitignore，每台機器一份）

```json
{
  "release": "skills-2026.09-r1",
  "synced_at": "2026-09-17T14:20:00+08:00",
  "agents": {
    "<專案>-agent": {
      "ark-superpowers": { "version": "2.0.0", "tree_hash": "sha256:…",
                           "source": "upstream@0c4fac3", "tier": "base",
                           "declared_by": ["role-skills-map", "role-profile"] }
    }
  }
}
```

## 為什麼 lock 不進 git

同一個 team repo 會在多台機器各跑一份（個人機/AIPC/AWS）。matrix 是 git 版控的「期望」，
lock 描述「**這台機器現在裝了什麼**」——進 git 會在多機間互相覆寫。日報以 `deployment@host`
為列，同 deployment 不同 host 的差異才看得見。

## align_sync 動詞 × exit code

| 動詞 | exit |
|------|------|
| plan | 0 無差異 / 1 有差異 / 2 matrix/manifest 無法解析 |
| apply --yes | 0 / 1 / 10（無 --yes：只印 plan，C-5 需人私訊 manager 確認） |
| verify | 0 / 1 有 P1 / 2 有 P0 |
| verify --remote | 0 同版 / 1 落後或未知 / 2 無法判定 |
| resolve | 0 查到 / 1 unknown |
| heartbeat | 0（同版只寫 health、不發 TG） |
