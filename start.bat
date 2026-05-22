@echo off
cd /d "%~dp0"

REM 安全关闭之前的后端进程（只杀掉占用5001-5010端口的Python进程）
for /l %%p in (5001,1,5010) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /c:"%%p " ^| findstr "LISTENING"') do (
        tasklist /fi "PID eq %%a" 2>nul | findstr /i "python" >nul && (
            taskkill /f /pid %%a 2>nul
        )
    )
)

if not exist "node_modules" (
    npm install
)

npm start
