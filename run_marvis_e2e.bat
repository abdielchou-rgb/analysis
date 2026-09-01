@echo off
REM run_marvis_e2e.bat — Marvis主执行E2E管线
REM 用法: run_marvis_e2e.bat "公司名" [report_type]
REM 示例: run_marvis_e2e.bat "浙江觉纤" unlisted_company

setlocal

set ASSET=%~1
if "%ASSET%"=="" (
    echo 用法: run_marvis_e2e.bat "公司名" [report_type]
    echo 示例: run_marvis_e2e.bat "浙江觉纤" unlisted_company
    exit /b 1
)

set REPORT_TYPE=%~2
if "%REPORT_TYPE%"=="" set REPORT_TYPE=unlisted_company

REM Marvis主执行：RUN_MODE=train 让写/骨架/修订走agent_provider(marvis)
REM prefetch/roundtable/merge 保持默认（merge必须用deepseek/openrouter质量红线）
set RUN_MODE=train

REM 写作节点强制走agent_provider
set NODE_PROVIDER_WRITE=agent_provider
set NODE_PROVIDER_SKELETON=agent_provider
set NODE_PROVIDER_REVISE=agent_provider

echo ========================================
echo Marvis E2E 管线
echo 标的: %ASSET%
echo 类型: %REPORT_TYPE%
echo 模式: %RUN_MODE%
echo 写作: agent_provider ^(marvis^)
echo ========================================

cd /d D:\Claude\projects\2hao-analyst
D:\Claude\pro-stack\.venv\Scripts\python.exe main.py "%ASSET%" --type %REPORT_TYPE% 2>&1

echo.
echo 管线结束

endlocal
