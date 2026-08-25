#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2hao-analyst 财务层查漏补缺脚本 — akshare 补最新季度 → 本地 SQLite

配合 sync_financials.py（Baostock 历史层）使用：
  Baostock: 免费稳定，但财务数据滞后约 3 季度（当前到 2025Q3）
  akshare:  同花顺财务摘要，实时性好（能补上 2025Q4/2026Q1/Q2）

本脚本只补库内缺失的季度（增量），字段格式与 Baostock 对齐写入 financials.db，
下游（_local_search/图表/离线兜底）无需改动即可读到完整数据。

用法:
    python scripts/sync_akshare_financials.py --batch 20 --workers 4
    python scripts/sync_akshare_financials.py --batch 20 --dry-run   # 预览要补什么
    python scripts/sync_akshare_financials.py "600519"               # 单只

数据源: akshare stock_financial_abstract_ths（同花顺）
  - 按报告期拉取，含 2025Q4 / 2026Q1 / 2026Q2 最新季度
  - 字段: 报告期/营业总收入/净利润/销售毛利率/净资产收益率/基本每股收益/资产负债率

字段映射（akshare → financials.db，单位对齐 Baostock）:
  profit.MBRevenue    = 营业总收入           (元，原样)
  profit.netProfit    = 净利润               (元，原样)
  profit.gpMargin     = 销售毛利率 / 100      (Baostock 存比值 0.xx)
  profit.roeAvg       = 净资产收益率 / 100    (比值)
  profit.epsTTM       = 基本每股收益          (元)
  balance.totalAssets = 总资产               (元)
  balance.totalLiab   = 总负债               (元)
  balance.totalEquity = 股东权益合计          (元)
  balance.cashAssets  = 货币资金             (元)
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures import TimeoutError as concurrent_futures_timeout
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "financials.db"
INSTRUMENTS = _ROOT / "data" / "qlib_bin" / "instruments" / "all.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("sync_ak")

_HAS_AKSHARE = False
try:
    import akshare as ak

    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare 未安装")

# ──────────────────────────────────────────────────────────────
# 字段映射：akshare 中文列 → (table_name, field, 单位变换函数)
# R27（2026-08-02 全量明细）：扩展三表明细到 30+ 字段
# ──────────────────────────────────────────────────────────────
PROFIT_MAP = {
    "营业总收入": ("profit", "MBRevenue", lambda v: v),  # 元
    "营业收入": ("profit", "MBRevenue", lambda v: v),
    "净利润": ("profit", "netProfit", lambda v: v),  # 元
    "销售毛利率": ("profit", "gpMargin", lambda v: v / 100),  # % → 比值
    "净资产收益率": ("profit", "roeAvg", lambda v: v / 100),  # % → 比值
    "基本每股收益": ("profit", "epsTTM", lambda v: v),  # 元
    "资产负债率": ("balance", "totalLiab", None),  # 占位，见下
    # R27 新增：利润表明细
    "营业成本": ("profit", "operatingCost", lambda v: v),  # 元
    "营业总成本": ("profit", "operatingCost", lambda v: v),
    "研发费用": ("profit", "RD", lambda v: v),  # 元（R53 字段名规范为 RD）
    "销售费用": ("profit", "sellExpense", lambda v: v),  # 元
    "管理费用": ("profit", "manageExpense", lambda v: v),  # 元
    "财务费用": ("profit", "financeExpense", lambda v: v),  # 元
    "营业利润": ("profit", "operateProfit", lambda v: v),  # 元
    "利润总额": ("profit", "totalProfit", lambda v: v),  # 元
    "所得税费用": ("profit", "incomeTax", lambda v: v),  # 元
    "扣非净利润": ("profit", "deductNetProfit", lambda v: v),  # 元
}
# 从按报告期数据可获得的资产负债表字段（若有）
BALANCE_MAP = {
    "总资产": ("balance", "totalAssets", lambda v: v),
    "总负债": ("balance", "totalLiab", lambda v: v),
    "股东权益合计": ("balance", "totalEquity", lambda v: v),
    "货币资金": ("balance", "cashAssets", lambda v: v),
    # R27 新增：资产负债表明细
    "应收账款": ("balance", "accountsReceivable", lambda v: v),  # 元
    "应收票据": ("balance", "notesReceivable", lambda v: v),
    "存货": ("balance", "inventory", lambda v: v),  # 元
    "商誉": ("balance", "goodwill", lambda v: v),  # 元
    "固定资产": ("balance", "fixedAssets", lambda v: v),  # 元
    "无形资产": ("balance", "intangibleAssets", lambda v: v),  # 元
    "短期借款": ("balance", "shortLoan", lambda v: v),  # 元
    "长期借款": ("balance", "longLoan", lambda v: v),  # 元
    "应付账款": ("balance", "accountsPayable", lambda v: v),  # 元
    "应付债券": ("balance", "bondPayable", lambda v: v),  # 元（R53 新增）
    "预收款项": ("balance", "advanceReceived", lambda v: v),  # 元
    "流动负债合计": ("balance", "totalCurrentLiab", lambda v: v),  # 元
    "非流动负债合计": ("balance", "totalNonCurrentLiab", lambda v: v),
}

# 现金流量表字段映射（akshare 东财接口 → financials.db，单位对齐 Baostock）
CASHFLOW_MAP = {
    "经营活动产生的现金流量净额": ("cashflow", "OCF", lambda v: v),
    "投资活动产生的现金流量净额": ("cashflow", "ICF", lambda v: v),
    "筹资活动产生的现金流量净额": ("cashflow", "FCF", lambda v: v),
    # R27 新增：现金流明细
    "销售商品、提供劳务收到的现金": ("cashflow", "cashFromSales", lambda v: v),
    "购建固定资产、无形资产和其他长期资产支付的现金": ("cashflow", "capex", lambda v: v),
    # R53 新增：折旧摊销（固定资产折旧、油气资产折耗、生产性生物资产折旧，年报/中报披露）
    "折旧摊销": ("cashflow", "DA", lambda v: v),
}

# 东财接口列名 → 我们映射用的中文列名
# akshare stock_balance_sheet_by_report_em 返回列名（实测 akshare_connector.py 用小写）
# 同时兼容大小写（TOTAL_ASSETS / total_assets）——2026-08-01 修复
_EM_BALANCE_COLS = {
    "TOTAL_ASSETS": "总资产",
    "total_assets": "总资产",
    "TOTAL_LIABILITIES": "总负债",
    "total_liabilities": "总负债",
    "TOTAL_EQUITY": "股东权益合计",
    "total_equity": "股东权益合计",
    "MONETARYFUNDS": "货币资金",
    "monetaryfunds": "货币资金",
    "货币资金": "货币资金",
    # R27 新增：资产负债表明细列名映射（东财返回中文）
    "应收账款": "应收账款",
    "应收票据": "应收票据",
    "存货": "存货",
    "商誉": "商誉",
    "固定资产": "固定资产",
    "无形资产": "无形资产",
    "短期借款": "短期借款",
    "长期借款": "长期借款",
    "应付账款": "应付账款",
    "预收款项": "预收款项",
    "流动负债合计": "流动负债合计",
    "非流动负债合计": "非流动负债合计",
}
# akshare stock_cash_flow_sheet_by_report_em
_EM_CASHFLOW_COLS = {
    "NETCASH_OPERATE": "经营活动产生的现金流量净额",
    "netcash_operate": "经营活动产生的现金流量净额",
    "NETCASH_INVEST": "投资活动产生的现金流量净额",
    "netcash_invest": "投资活动产生的现金流量净额",
    "NETCASH_FINANCE": "筹资活动产生的现金流量净额",
    "netcash_finance": "筹资活动产生的现金流量净额",
    "经营活动产生的现金流量净额": "经营活动产生的现金流量净额",
    # R27 新增：现金流明细列名
    "销售商品、提供劳务收到的现金": "销售商品、提供劳务收到的现金",
    "购建固定资产、无形资产和其他长期资产支付的现金": "购建固定资产、无形资产和其他长期资产支付的现金",
}
# R27 新增：利润表明细列名映射（stock_profit_sheet_by_report_em 返回）
_EM_PROFIT_COLS = {
    "营业总收入": "营业总收入",
    "营业收入": "营业收入",
    "营业总成本": "营业总成本",
    "营业成本": "营业成本",
    "研发费用": "研发费用",
    "销售费用": "销售费用",
    "管理费用": "管理费用",
    "财务费用": "财务费用",
    "营业利润": "营业利润",
    "利润总额": "利润总额",
    "净利润": "净利润",
    "所得税费用": "所得税费用",
    "基本每股收益": "基本每股收益",
    "扣非净利润": "扣非净利润",
}


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS financials (
            code TEXT NOT NULL,
            quarter TEXT NOT NULL,
            table_name TEXT NOT NULL,
            field TEXT NOT NULL,
            value REAL,
            source TEXT DEFAULT 'baostock',
            PRIMARY KEY (code, quarter, table_name, field)
        )
    """)
    # 迁移：旧库无 source 列 → 添加（默认 baostock 历史数据）
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(financials)")}
        if "source" not in cols:
            conn.execute("ALTER TABLE financials ADD COLUMN source TEXT DEFAULT 'baostock'")
            conn.commit()
            logger.info("[MIGRATE] financials 表新增 source 列（默认 baostock）")
    except Exception as e:
        logger.warning("[MIGRATE] source 列迁移失败: %s", e)
    conn.commit()
    return conn


def _latest_quarters(code: str) -> set:
    """库内已有的季度集合（跨表合并，向后兼容）

    注意：旧逻辑按 code 取全部季度合并，导致 profit 最新季度掩盖 balance/cashflow 缺失。
    新逻辑用 _latest_quarters_by_table 按表独立判断（见 sync_code）。
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT DISTINCT quarter FROM financials WHERE code=?", (code,)).fetchall()
        conn.close()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _latest_quarters_by_table(code: str) -> dict:
    """按表返回库内已有季度集合 {table_name: set(quarter)}

    修复（2026-08-01 审计）：增量判断必须按表独立，避免 profit 的
    最新季度掩盖 balance/cashflow 的缺口（同 sync_financials.py 的修复）。
    """
    out = {"profit": set(), "balance": set(), "cashflow": set()}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT DISTINCT table_name, quarter FROM financials WHERE code=?", (code,)).fetchall()
        conn.close()
        for t, q in rows:
            if t in out:
                out[t].add(q)
    except Exception:
        pass
    return out


def _parse_cn_num(val) -> float | None:
    """解析中文数字单位字符串 → float

    支持: "6.06亿"→606000000, "9021.95万"→90219500, "35.60%"→35.60, 纯数字→原值
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "").replace("，", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    # 中文单位解析
    multiplier = 1.0
    if s.endswith("亿"):
        multiplier = 1e8
        s = s[:-1]
    elif s.endswith("万"):
        multiplier = 1e4
        s = s[:-1]
    elif s.endswith("%"):
        return float(s[:-1]) if s[:-1].replace(".", "").replace("-", "").isdigit() else None
    try:
        return float(s) * multiplier
    except (ValueError, TypeError):
        return None


def to_akshare_code(code: str) -> str:
    """把代码转换为 akshare 同花顺接口需要的形式。

    实测结论（2026-07-31 诊断）：
      同花顺 stock_financial_abstract_ths 只接受【纯数字】，带 .SH/.SZ 后缀全部失败。
      → 直接返回 6 位纯数字。
    """
    code = code.strip().upper()
    if "." in code:
        code = code.split(".")[0]  # 去掉可能的后缀
    if code.startswith(("SH", "SZ")):
        code = code[2:]
    return code[-6:] if len(code) >= 6 else code.zfill(6)


def fetch_quarterly(code: str) -> dict:
    """akshare 拉按报告期财务数据（利润表 + 资产负债表 + 现金流量表）。

    返回 {报告期: {中文列: 值}}，按报告期升序。
    优先同花顺 stock_financial_abstract_ths，失败时用新浪源兜底；
    额外用东财 stock_balance_sheet_by_report_em / stock_cash_flow_sheet_by_report_em
    补齐资产负债表和现金流量表（修复 2026-08-01：深市 balance/cashflow 缺失）。

    2026-08-01 修复：akshare 摘要接口（THS/新浪）只返回利润表指标，
    资产负债表/现金流量表需东财接口单独拉取。这里合并三部分。
    """
    if not _HAS_AKSHARE:
        return {}
    ak_code = to_akshare_code(code)
    # 优先同花顺
    result = _fetch_ths(ak_code)
    if not result:
        result = _fetch_sina(ak_code)
    # 东财三表补齐（balance/cashflow 字段合并进同一 dict）
    result = _merge_statements(result, ak_code)
    return result


def _merge_statements(profit_data: dict, ak_code: str) -> dict:
    """合并利润表 + 资产负债表 + 现金流量表为统一 dict。

    东财接口单独调用，把 balance/cashflow/profit 明细字段 merge 进 profit_data。
    单位统一为元（与 Baostock 对齐）。
    R27：新增东财利润表明细（研发/费用/营业成本等）。
    """
    result = dict(profit_data) if isinstance(profit_data, dict) else {}
    bal = _fetch_em_balance(ak_code)
    for period, entry in bal.items():
        result.setdefault(period, {}).update(entry)
    cf = _fetch_em_cashflow(ak_code)
    for period, entry in cf.items():
        result.setdefault(period, {}).update(entry)
    # R27：东财利润表明细（补充 akshare/新浪缺失的研发/费用/成本明细）
    profit = _fetch_em_profit(ak_code)
    for period, entry in profit.items():
        # 已有字段不覆盖（profit_data 优先）
        existing = result.setdefault(period, {})
        for k, v in entry.items():
            if k not in existing:
                existing[k] = v
    return result


def _fetch_ths(code: str) -> dict:
    """同花顺源：stock_financial_abstract_ths"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            period = str(row.get("报告期", "")).strip()
            if not period or not period[:4].isdigit():
                continue
            entry = {}
            for col in [
                "营业总收入",
                "净利润",
                "销售毛利率",
                "净资产收益率",
                "基本每股收益",
                "资产负债率",
                "总资产",
                "总负债",
                "股东权益合计",
                "货币资金",
            ]:
                val = row.get(col)
                if val is not None:
                    parsed = _parse_cn_num(val)
                    if parsed is not None:
                        entry[col] = parsed
            if entry:
                result[period] = entry
        return result
    except Exception as e:
        logger.debug("akshare %s THS 失败: %s", code, e)
        return {}


# 新浪源指标名 → 我们的字段名
_SINA_MAP = {
    "营业总收入": "营业总收入",
    "净利润": "净利润",
    "销售毛利率": "销售毛利率",
    "净资产收益率": "净资产收益率",
    "基本每股收益": "基本每股收益",
    "资产负债率": "资产负债率",
    "总资产": "总资产",
    "总负债": "总负债",
    "股东权益合计": "股东权益合计",
    "货币资金": "货币资金",
}


def _fetch_sina(code: str) -> dict:
    """新浪源：stock_financial_abstract（长表格式，指标行×报告期列）"""
    try:
        df = ak.stock_financial_abstract(symbol=code)
        if df is None or df.empty:
            return {}
        # 长表：每行一个指标，列是报告期（如 20260331）
        # 找"指标"列
        if "指标" not in df.columns:
            return {}
        result = {}
        for _, row in df.iterrows():
            metric = str(row.get("指标", "")).strip()
            if metric not in _SINA_MAP:
                continue
            for col in df.columns:
                # 报告期列：8 位数字（YYYYMMDD）
                if str(col).isdigit() and len(str(col)) == 8:
                    val = row.get(col)
                    if val is not None:
                        try:
                            period = f"{str(col)[:4]}-{str(col)[4:6]}-{str(col)[6:8]}"
                            result.setdefault(period, {})[_SINA_MAP[metric]] = float(val)
                        except (ValueError, TypeError):
                            pass
        return result
    except Exception as e:
        logger.debug("akshare %s 新浪失败: %s", code, e)
        return {}


def rows_from_data(code: str, data: dict) -> list:
    """把 akshare 数据转换为 financials.db 行（含字段映射 + 单位变换）。

    返回 [(quarter, table_name, field, value), ...]
    """
    out = []
    for period, entry in data.items():
        for col, val in entry.items():
            if col in PROFIT_MAP and PROFIT_MAP[col][2] is not None:
                table, field, transform = PROFIT_MAP[col]
                out.append((period, table, field, transform(val)))
            elif col in BALANCE_MAP and BALANCE_MAP[col][2] is not None:
                table, field, transform = BALANCE_MAP[col]
                out.append((period, table, field, transform(val)))
            elif col in CASHFLOW_MAP and CASHFLOW_MAP[col][2] is not None:
                table, field, transform = CASHFLOW_MAP[col]
                out.append((period, table, field, transform(val)))
    return out


def _em_get(row, col: str):
    """从 DataFrame 行取列值，大小写不敏感匹配（东财列名大小写不定）。"""
    if col in row.index:
        return row.get(col)
    # 大小写归一化匹配
    norm = str(col).lower()
    for c in row.index:
        if str(c).lower() == norm:
            return row.get(c)
    return None


# 东财 datacenter API 常量（HTTP 直连，绕过 akshare 坏封装）
_EM_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}
# 资产负债表 reportName → 需要的字段
_EM_BALANCE_REPORT = "RPT_F10_FINANCE_GBALANCE"
_EM_CASHFLOW_REPORT = "RPT_F10_FINANCE_GCASHFLOW"


def _em_http_fetch(code: str, report_name: str, page_size: int = 30) -> list:
    """HTTP 直连东财 datacenter API，返回行列表（dict）。

    修复（2026-08-01）：akshare 的 stock_balance_sheet_by_report_em /
    stock_cash_flow_sheet_by_report_em 在用户机抛 TypeError（封装 bug），
    改用 requests 直连东财 datacenter API。
    """
    import requests as _req

    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": f'(SECURITY_CODE="{code}")',
        "pageNumber": "1",
        "pageSize": str(page_size),
        "source": "WEB",
        "client": "WEB",
    }
    try:
        resp = _req.get(_EM_API, params=params, headers=_EM_HEADERS, timeout=15)
        data = resp.json()
        return (data.get("result") or {}).get("data") or []
    except Exception as e:
        logger.debug("东财 HTTP %s %s 失败: %s", report_name, code, e)
        return []


def _fetch_em_balance(code: str) -> dict:
    """东财资产负债表（HTTP 直连 datacenter API）

    返回 {报告期: {中文列: 值}}，与 THS/新浪格式对齐。
    R27：扩展 20+ 字段（应收/存货/商誉/研发相关/借款/固定资产等）。
    """
    rows = _em_http_fetch(code, _EM_BALANCE_REPORT)
    if not rows:
        return {}
    result = {}
    # 东财字段名 → 中文列名（资产负债表）
    EM_BALANCE_FIELDS = [
        ("TOTAL_ASSETS", "总资产"),
        ("TOTAL_LIABILITIES", "总负债"),
        ("TOTAL_EQUITY", "股东权益合计"),
        ("MONETARYFUNDS", "货币资金"),
        ("ACCOUNTS_RECE", "应收账款"),  # 应收账款
        ("NOTE_RECE", "应收票据"),  # 应收票据
        ("INVENTORY", "存货"),  # 存货
        ("GOODWILL", "商誉"),  # 商誉
        ("FIXED_ASSET", "固定资产"),  # 固定资产
        ("INTANGIBLE_ASSET", "无形资产"),  # 无形资产
        ("SHORT_LOAN", "短期借款"),  # 短期借款
        ("LONG_LOAN", "长期借款"),  # 长期借款
        ("ACCOUNTS_PAYABLE", "应付账款"),  # 应付账款
        ("BOND_PAYABLE", "应付债券"),  # 应付债券（R53 新增）
        ("ADVANCE_RECE", "预收款项"),  # 预收款项
        ("TOTAL_CURRENT_LIAB", "流动负债合计"),  # 流动负债合计
        ("TOTAL_NONCURRENT_LIAB", "非流动负债合计"),
    ]
    for row in rows:
        period_raw = str(row.get("REPORT_DATE", "")).strip()
        if not period_raw:
            continue
        period = period_raw[:10] if len(period_raw) >= 10 else period_raw
        entry = {}
        for em_field, cn_col in EM_BALANCE_FIELDS:
            val = row.get(em_field)
            if val is not None:
                try:
                    entry[cn_col] = float(str(val).replace(",", ""))
                except (ValueError, TypeError):
                    pass
        if entry:
            result.setdefault(period, {}).update(entry)
    return result


def _fetch_em_cashflow(code: str) -> dict:
    """东财现金流量表（HTTP 直连 datacenter API）

    返回 {报告期: {中文列: 值}}。
    R27：扩展现金流明细（销售收现/资本开支）。
    """
    rows = _em_http_fetch(code, _EM_CASHFLOW_REPORT)
    if not rows:
        return {}
    result = {}
    # 东财字段名 → 中文列名（现金流量表）
    EM_CASHFLOW_FIELDS = [
        ("NETCASH_OPERATE", "经营活动产生的现金流量净额"),
        ("NETCASH_INVEST", "投资活动产生的现金流量净额"),
        ("NETCASH_FINANCE", "筹资活动产生的现金流量净额"),
        ("CASH_RECV_SG_RS", "销售商品、提供劳务收到的现金"),
        ("CONSTRUCT_LONG_ASSET", "购建固定资产、无形资产和其他长期资产支付的现金"),
        ("FA_IR_DEPR", "折旧摊销"),  # 折旧摊销（R53 新增，年报/中报披露）
    ]
    for row in rows:
        period_raw = str(row.get("REPORT_DATE", "")).strip()
        if not period_raw:
            continue
        period = period_raw[:10] if len(period_raw) >= 10 else period_raw
        entry = {}
        for em_field, cn_col in EM_CASHFLOW_FIELDS:
            val = row.get(em_field)
            if val is not None:
                try:
                    entry[cn_col] = float(str(val).replace(",", ""))
                except (ValueError, TypeError):
                    pass
        if entry:
            result.setdefault(period, {}).update(entry)
    return result


# R27：东财利润表 reportName
_EM_PROFIT_REPORT = "RPT_F10_FINANCE_GINCOME"


def _fetch_em_profit(code: str) -> dict:
    """东财利润表（HTTP 直连 datacenter API）

    返回 {报告期: {中文列: 值}}。R27 新增。
    """
    rows = _em_http_fetch(code, _EM_PROFIT_REPORT)
    if not rows:
        return {}
    result = {}
    # 东财字段名 → 中文列名（利润表）
    EM_PROFIT_FIELDS = [
        ("TOTAL_OPERATE_INCOME", "营业总收入"),
        ("OPERATE_INCOME", "营业收入"),
        ("TOTAL_OPERATE_COST", "营业总成本"),
        ("OPERATE_COST", "营业成本"),
        ("RESEARCH_EXPENSE", "研发费用"),  # 研发费用（R53 修复：实测字段名，原 R_D_EXPENSE 取不到值）
        ("SALE_EXPENSE", "销售费用"),
        ("MANAGE_EXPENSE", "管理费用"),
        ("FINANCE_EXPENSE", "财务费用"),
        ("OPERATE_PROFIT", "营业利润"),
        ("TOTAL_PROFIT", "利润总额"),
        ("NETPROFIT", "净利润"),
        ("INCOME_TAX", "所得税费用"),
        ("BASIC_EPS", "基本每股收益"),
        ("DEDUCT_NETPROFIT", "扣非净利润"),
    ]
    for row in rows:
        period_raw = str(row.get("REPORT_DATE", "")).strip()
        if not period_raw:
            continue
        period = period_raw[:10] if len(period_raw) >= 10 else period_raw
        entry = {}
        for em_field, cn_col in EM_PROFIT_FIELDS:
            val = row.get(em_field)
            if val is not None:
                try:
                    entry[cn_col] = float(str(val).replace(",", ""))
                except (ValueError, TypeError):
                    pass
        if entry:
            result.setdefault(period, {}).update(entry)
    return result


def save_rows(code: str, rows: list) -> int:
    """写入 SQLite（WAL 支持多进程）。返回写入条数。"""
    if not rows:
        return 0
    conn = _connect()
    conn.execute("PRAGMA journal_mode=WAL")
    count = 0
    for quarter, table, field, value in rows:
        conn.execute(
            "INSERT OR REPLACE INTO financials (code, quarter, table_name, field, value, source) "
            "VALUES (?,?,?,?,?, 'akshare')",
            (code, quarter, table, field, value),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def _existing_fields_by_table(code: str) -> dict:
    """返回每张表每个季度已有的字段集合 {table: {quarter: set(fields)}}"""
    out = {"profit": {}, "balance": {}, "cashflow": {}}
    try:
        import sqlite3 as _sql

        conn = _sql.connect(str(DB_PATH))
        rows = conn.execute("SELECT table_name, quarter, field FROM financials WHERE code=?", (code,)).fetchall()
        conn.close()
        for t, q, f in rows:
            if t in out:
                out[t].setdefault(q, set()).add(f)
    except Exception:
        pass
    return out


def sync_code(code: str, dry_run: bool = False) -> dict:
    """同步单只股票：只补库内缺失季度+字段。返回 {code, added, new_quarters}

    修复（2026-08-01 审计）：按表+字段独立判断缺失，避免 profit 的 epsTTM
    掩盖 MBRevenue/netProfit 缺口，以及 profit 最新季度掩盖 balance/cashflow 缺口。
    """
    code_clean = code[-6:] if len(code) >= 6 else code
    existing_by_table = _latest_quarters_by_table(code_clean)
    existing_fields = _existing_fields_by_table(code_clean)
    data = fetch_quarterly(code_clean)
    if not data:
        return {"code": code_clean, "added": 0, "new_quarters": []}

    # 两级判断：季度缺失 OR 字段缺失
    missing_periods = set()
    for period in data:
        tables_for_period = set()
        for col in data[period]:
            if col in PROFIT_MAP:
                tables_for_period.add("profit")
            if col in BALANCE_MAP:
                tables_for_period.add("balance")
            if col in CASHFLOW_MAP:
                tables_for_period.add("cashflow")
        for tbl in tables_for_period:
            # 季度缺失：整个季度都没有该表数据
            if period not in existing_by_table.get(tbl, set()):
                missing_periods.add(period)
                continue
            # 字段缺失：季度有但缺特定字段（如 profit 有 epsTTM 但缺 MBRevenue）
            for col in data[period]:
                if col in PROFIT_MAP and PROFIT_MAP[col][0] == tbl:
                    field = PROFIT_MAP[col][1]
                    if field not in existing_fields.get(tbl, {}).get(period, set()):
                        missing_periods.add(period)
                elif col in BALANCE_MAP and BALANCE_MAP[col][0] == tbl:
                    field = BALANCE_MAP[col][1]
                    if field not in existing_fields.get(tbl, {}).get(period, set()):
                        missing_periods.add(period)
                elif col in CASHFLOW_MAP and CASHFLOW_MAP[col][0] == tbl:
                    field = CASHFLOW_MAP[col][1]
                    if field not in existing_fields.get(tbl, {}).get(period, set()):
                        missing_periods.add(period)

    if not missing_periods:
        return {"code": code_clean, "added": 0, "new_quarters": []}

    filtered = {q: data[q] for q in sorted(missing_periods)}
    rows = rows_from_data(code_clean, filtered)
    if dry_run:
        return {"code": code_clean, "added": len(rows), "new_quarters": sorted(missing_periods)}
    n = save_rows(code_clean, rows)
    return {"code": code_clean, "added": n, "new_quarters": sorted(missing_periods)}


def _worker_init():
    pass  # akshare 无全局 socket 依赖，无需初始化


def _worker_sync(args: tuple) -> dict:
    """akshare 拉取 worker，带失败重试（应对源限流/瞬断）。"""
    code, dry_run = args
    max_retries = 3
    last_err = ""
    for attempt in range(max_retries):
        try:
            r = sync_code(code, dry_run)
            if r.get("error"):
                last_err = r["error"]
                continue
            return r
        except Exception as e:
            last_err = str(e)[:200]
            if attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))  # 退避重试
    return {"code": code, "added": 0, "new_quarters": [], "error": last_err}


def get_index_constituents(index_code: str = "000300") -> list[str]:
    """获取指数成分股代码列表（沪深300/中证1000等）。

    R27（2026-08-02 全量明细）：用中证指数官方接口。
      - 000300 = 沪深300
      - 000852 = 中证1000
    返回纯 6 位代码列表；失败时返回空。
    """
    try:
        import akshare as ak

        df = ak.index_stock_cons_csindex(symbol=index_code)
        if df is not None and not df.empty:
            return [str(c).zfill(6) for c in df["成分券代码"].tolist()]
    except Exception as e:
        logger.warning("获取 %s 成分股失败: %s", index_code, e)
    return []


def read_instruments() -> list[str]:
    """复用 sync_financials 的过滤逻辑（指数/北交所/退市股）"""
    if not INSTRUMENTS.exists():
        return []
    result = []
    for line in INSTRUMENTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0]
        if code.startswith("BJ") or code.startswith("SH000") or code.startswith("SZ399"):
            continue
        # 退市股默认跳过
        if len(parts) >= 3 and parts[2][:4].isdigit() and parts[2][:4] < "2025":
            continue
        result.append(code)
    return result


def main():
    parser = argparse.ArgumentParser(description="财务层查漏补缺（akshare → SQLite），配合 Baostock 历史层")
    parser.add_argument("asset", nargs="?", help="股票代码，如 600519")
    parser.add_argument("--all", action="store_true", help="全量同步所有过滤后标的")
    parser.add_argument("--batch", type=int, metavar="N", help="批量同步前 N 只")
    parser.add_argument(
        "--market", choices=["sh", "sz", "all"], default="all", help="只同步某市场（sz=深市 000/002/300/301，sh=沪市）"
    )
    parser.add_argument("--code-prefix", default=None, help="只同步指定代码前缀（如 300/301=创业板，002=中小板）")
    parser.add_argument("--workers", type=int, default=2, help="并发数（akshare 源有限流，建议 2-4）")
    parser.add_argument(
        "--index", default=None, help="按指数成分同步：000300=沪深300, 000852=中证1000（可逗号分隔多指数）"
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览要补什么，不写入")
    parser.add_argument("--status", action="store_true", help="查看库状态")
    args = parser.parse_args()

    if args.status:
        conn = sqlite3.connect(str(DB_PATH))
        n_codes = conn.execute("SELECT COUNT(DISTINCT code) FROM financials").fetchone()[0]
        n_rows = conn.execute("SELECT COUNT(*) FROM financials").fetchone()[0]
        latest = conn.execute("SELECT MAX(quarter) FROM financials").fetchone()[0]
        src = conn.execute("SELECT source, COUNT(*) FROM financials GROUP BY source").fetchall()
        conn.close()
        print(f"财务库: {n_codes} 只, {n_rows} 条, 最新季度 {latest}")
        print(f"来源分布: {dict(src)}")
        return 0

    if not _HAS_AKSHARE:
        print("[!!] akshare 未安装，请先 pip install akshare")
        return 1

    targets = []
    all_instruments = read_instruments()

    # 按指数成分过滤（沪深300/中证1000）——R27 全量明细
    index_codes = set()
    if args.index:
        for idx in args.index.split(","):
            idx = idx.strip()
            if idx in ("000300", "000852", "000905"):
                members = get_index_constituents(idx)
                index_codes.update(members)
                logger.info("指数 %s 成分股: %d 只", idx, len(members))
        if index_codes:
            # 保留指数成分（不应用市场/前缀过滤，指数已限定范围）
            all_instruments = [t for t in all_instruments if t[2:].zfill(6) in index_codes]
            logger.info("指数成分过滤: %d 只", len(all_instruments))

    # 按市场过滤
    if args.market == "sh":
        all_instruments = [t for t in all_instruments if t.startswith("SH")]
    elif args.market == "sz":
        all_instruments = [t for t in all_instruments if t.startswith("SZ")]
    logger.info("市场过滤 %s: %d 只", args.market, len(all_instruments))

    # 按代码前缀过滤（如 300=创业板，代码格式 SZ300750）
    if args.code_prefix:
        # 代码格式是 SZ300750 / SH600000，前缀匹配代码的数字部分开头
        prefixes = tuple(p.strip() for p in args.code_prefix.split(",") if p.strip())
        all_instruments = [t for t in all_instruments if any(t[2:].startswith(p) for p in prefixes)]
        logger.info("代码前缀过滤 %s: %d 只", args.code_prefix, len(all_instruments))

    if args.all:
        targets = all_instruments
        logger.info("全量模式：%d 只（已过滤指数/北交所/退市）", len(targets))
    elif args.batch:
        targets = all_instruments[: args.batch]
    elif args.asset:
        targets = [args.asset]
    else:
        parser.print_help()
        return 1

    print(f"[SYNC] {len(targets)} 只 {'预览' if args.dry_run else '同步'}（akshare 查漏补缺, workers={args.workers}）")
    total_added = 0
    total_fixed = 0
    total_failed = 0

    # 分批提交 + 逐 future 异常隔离（2026-08-01 修复 BrokenProcessPool）
    # 原实现一次性 submit 全部 5254 个任务 → 任务队列 + worker 并发拉 akshare
    # 把主进程/子进程内存打爆，或 akshare 原生库段错误 → 池 broken。
    # 现在：每批只提交 BATCH=200 个，future.result() 包 try/except，
    # 单个 worker 崩溃只影响该批，下一批重新建池续跑。
    try:
        BATCH = int(os.environ.get("SYNC_BATCH", "200"))
    except Exception:
        BATCH = 200

    done = 0
    for start in range(0, len(targets), BATCH):
        batch = targets[start : start + BATCH]
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
            futures = {pool.submit(_worker_sync, (t, args.dry_run)): t for t in batch}
            for fut in as_completed(futures):
                code = futures[fut]
                try:
                    r = fut.result(timeout=60)
                except concurrent_futures_timeout:
                    total_failed += 1
                    logger.warning("%s 超时跳过", code)
                    continue
                except Exception as e:
                    # 单个 worker 崩溃：记失败，继续下一批（不再让整个池 broken）
                    total_failed += 1
                    logger.warning("%s worker 异常: %s", code, str(e)[:100])
                    continue
                if r is None:
                    total_failed += 1
                    continue
                if r.get("error"):
                    total_failed += 1
                    logger.warning("%s 失败: %s", r["code"], r["error"])
                    continue
                if r["added"]:
                    total_added += r["added"]
                    total_fixed += 1
                    logger.info(
                        "[补] %s: +%d 条 %s%s",
                        r["code"],
                        r["added"],
                        r["new_quarters"],
                        " (预览)" if args.dry_run else "",
                    )
                else:
                    logger.debug("%s 无缺失", r["code"])
        done += len(batch)
        logger.info("[进度] %d/%d 只（累计 +%d 条, 失败 %d）", done, len(targets), total_added, total_failed)
        # 批间喘息，降低对 akshare 源的瞬时压力
        time.sleep(0.5)

    print(
        f"\n[完成] {total_fixed} 只补数据，共 +{total_added} 条，失败 {total_failed}"
        f"{'（预览，未写入）' if args.dry_run else ''}"
    )
    if total_failed:
        print("提示：失败标的可用 --batch 或单只代码重跑（akshare 源限流属预期）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
