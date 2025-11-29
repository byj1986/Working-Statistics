@echo off
REM 工作时间提醒器 - 开机自启动脚本
REM 请将此文件的快捷方式放入启动文件夹
chcp 65001 >nul 2>&1

REM 设置程序目录（自动获取批处理文件所在目录）
REM %~dp0 返回批处理文件所在目录（带尾部反斜杠）
set "PROGRAM_DIR=%~dp0"
set "PY_FILE=app_tracker.py"

REM 切换到程序目录
cd /d "%PROGRAM_DIR%"

REM 尝试PATH中的 pythonw
pythonw "%PROGRAM_DIR%%PY_FILE%" >nul 2>&1
if not errorlevel 1 exit /b 0
