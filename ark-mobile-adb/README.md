# ark-mobile-adb

Python-first ArkAgent Skill for Android / BlueStacks automation.

## Requirements

- Python 3.10+
- Android Platform Tools
- `adb`
- BlueStacks or Android device/emulator

No Node.js. No MCP.

> 直譯器名稱依平台而異：Windows 用 **`py`**（商店版 `python` 常是 Store stub），
> macOS/Linux 用 **`python3`**。下文範例一律寫 `python`，請替換成你平台能跑的那個。
> CLI 已在 subprocess 層固定 UTF-8，中文 dumpsys 不會撞 cp950（無需設 `PYTHONUTF8`）。

## Quick start

```bash
python scripts/ark_mobile_adb.py doctor
python scripts/ark_mobile_adb.py devices
```

BlueStacks:

```bash
python scripts/ark_mobile_adb.py connect 127.0.0.1:5555
python scripts/ark_mobile_adb.py doctor
```

Screenshot:

```bash
python scripts/ark_mobile_adb.py screenshot --out artifacts/screen.png
```

Control:

```bash
python scripts/ark_mobile_adb.py tap 500 300
python scripts/ark_mobile_adb.py swipe 800 700 800 250 --duration 500
python scripts/ark_mobile_adb.py keyevent BACK
```

## Install Skill

Windows PowerShell:

```powershell
.\install.ps1
```

macOS/Linux:

```bash
bash ./install.sh
```

Default destination:

```text
~/.arkagent/skills/ark-mobile-adb
```

Override:

```bash
ARK_SKILLS_DIR=/path/to/skills bash ./install.sh
```

## Configuration

Create `.ark-mobile.json` in your project:

```json
{
  "device": "127.0.0.1:5555"
}
```

Or set:

```text
ARK_MOBILE_DEVICE=127.0.0.1:5555
```

CLI `--device` always wins.

## Design

See `DESIGN.md`.

## Game automation

For Unity/custom rendering:

```text
screenshot → locate target → tap/swipe → wait → screenshot → verify
```

Do not repeatedly retry UI hierarchy when the game exposes only a SurfaceView.
