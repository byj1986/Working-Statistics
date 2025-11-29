@echo off
REM 工作时间提醒器 - 开机自启动脚本
REM 请将此文件的快捷方式放入启动文件夹
chcp 65001 >nul 2>&1

REM 设置程序目录（请根据实际路径修改）
set "PROGRAM_DIR=D:\Statistics"
set "PY_FILE=app_tracker.py"

REM 切换到程序目录
cd /d "%PROGRAM_DIR%"

REM 尝试PATH中的 pythonw
pythonw "%PROGRAM_DIR%\%PY_FILE%" >nul 2>&1
if not errorlevel 1 exit /b 0
