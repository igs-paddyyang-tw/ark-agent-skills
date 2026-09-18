---
name: ark-mobile-adb
description: >
  透過 Python CLI 直接使用 Android Debug Bridge (adb) 操控 BlueStacks、
  Android Emulator 或 adb 可連線的 Android 裝置。當需要連線模擬器、
  查看裝置、螢幕擷取 screencap、點擊、滑動、輸入文字、按鍵、啟動/停止 App、
  UI hierarchy、安裝 APK、排查 adb/裝置問題，或自動化 Unity/遊戲畫面時觸發。
  優先採用 observe → act → observe → verify；遊戲/Unity 優先使用 screenshot + coordinates。
  不依賴 MCP 或 Node.js（直接控 adb）；若要走 mobile-mcp/MCP 生態的整合，那是另一條路徑。
metadata:
  version: "1.0.0"
  schema_version: 1
  status: active
  updated: 2026-09-18
  category: ops
  outputs:
    - format: data
      audience: ai
  author: paddyyang
---

# ark-mobile-adb

## Purpose

讓 ArkAgent 不透過 MCP，直接以：

```text
ArkAgent → Python CLI → adb → Android / BlueStacks
```

完成 Android 裝置觀察與操作。

## Mandatory workflow

### 1. Always diagnose bottom-up

```text
adb runtime
  ↓
adb devices
  ↓
selected serial
  ↓
screen / foreground app
  ↓
action
  ↓
verification
```

先跑：

```bash
python scripts/ark_mobile_adb.py doctor
```

### 2. Never guess a device

優先：

```bash
--device SERIAL
```

其次：

```text
ARK_MOBILE_DEVICE
.ark-mobile.json
single connected device
```

若有多台 device，必須指定 serial。

### 3. Game / Unity rule

如果 `ui-dump` 只有 FrameLayout / SurfaceView / unitySurfaceView 或幾個全螢幕節點：

**停止依賴 UI hierarchy，改用 screenshot + 座標。**

標準 loop：

```text
screenshot
→ inspect
→ tap/swipe
→ wait
→ screenshot
→ verify
```

### 4. Coordinate rule

先確認：

```bash
python scripts/ark_mobile_adb.py shell wm size
```

若 screenshot 與 physical screen resolution 相同，可直接用 screenshot 座標。

如果 screenshot 被縮放，必須依輸出中的原始尺寸換算座標。

### 5. Important actions require verification

不要連續盲點。

例如：

```bash
python scripts/ark_mobile_adb.py tap 1130 710
python scripts/ark_mobile_adb.py wait 2
python scripts/ark_mobile_adb.py screenshot --out artifacts/after-tap.png
```

## CLI cookbook

```bash
# Diagnose
python scripts/ark_mobile_adb.py doctor
python scripts/ark_mobile_adb.py devices

# BlueStacks
python scripts/ark_mobile_adb.py connect 127.0.0.1:5555

# Observation
python scripts/ark_mobile_adb.py screenshot --out artifacts/screen.png
python scripts/ark_mobile_adb.py foreground
python scripts/ark_mobile_adb.py ui-dump --out artifacts/ui.xml
python scripts/ark_mobile_adb.py shell wm size

# Input
python scripts/ark_mobile_adb.py tap 500 300
python scripts/ark_mobile_adb.py swipe 800 700 800 250 --duration 500
python scripts/ark_mobile_adb.py long-press 800 700 --duration 1000
python scripts/ark_mobile_adb.py text "hello"
python scripts/ark_mobile_adb.py keyevent BACK
python scripts/ark_mobile_adb.py home
python scripts/ark_mobile_adb.py back
python scripts/ark_mobile_adb.py recent

# App
python scripts/ark_mobile_adb.py packages
python scripts/ark_mobile_adb.py launch com.example.app
python scripts/ark_mobile_adb.py stop com.example.app
python scripts/ark_mobile_adb.py clear-data com.example.app
python scripts/ark_mobile_adb.py install app.apk

# Raw adb
python scripts/ark_mobile_adb.py shell dumpsys window
python scripts/ark_mobile_adb.py shell settings get secure android_id

# Agent friendly
python scripts/ark_mobile_adb.py --json devices
python scripts/ark_mobile_adb.py --json foreground
```

## Troubleshooting

### `adb` not found

Install Android Platform Tools and ensure `adb` is discoverable through:

1. `ANDROID_HOME/platform-tools/adb`
2. `ANDROID_SDK_ROOT/platform-tools/adb`
3. common Windows SDK path
4. PATH

Then open a new terminal.

### BlueStacks not visible

In BlueStacks enable Android Debug Bridge and use its displayed port:

```bash
python scripts/ark_mobile_adb.py connect 127.0.0.1:<PORT>
python scripts/ark_mobile_adb.py devices
```

Expected state:

```text
device
```

not `offline`.

### Multiple serials

Do not switch serials between calls. Use:

```bash
python scripts/ark_mobile_adb.py --device SERIAL screenshot
python scripts/ark_mobile_adb.py --device SERIAL tap 100 200
```

### `ui-dump` returns little information

Normal for Unity/custom-rendered games.

Use screenshot + coordinate automation.

### Device disappeared after restart

Reconnect:

```bash
python scripts/ark_mobile_adb.py connect 127.0.0.1:<PORT>
```

Then rerun `doctor`.

## Agent policy

The Skill defines method; the CLI executes commands.

Do not fabricate successful actions. Every mutation should be followed by an observation when the task requires visual confirmation.

Do not use automation to bypass authentication, CAPTCHA, anti-cheat, service restrictions, or authorization controls.

Use test accounts and test environments for automation where appropriate.

## Examples & references

- `examples/bluestacks.json` — BlueStacks 連線設定範例（host:port）
- `examples/.ark-mobile.json` — 專案級裝置設定範例（固定 serial，避免多裝置猜測）
- `examples/game-loop.md` — Unity/遊戲畫面的 screenshot→tap→verify 標準 loop 範例
- `DESIGN.md` — 設計文件（架構、與 mobile-mcp 的改版差異、驗收標準）
