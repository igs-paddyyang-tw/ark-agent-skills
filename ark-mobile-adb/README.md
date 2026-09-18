# ark-mobile-adb

Python-first ArkAgent Skill for Android / BlueStacks automation.

## Requirements

- Python 3.10+
- Android Platform Tools
- `adb`
- BlueStacks or Android device/emulator

No Node.js. No MCP.

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
