#!/bin/bash
# 柯力油位报告一键执行（R82 封装，最高信任命令）
# 用法: bash scripts/run_oil_report.sh [train|perf]
cd "$(dirname "$0")/.."
MODE="${1:-train}"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
export DEEPSEEK_API_KEY=$(grep '^DEEPSEEK_API_KEY=' .env | cut -d= -f2 | tr -d '"')
echo "=== 柯力油位报告执行 [mode=$MODE] ==="
python scripts/run_reports.py "油位传感器" --type industry_deep \
  --mode "$MODE" --workers 1 \
  --enrich-file data/keli_oil_enrich_20260805.json
echo "=== 完成 exit=$? ==="
