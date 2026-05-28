@echo off
chcp 65001 >nul
cd /d %~dp0

:loop
echo [%date% %time%] Starting Agent Team...
py start.py

if exist "restart.flag" (
    del "restart.flag"
    echo [%date% %time%] Restart requested, restarting in 3s...
    timeout /t 3 /nobreak >nul
    goto loop
)

echo [%date% %time%] Stopped.
