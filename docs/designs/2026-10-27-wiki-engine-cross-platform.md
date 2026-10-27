---
title: ark-wiki-engine 跨平台支援設計（Windows / macOS / Linux）
date: 2026-10-27
author: 娜娜 (Kiro IDE)
status: draft
type: design
skill: ark-wiki-engine
skill_version_current: 3.0.3
tags: [wiki-engine, cross-platform, windows, fcntl, file-lock, design]
---

# ark-wiki-engine 跨平台支援設計

## 1. 背景與問題

### 1.1 現象
ark-wiki-engine 在 Windows 原生 Python 上有 **17 項測試失敗**，與上游原版在同一台機器上失敗的是同一批。

### 1.2 根因（實查，非推測）
失敗**不是**「建索引用了一堆 Linux 模組」這麼廣泛，而是收斂到**單一依賴**：

| 位置 | 用途 |
|------|------|
| `scripts/wiki_index.py:24` | `import fcntl`（模組層 import，Windows 無此模組 → `ModuleNotFoundError`，整個檔案載入即失敗） |
| `scripts/wiki_index.py:225` | `fcntl.flock(lock_fd, LOCK_EX \| LOCK_NB)` — build 開始取互斥鎖 |
| `scripts/wiki_index.py:266` | `fcntl.flock(lock_fd, LOCK_UN)` — build 結束釋放鎖 |
| `scripts/tests/test_wiki_v3.py:136-144` | 測試直接 `import fcntl` + `flock`（驗證鎖行為） |
| `scripts/tests/test_index_no_delete.py:19` | 已有 `pytest.importorskip("fcntl")` — **此檔在 Windows 已正確 skip** |

`fcntl` 是 POSIX-only 標準模組，Windows 的 CPython **不提供**。因為 `wiki_index.py` 在**模組頂層** import 它，只要該檔被載入（build / 任何 import 它的測試）就直接炸，連帶 17 個測試失敗。

### 1.3 fcntl 實際只做一件事
掃過 `wiki_index.py` 全檔，`fcntl` 僅用於 **build index 的互斥鎖**（防兩個 build 同時跑互相覆蓋 `.index/`）：
- `lock_path` 放在 `tempfile.gettempdir()`，用 wiki 路徑 hash 命名
- 取不到鎖 → 回 `BUILD_LOCKED` 錯誤碼
- **核心索引邏輯（collect / 寫 json / `os.replace` 原子切換）全部已跨平台**

> 關鍵認知：`os.replace(tmp, idx)`（原子切換）本就跨平台；鎖只是防併發的「額外保護」，不是索引正確性的必要條件。

### 1.4 平台現況修正
| 平台 | 現況 | 說明 |
|------|------|------|
| Linux / WSL | ✅ 正常 | fcntl 原生 |
| **macOS** | ✅ **正常** | macOS 是 POSIX，有 fcntl —— CHANGELOG「只能 Linux/WSL」的說法不精確，macOS 一樣能跑 |
| **Windows** | ❌ 失敗 | 無 fcntl 模組 |

**真正不支援的只有 Windows。** 需求：llm-wiki-agent 會在 Windows 原生執行，故需真正的 Windows 支援，非僅 skip 測試。

## 2. 目標與非目標

### 目標
1. `wiki_index.py` 在 Windows / macOS / Linux 三平台都能 import 與 build
2. 保留「併發 build 互斥」語意（三平台都要有鎖保護）
3. 不引入第三方依賴（遵守本 skill「scripts 零第三方依賴」慣例，見 SKILL.md）
4. 測試在三平台都能跑（Windows 跑 msvcrt 分支，非 skip）
5. **SKILL.md 補跨平台使用說明**（共用 skill 的義務）

### 非目標
- 不改索引格式、搜尋邏輯、JSON 契約（跨平台改動不碰功能）
- 不處理跨「網路檔案系統」的鎖（NFS/SMB 的 flock 語意本就不保證，超出範圍）

## 3. 方案評估

| 方案 | 做法 | 改動 | 依賴 | 風險 | 採用 |
|------|------|------|------|------|:---:|
| **A 平台分支鎖** | fcntl(POSIX) ↔ msvcrt(Windows) 封裝 `_lock/_unlock` | ~15 行，單檔 | 無（msvcrt 是 Windows 標準庫） | 低 | ✅ |
| B 第三方 filelock | 用 `filelock` 套件 | 鎖邏輯全換 | **+1 pip 依賴** | 低 | ❌ 違反零依賴慣例 |
| C O_EXCL 免鎖 | `os.open(O_CREAT\|O_EXCL)` 當鎖 | 中等 | 無 | 中（crash 留死鎖檔，需 stale 清理） | ❌ 失去 fcntl crash 自動釋放優點 |

**採方案 A** —— 改動最小、零依賴、保留 POSIX 的 crash-safe 鎖優點、Windows 用對等的 msvcrt。

## 4. 詳細設計（方案 A）

### 4.1 新增跨平台鎖封裝（wiki_index.py 頂部）

取代 `import fcntl`（line 24）為：

```python
# --- 跨平台檔案鎖（POSIX: fcntl / Windows: msvcrt）---
try:
    import fcntl  # POSIX（Linux / WSL / macOS）

    def _acquire_lock(fd):
        """非阻塞取獨佔鎖；取不到拋 BlockingIOError。"""
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release_lock(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)

except ModuleNotFoundError:  # Windows
    import msvcrt

    def _acquire_lock(fd):
        """非阻塞取鎖；取不到 msvcrt 拋 OSError，統一轉 BlockingIOError。"""
        try:
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as e:
            raise BlockingIOError(str(e)) from e

    def _release_lock(fd):
        try:
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass  # 鎖已釋放或檔案將關閉，忽略
```

### 4.2 cmd_build 內兩處呼叫改用封裝

- line 225：`fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` → `_acquire_lock(lock_fd)`
- line 266：`fcntl.flock(lock_fd, fcntl.LOCK_UN)` → `_release_lock(lock_fd)`
- `except BlockingIOError` 不變（msvcrt 分支已統一轉成 BlockingIOError）

> msvcrt.locking 鎖的是「從目前檔案位置起 N 個位元組」，故 release 前 `seek(0)` 對齊 acquire 時的位置（acquire 時 fd 剛 open 在 offset 0）。鎖 1 byte 作為單一旗標鎖，語意對等。

### 4.3 測試調整

- `test_wiki_v3.py:136` 的 `import fcntl` + flock 區段：改成「import wiki_index 的 `_acquire_lock/_release_lock`」來測，而非直接測 fcntl —— 這樣三平台都能驗鎖行為，且測的是真正用到的封裝
- `test_index_no_delete.py:19` 的 `importorskip("fcntl")`：移除 skip（因為現在 Windows 也有鎖封裝可跑），改為直接測 `_acquire_lock`

### 4.4 模組 docstring 更新
`wiki_index.py:12` 的「互斥：build 取 `.index.lock`（fcntl）」→ 改為「（fcntl on POSIX / msvcrt on Windows）」。

## 5. SKILL.md 跨平台說明（共用 skill 的義務）

在 SKILL.md 補一節（建議放「模式路由」前或文末「相容性」段）：

```markdown
## 跨平台相容性

本 skill 的 scripts 支援 **Linux / WSL / macOS / Windows** 原生 Python（≥ 3.9）。

| 能力 | Linux/WSL | macOS | Windows |
|------|:---:|:---:|:---:|
| wiki_query / ingest / lint / graph | ✅ | ✅ | ✅ |
| wiki_index build（含併發互斥鎖） | ✅ fcntl | ✅ fcntl | ✅ msvcrt |

**併發鎖**：build index 時取互斥鎖防兩個 build 互相覆蓋。POSIX 用 `fcntl.flock`、
Windows 用 `msvcrt.locking`，行為對等（非阻塞，取不到回 `BUILD_LOCKED`）。

**Windows 注意事項**：
- 需 Python ≥ 3.9（msvcrt 為標準庫，無需額外安裝）
- 索引鎖檔落在 `%TEMP%`（POSIX 落 `/tmp`），用 wiki 路徑 hash 命名，不互鎖
- 路徑一律用 `pathlib.Path`，已處理分隔符差異；呼叫腳本時 Windows 用 `py -3` 或 `python`
- 不支援跨網路磁碟（SMB/NFS）的併發鎖 —— 鎖語意在網路檔案系統不保證

**零第三方依賴**：跨平台鎖用 Python 標準庫（fcntl/msvcrt）條件 import，未新增 pip 依賴。
```

## 6. 驗證計畫（遵守「新檢查要先反證會不會紅」）

1. **Linux/WSL**（本機）：全測試綠（含改後的鎖測試）；手動跑兩個並行 build 確認第二個回 `BUILD_LOCKED`
2. **Windows**：
   - 反證「鎖真的有作用」：並行跑兩個 build，第二個必須回 `BUILD_LOCKED`（不能兩個都成功 → 那是鎖沒生效）
   - 正向：單一 build 正常產 `.index/`、`wiki_query` 可查
   - 17 個原失敗測試轉綠
3. **macOS**（若有環境）：同 Linux 路徑，應全綠
4. 清理：確認鎖檔在 build 結束/crash 後不殘留致死鎖（msvcrt 分支 release 的 except 要涵蓋）

## 7. 版本與發布

- 這是 bug fix + 相容性擴展，無契約變更 → 升 **3.0.4**（patch，上游基礎 3.0.3）
- CHANGELOG 補：「修 Windows fcntl 不可用 → 加 msvcrt 分支鎖；SKILL.md 補跨平台說明；macOS 本就支援（更正先前 CHANGELOG 說法）」
- 走 ark-skills-align 的 release train 對齊 manifest
- 消費端（含 llm-wiki-agent）各自 mirror_sync 同步

## 8. 風險與回退

| 風險 | 緩解 |
|------|------|
| msvcrt.locking 語意與 flock 不完全一致（鎖位元組非整檔） | 只鎖 1 byte 當旗標，兩者對「單一 build 互斥」等效；驗證計畫第 2 點反證 |
| crash 後鎖檔殘留 | fcntl/msvcrt 的 OS 層鎖在行程結束時自動釋放；鎖檔本身（空檔）殘留無害，下次 build 重用 |
| 回退 | 改動集中單檔 + 測試，git revert 即可；不碰索引格式故無資料遷移風險 |

## 9. 範圍釐清（2026-10-27 已查證）

1. **llm-wiki-agent 的 Windows runtime 走自己的實作**：`src/skills/wiki_skills/`（含獨立 `wiki_indexer.py`），**完全不用 fcntl**（grep 零命中），故 llm-wiki-agent 在 Windows 的功能本就正常。17 項失敗是**跑 ark-wiki-engine skill 本身的測試套件**失敗，非 llm-wiki-agent runtime 失敗。
2. **本修正的意義**：ark-wiki-engine 是**共用 skill 資產**，任何人若直接呼叫其 `scripts/wiki_index.py`（不透過 llm-wiki-agent）在 Windows 就會因 fcntl 炸。讓 skill 本體跨平台 + 文件說明，是「共用 skill 該跨平台」的正解，與 llm-wiki-agent 是否用它無關。
3. 待確認：是否有 macOS CI 環境可納入驗證矩陣；版號 3.0.4 是否符合當前 release train 節奏。
