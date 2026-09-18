#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="ark-mobile-adb"
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="${ARK_SKILLS_DIR:-$HOME/.arkagent/skills}"
TARGET="$TARGET_ROOT/$SKILL_NAME"

mkdir -p "$TARGET_ROOT"
rm -rf "$TARGET"
cp -R "$SOURCE" "$TARGET"

echo "Installed $SKILL_NAME to $TARGET"
echo "Test:"
echo "  python3 \"$TARGET/scripts/ark_mobile_adb.py\" doctor"
