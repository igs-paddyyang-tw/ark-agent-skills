#!/bin/bash
# ─────────────────────────────────────────────
#  ark-team-agent Watchdog (Linux/Mac)
#  偵測 restart.flag → 自動重啟
#  正常退出（無 flag）→ 停止
# ─────────────────────────────────────────────
cd "$(dirname "$0")"
export ARK_TEAM_AGENT_HOME="${ARK_TEAM_AGENT_HOME:-$(pwd)}"

while true; do
    echo "[$(date)] Starting team-agent..."
    python3 start.py

    if [ -f "$ARK_TEAM_AGENT_HOME/restart.flag" ]; then
        rm -f "$ARK_TEAM_AGENT_HOME/restart.flag"
        echo "[$(date)] Restart requested, restarting in 3s..."
        sleep 3
        continue
    fi

    echo "[$(date)] Team-agent exited without restart flag. Stopping."
    break
done
