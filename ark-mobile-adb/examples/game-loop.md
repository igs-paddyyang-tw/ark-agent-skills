# Unity / Game Agent Loop

## Goal

Use screenshot-based interaction when UIAutomator does not expose meaningful game controls.

## Loop

1. Capture screenshot.
2. Determine screen resolution.
3. Locate target visually.
4. Tap/swipe.
5. Wait for transition.
6. Capture screenshot again.
7. Verify expected state.
8. Continue or stop.

Example:

```bash
python scripts/ark_mobile_adb.py screenshot --out artifacts/before.png
python scripts/ark_mobile_adb.py tap 1130 710
python scripts/ark_mobile_adb.py wait 2
python scripts/ark_mobile_adb.py screenshot --out artifacts/after.png
```

If the target is small, crop and enlarge the screenshot externally before deciding coordinates.
