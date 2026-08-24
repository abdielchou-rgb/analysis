@echo off
REM ============================================================
REM 2hao-analyst 三份深度报告一键运行
REM 标的: 中芯国际 / 宁德时代 / 汇川技术
REM 类型: listed_company (上市公司深度分析)
REM 风格: cicc
REM ============================================================
chcp 65001 >nul
cd /d %~dp0

echo ============================================================
echo  2hao-analyst — 三份深度报告批量运行
echo  时间: %date% %time%
echo ============================================================
echo.

REM ---- 环境准备：安装依赖（若缺） ----
echo [1/4] 检查依赖...
python -c "import akshare, tavily, openai, pdfplumber" 2>nul
if errorlevel 1 (
    echo   ^> 安装依赖中...
    pip install -r requirements.txt
)

echo.
echo [2/4] 检查 API 密钥 (.env)...
if not exist .env (
    echo   [!!] 缺少 .env 文件！请先创建 .env 并填入 DEEPSEEK_API_KEY / TAVILY_API_KEY
    pause
    exit /b 1
)
python -c "import os; os.environ['K']='1'"
echo   ^> .env 存在

echo.
echo [3/4] 生成三份报告（每份约 5-15 分钟）...
set ENFORCE_GATE=true

echo   --- 第1份: 中芯国际 ---
python pipeline\scheduler.py "中芯国际" --type listed_company --style cicc --output output
if errorlevel 1 echo   [!!] 中芯国际失败

echo   --- 第2份: 宁德时代 ---
python pipeline\scheduler.py "宁德时代" --type listed_company --style cicc --output output
if errorlevel 1 echo   [!!] 宁德时代失败

echo   --- 第3份: 汇川技术 ---
python pipeline\scheduler.py "汇川技术" --type listed_company --style cicc --output output
if errorlevel 1 echo   [!!] 汇川技术失败

echo.
echo [4/4] 完成！报告输出在 output/ 目录
echo ============================================================
dir output\*中芯*.docx output\*宁德*.docx output\*汇川*.docx 2>nul
echo ============================================================
pause
