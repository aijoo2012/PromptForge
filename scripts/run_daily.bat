@echo off
REM ============================================================
REM  PromptForge 每日任务 - Windows 一键执行
REM  用法：直接双击，或从计划任务调用
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0\.."

REM ---- 日志 ----
set LOG_DIR=output\daily\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\run_%date:~0,4%%date:~5,2%%date:~8,2%.log

echo [%date% %time%] === PromptForge 每日任务开始 === >> "%LOG_FILE%"

REM ---- 激活虚拟环境（如果存在） ----
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [%date% %time%] 已激活 venv >> "%LOG_FILE%"
)

REM ---- 执行每日任务 ----
REM 默认：随机主题/预设 + 6 张图 + 每张不同构图 + 每张换同分类预设 + newspaper 排版 + 推草稿箱
REM 想关掉推送就在末尾加 --no-publish
python scripts\daily_task.py --count 6 --theme newspaper --vary-preset >> "%LOG_FILE%" 2>&1

set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] === 任务结束，退出码 %EXIT_CODE% === >> "%LOG_FILE%"

if not %EXIT_CODE%==0 (
    echo ⚠️ PromptForge 每日任务失败，请查看 %LOG_FILE%
)

exit /b %EXIT_CODE%