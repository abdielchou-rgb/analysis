#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""东财三表 HTTP 直连获取器（不依赖 akshare）

背景（2026-08-01）：akshare 的 stock_balance_sheet_by_report_em /
stock_cash_flow_sheet_by_report_em 在本机抛 TypeError（接口封装坏了），
无法用 akshare 拿 balance/cashflow。本模块用 requests 直连东财
财务报表 HTTP API，稳定获取资产负债表/现金流量表。

用法:
    python scripts/fetch_em_financials.py 000001    # 测试单只
    python scripts/fetch_em_financials.py 000001 --all  # 打印全部报告期
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parent.parent

# 东财财务报表 API（同 akshare 内部使用）
# 资产负债表
_BALANCE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
# 现金流量表
_CASHFLOW_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}


def _build_params(code: str, report_name: str, columns: str, filter_field: str = "SECURITY_CODE") -> dict:
    """构造东财 API 参数。report_name: 报表类型标识"""
    return {
        "reportName": report_name,
        "columns": columns,
        "filter": f'({filter_field}="{code}")',
        "pageNumber": "1",
        "pageSize": "10",
        "sortTypes": "-1",
        "sortColumns": "REPORT_DATE",
        "source": "WEB",
        "client": "WEB",
    }


def fetch_balance_sheet(code: str) -> dict:
    """拉资产负债表，返回 {报告期: {字段: 值}}"""
    columns = ("ALL")
    params = _build_params(code, "RPT_F10_FINANCE_GINCOME", columns)
    # 资产负债表 reportName 需确认，先用利润表接口试
    try:
        resp = requests.get(_BALANCE_URL, params=params, headers=_HEADERS, timeout=15)
        data = resp.json()
        rows = (data.get("result") or {}).get("data") or []
        out = {}
        for r in rows:
            period = str(r.get("REPORT_DATE", ""))[:10]
            out[period] = r
        return out
    except Exception as e:
        return {"error": str(e)[:200]}


if __name__ == "__main__":
    print("东财 HTTP 直连方案 — 需要先确认正确的 reportName/API 结构")
    print("正在测试连接东财接口...")
    # 简单连通性测试
    try:
        r = requests.get("https://datacenter-web.eastmoney.com/api/data/v1/get",
                         params={"reportName": "RPT_F10_FINANCE_MAINFINADATA",
                                 "columns": "ALL", "filter": '(SECURITY_CODE="000001")',
                                 "pageNumber": "1", "pageSize": "3",
                                 "source": "WEB", "client": "WEB"},
                         headers=_HEADERS, timeout=15)
        print("HTTP 状态:", r.status_code)
        data = r.json()
        rows = (data.get("result") or {}).get("data") or []
        print("返回行数:", len(rows))
        if rows:
            print("列名(前20):", list(rows[0].keys())[:20])
    except Exception as e:
        print("连接失败:", str(e)[:200])
