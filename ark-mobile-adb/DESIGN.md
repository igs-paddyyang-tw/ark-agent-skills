# ark-mobile-adb Skill 設計文件 v1.0

## 1. 目標

讓 ArkAgent 可直接掛載一條純本機的行動自動化管線：

**ArkAgent → Skill → Python CLI → adb → Android 模擬器 / BlueStacks**

核心原則：

- 不依賴 MCP、不依賴 Node.js —— 只靠 Python 3.10+ 與 Android Platform Tools 的 `adb`。
- Python 只負責流程編排與 adb 封裝；真正的裝置控制仍由 `adb` 完成。
- Skill 提供「方法與決策規則」，CLI 提供「可執行工具」。
- 所有操作明確指定 `device serial`，避免多模擬器互相操作。
- 遊戲 / Unity 等自繪畫面，以 screenshot + coordinate 為主；不要期待 UIAutomator 提供完整遊戲元素。

## 2. 設計守則與能力總覽

### 決策守則（Skill 教 ArkAgent 的判斷力）

1. 由下往上診斷：`adb → device → app/screen → automation`。
2. BlueStacks ADB 透過 `adb connect host:port`。
3. `adb devices -l` 必須看到 `device`（不是 `offline`）。
4. 多 serial 時固定指定 serial，不在呼叫間切換。
5. Unity / 遊戲畫面優先採 screenshot + 座標，不死磕 UIAutomator。
6. 每次重要操作後重新觀察畫面，不盲點。
7. 使用測試帳號，不將自動化用於繞過服務限制。

### CLI 能力總覽

- 診斷：`doctor`（一次看 adb / device / screen）、`devices`、`connect` / `disconnect`。
- 觀察：`screenshot`、`foreground`、`ui-dump`、`shell`（任意 adb 子指令）。
- 輸入：`tap` / `swipe` / `long-press`、`text`、`keyevent` / `home` / `back` / `recent`。
- App：`launch` / `stop` / `clear-data`、`packages` / `install`。
- 流程：`wait`；所有命令加 `--json` 輸出機器可解析結果。
- 跨平台：Windows / macOS / Linux；adb 定位走 `ANDROID_HOME` / `ANDROID_SDK_ROOT` / PATH 自動探測。
- 設定：專案級 `.ark-mobile.json` 固定裝置；subprocess 固定 UTF-8（中文 dumpsys 不撞 cp950）。
- 可測試的 Python module（`tests/test_cli.py`）。

## 3. 架構

```text
ArkAgent
   │
   ├── Skill: skills/ark-mobile-adb/SKILL.md
   │       ├── decision rules
   │       ├── troubleshooting
   │       └── command cookbook
   │
   └── CLI: scripts/ark_mobile_adb.py
           │
           ├── AdbLocator
           ├── DeviceResolver
           ├── CommandRunner
           ├── Screenshot / UI
           └── App / Input control
                    │
                    ▼
                  adb
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
   BlueStacks                 Android
   emulator                   real device
```

ArkAgent 的責任：

```text
Goal
 → 讀 Skill
 → 判斷目前狀態
 → 呼叫 CLI
 → 取得 JSON / screenshot
 → Observation
 → 再決策
 → Verifier
```

CLI 不負責 LLM 決策。

## 4. 安裝模型

### Skill 安裝

```text
~/.arkagent/skills/ark-mobile-adb/
├── SKILL.md
├── README.md
├── scripts/
│   └── ark_mobile_adb.py
├── examples/
│   ├── bluestacks.json
│   └── game-loop.md
└── tests/
    └── test_cli.py
```

安裝器：

- Windows: `install.ps1`
- macOS/Linux: `install.sh`
- 手動：將整個目錄放入 ArkAgent skills root。

### Runtime 需求

唯一必要 runtime：

- Python 3.10+
- Android Platform Tools (`adb`)

Node.js 不再是必要條件。

## 5. Device 設計

優先順序：

1. CLI `--device SERIAL`
2. `.ark-mobile.json` 的 `device`
3. 環境變數 `ARK_MOBILE_DEVICE`
4. 若只有一台 `device` 狀態的裝置，自動選取
5. 多台時拒絕猜測並列出 serial

這個設計避免：

```text
tap → emulator-5554
screenshot → 127.0.0.1:5555
```

造成畫面與操作不一致。

## 6. 核心命令

```bash
python scripts/ark_mobile_adb.py doctor
python scripts/ark_mobile_adb.py devices
python scripts/ark_mobile_adb.py connect 127.0.0.1:5555
python scripts/ark_mobile_adb.py screenshot --out artifacts/screen.png

python scripts/ark_mobile_adb.py tap 1130 710
python scripts/ark_mobile_adb.py swipe 800 700 800 250 --duration 500
python scripts/ark_mobile_adb.py long-press 800 700 --duration 1000

python scripts/ark_mobile_adb.py text "hello world"
python scripts/ark_mobile_adb.py keyevent BACK
python scripts/ark_mobile_adb.py home
python scripts/ark_mobile_adb.py back

python scripts/ark_mobile_adb.py launch com.example.game
python scripts/ark_mobile_adb.py stop com.example.game
python scripts/ark_mobile_adb.py clear-data com.example.game

python scripts/ark_mobile_adb.py packages
python scripts/ark_mobile_adb.py install app.apk

python scripts/ark_mobile_adb.py foreground
python scripts/ark_mobile_adb.py ui-dump --out artifacts/ui.xml
python scripts/ark_mobile_adb.py shell wm size
```

所有命令預設輸出人類可讀結果；加 `--json` 時輸出機器可解析 JSON。

## 7. Game / Unity 操作策略

```text
1. screenshot
2. 取得 screen size
3. 視覺定位目標
4. tap/swipe
5. wait
6. screenshot
7. 驗證畫面是否符合預期
```

不要：

```text
ui-dump
→ 找不到遊戲按鈕
→ 無限 retry
```

`ui-dump` 仍然保留，因為原生 Android App、設定頁、登入頁等常可透過 UI hierarchy 操作。

## 8. 安全邊界

CLI 不提供：

- 帳號驗證繞過。
- CAPTCHA 破解。
- anti-cheat 繞過。
- 權限繞過。
- 隱藏持久化。
- 未授權裝置控制。

可用於：

- 自己的 App 測試。
- QA。
- BlueStacks 開發環境。
- UI regression。
- 遊戲原型測試。
- CI / local automation。

## 9. 驗收標準

### Level 0 — Runtime

- Python >= 3.10
- `adb version` 成功

### Level 1 — Device

- `doctor` 成功
- `devices` 至少一台 `device`

### Level 2 — Observation

- screenshot 成功
- foreground 成功
- ui-dump 可取得 XML

### Level 3 — Control

- tap
- swipe
- keyevent
- text
- home/back

### Level 4 — App

- launch
- stop
- clear-data
- install

### Level 5 — Agent loop

```text
observe → decide → act → observe → verify
```

## 10. 版本策略

Skill 固定自己的 CLI 介面（子命令名稱、參數、`--json` 輸出結構），不綁定任何外部工具的版本。
唯一的外部相依是 Android Platform Tools 的 `adb`，而 adb 的介面高度穩定。
升版時只需維護本 skill 自己的 CLI 契約與 `skill.json` / SKILL.md frontmatter 的 `metadata.version`。

## 11. 已知環境注意事項（實測踩坑）

以下兩點是實際在中文 Windows 環境跑出來的，已在本 skill 內處理，記錄供消費端理解：

### 中文 dumpsys → cp950 解碼錯（已修）

**症狀**：`foreground` / `ui-dump` / `shell dumpsys` 等讀 shell 輸出的命令，在中文 Windows 上
`UnicodeDecodeError`。
**根因**：`run_cmd` 的 `subprocess.run(text=True)` 未指定 `encoding`，Python 用系統預設
（中文 Windows = cp950）去解 adb 的 UTF-8 輸出。
**修法（已在源頭）**：`run_cmd` 固定 `encoding="utf-8", errors="replace"`。此處覆蓋所有走
`run_cmd` 的命令，一次解決。**使用者不需要再設 `PYTHONUTF8=1` 繞過**。

### Windows 的 `python` 可能是 Store stub（用 `py`）

微軟商店版的 `python` 常是 **Store stub**（執行沒反應或跳商店）。Windows 上請用 Python launcher
**`py`** 跑本 skill 的命令；macOS/Linux 用 **`python3`**。文件範例一律寫 `python`，請替換成你平台上
真正能跑的直譯器。驗證：`py --version`（Windows）／`python3 --version`（mac/Linux）。
