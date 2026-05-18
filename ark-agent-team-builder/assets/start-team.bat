@echo off
chcp 65001 >nul
REM ─────────────────────────────────────────────
REM  ark-team-agent Watchdog (Windows)
REM  偵測 restart.flag → 自動重啟
REM  正常退出（無 flag）→ 停止
REM ─────────────────────────────────────────────
set ARK_TEAM_AGENT_HOME=%~dp0
cd /d %~dp0

:loop
echo [%date% %time%] Starting team-agent...
py -m ark_team_agent team start

if exist "%ARK_TEAM_AGENT_HOME%restart.flag" (
    del "%ARK_TEAM_AGENT_HOME%restart.flag"
    echo [%date% %time%] Restart requested, restarting in 3s...
    timeout /t 3 /nobreak >nul
    goto loop
)

echo [%date% %time%] Team-agent exited without restart flag. Stopping.
