@echo off
REM ============================================================
REM  MinerU 一键安装脚本 (Windows PowerShell / CMD)
REM  目标：本地引擎 + 云 CLI + MCP Server 全量可用
REM  运行：右键"以管理员身份运行"，或命令行执行
REM ============================================================
chcp 65001 >nul
echo ================================================
echo  MinerU 部署脚本 (Windows)
echo ================================================

echo.
echo [1/4] 检查 Python 环境...
python --version 2>nul || (echo [错误] 未找到 Python，请先安装 Python 3.10+ 并加入 PATH & pause & exit /b 1)

echo.
echo [2/4] 安装本地 MinerU 引擎（约 300MB，模型首次运行下载 ~3GB）...
python -m pip install --upgrade mineru --break-system-packages
if errorlevel 1 (echo [警告] mineru 安装失败，可跳过本地引擎仅用云 API & choice /c YN /m "继续？" & if errorlevel 2 goto:cloud_only)

echo.
echo [3/4] 安装云 CLI + MCP Server（MinerU-Ecosystem）...
python -m pip install --upgrade mineru-open-sdk --break-system-packages
if errorlevel 1 (echo [警告] mineru-open-sdk 安装失败 & choice /c YN /m "继续？" & if errorlevel 2 goto:done)
python -m pip install --upgrade mineru-open-mcp --break-system-packages
if errorlevel 1 (echo [提示] mineru-open-mcp 可能未发布到 PyPI，改用 uvx 方式 & goto:cloud_only)

echo.
echo [4/4] 验证...
mineru --version 2>nul && echo [OK] 本地引擎已装
mineru-open-api --help 2>nul >nul && echo [OK] 云 CLI 已装

echo.
echo ================================================
echo  安装完成。下一步：
echo   1. 本地引擎：mineru -p test.pdf -o ./out
echo   2. 云 Flash：  mineru-open-api flash-extract test.pdf
echo   3. 云 Precision：mineru-open-api auth  # 首次登录
echo   4. Claude MCP：运行 mineru-open-mcp 并参考 docs/mineru-deployment.md 配置
echo ================================================
pause
exit /b 0

:cloud_only
echo [提示] 已跳过本地引擎，仅云 API 可用（免 token 但限 20 页/10MB）。
echo        如需本地引擎，重新运行脚本或手动：pip install mineru
goto done

:done
pause
exit /b 0
