@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo  强制重启 Flask 服务 (端口 5011)
echo ========================================
echo [1] 结束占用 5011 端口的进程...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5011" ^| findstr "LISTENING"') do (
    echo    结束 PID=%%P
    taskkill /F /PID %%P >nul 2>&1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-NetTCPConnection -LocalPort 5011 -State Listen -ErrorAction SilentlyContinue; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 2 /nobreak >nul
netstat -ano | findstr ":5011" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [错误] 5011 仍被占用，请手动结束任务管理器中的 python.exe 后重试
    pause
    exit /b 1
)
echo [2] 5011 已释放，启动新版后端...
echo    目录: %~dp0
echo    版本: PDF fpdf2-light-gradient-v12 + 简约 favicon
python app.py
pause
