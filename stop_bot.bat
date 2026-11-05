@echo off
rem Stop Feishu codex bot: celery worker + main.py long connection
taskkill /F /IM celery.exe >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo [DONE] Bot services stopped. ^(Redis in Docker Desktop is untouched^)
pause
