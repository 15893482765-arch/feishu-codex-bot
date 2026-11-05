@echo off
cd /d D:\newcode\PythonProject\feishu_codex_bot

rem ===== 1. Check Redis (it runs inside Docker Desktop) =====
powershell -NoProfile -Command "exit ([int](-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue)))"
if errorlevel 1 (
  echo [ERROR] Redis 127.0.0.1:6379 is NOT reachable.
  echo Please start Docker Desktop first ^(redis container^), then run this script again.
  pause
  exit /b 1
)
echo [OK] Redis is running.

rem ===== 2. Start Celery worker =====
start "feishu-codex-celery" cmd /k ".venv\Scripts\celery.exe -A tasks worker --pool=solo --loglevel=info > celery.log 2>&1"

rem ===== 3. Start Feishu bot long connection =====
start "feishu-codex-bot" cmd /k ".venv\Scripts\python.exe main.py > bot.log 2>&1"

echo.
echo [DONE] Celery worker + Feishu bot started in two new windows.
echo Logs: celery.log / bot.log
echo Now you can @ the bot in Feishu group.
pause
