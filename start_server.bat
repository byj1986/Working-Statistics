@echo off
chcp 65001 >nul
echo ============================================
echo 启动 Statistics 服务器
echo ============================================
echo.

REM 检查端口是否被占用
echo 检查端口 8000 是否被占用...
netstat -ano | findstr :8000 >nul
if %errorlevel% == 0 (
    echo 发现端口 8000 已被占用，正在查找进程...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
        echo 发现进程 PID: %%a
        echo 正在停止进程...
        taskkill /PID %%a /F >nul 2>&1
        if %errorlevel% == 0 (
            echo 已停止进程 PID: %%a
        ) else (
            echo 无法停止进程，可能需要管理员权限
        )
        timeout /t 1 >nul
    )
)

echo.
echo 启动服务器...
echo.
python server.py
pause

