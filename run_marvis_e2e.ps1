# run_marvis_e2e.ps1 — Marvis主执行E2E管线
# 用法: .\run_marvis_e2e.ps1 "公司名" [report_type]
# 示例: .\run_marvis_e2e.ps1 "浙江觉纤" unlisted_company

param(
    [Parameter(Mandatory=$true)][string]$Asset,
    [string]$ReportType = "unlisted_company"
)

$ErrorActionPreference = "Continue"

# Marvis主执行：RUN_MODE=train 让写/骨架/修订走agent_provider(marvis)
$env:RUN_MODE = "train"
$env:NODE_PROVIDER_WRITE = "agent_provider"
$env:NODE_PROVIDER_SKELETON = "agent_provider"
$env:NODE_PROVIDER_REVISE = "agent_provider"

Write-Host "========================================"
Write-Host "Marvis E2E 管线"
Write-Host "标的: $Asset"
Write-Host "类型: $ReportType"
Write-Host "模式: $env:RUN_MODE"
Write-Host "写作: agent_provider (marvis)"
Write-Host "========================================"

$start = Get-Date
Push-Location "D:\Claude\projects\2hao-analyst"
& D:\Claude\pro-stack\.venv\Scripts\python.exe main.py $Asset --type $ReportType 2>&1
$exitCode = $LASTEXITCODE
Pop-Location

$duration = (Get-Date) - $start
Write-Host ""
Write-Host "========================================"
Write-Host "管线结束 | 耗时: $($duration.ToString('mm\:ss')) | 退出码: $exitCode"
Write-Host "========================================"

exit $exitCode
