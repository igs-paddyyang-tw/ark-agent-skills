@echo off
chcp 65001 >nul
echo ══════════════════════════════════════
echo   🤖 AI Agent Bot 啟動中...
echo ══════════════════════════════════════
echo.

REM 載入 .env
if exist .env (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
        if not "%%a"=="" set "%%a=%%b"
    )
)

echo [啟動] Web + Bot + 排程（整合模式）
py -m uvicorn src.server.main:app --host 127.0.0.1 --port 8000

pause
