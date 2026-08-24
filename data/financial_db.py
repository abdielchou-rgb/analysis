"""financial_db.py — 结构化财务数据库（DuckDB）

从akshare/Wind等源采集财务数据，存入本地DuckDB。
支持时间序列查询、跨公司对比、历史回补。

用法:
    from data.financial_db import FinancialDB
    db = FinancialDB()
    
    # 写入
    db.store_financials("600519", "income", {"revenue": 1500}, fiscal_year=2024)
    
    # 查询
    df = db.query_financials("600519", statement="income", years=5)
    
    # 跨公司对比
    peers = db.query_peers(["600519", "000858", "600809"], metric="revenue")
"""

from __future__ import annotations
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("v57.data.financial_db")

_HAS_DUCKDB = False
try:
    import duckdb
    _HAS_DUCKDB = True
except ImportError:
    logger.warning("duckdb not installed, FinancialDB unavailable")


class FinancialDB:
    """结构化财务数据库

    使用DuckDB存储财务数据，支持：
    - 三张财务报表（利润表/资产负债表/现金流量表）
    - 财务比率表（ROE/ROIC/毛利率等）
    - 时间序列查询
    - 跨公司对比
    """

    def __init__(self, db_path: str | None = None):
        if not _HAS_DUCKDB:
            self._available = False
            return
        self._available = True
        
        if db_path is None:
            root = Path(__file__).resolve().parent.parent
            db_path = str(root / "data" / "financial_db.duckdb")
        
        self.db_path = db_path
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
            self._init_schema()
        return self._conn

    def _init_schema(self):
        """初始化表结构"""
        conn = self.conn
        
        # 利润表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS income_statements (
                asset_code VARCHAR NOT NULL,
                fiscal_year INTEGER NOT NULL,
                fiscal_period VARCHAR DEFAULT 'FY',
                revenue DOUBLE,
                cost_of_revenue DOUBLE,
                gross_profit DOUBLE,
                operating_expense DOUBLE,
                operating_income DOUBLE,
                net_income DOUBLE,
                eps DOUBLE,
                currency VARCHAR DEFAULT 'CNY',
                source VARCHAR DEFAULT 'akshare',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (asset_code, fiscal_year, fiscal_period)
            )
        """)
        
        # 资产负债表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS balance_sheets (
                asset_code VARCHAR NOT NULL,
                fiscal_year INTEGER NOT NULL,
                fiscal_period VARCHAR DEFAULT 'FY',
                total_assets DOUBLE,
                total_liabilities DOUBLE,
                total_equity DOUBLE,
                cash DOUBLE,
                accounts_receivable DOUBLE,
                inventory DOUBLE,
                goodwill DOUBLE,
                currency VARCHAR DEFAULT 'CNY',
                source VARCHAR DEFAULT 'akshare',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (asset_code, fiscal_year, fiscal_period)
            )
        """)
        
        # 现金流量表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cash_flows (
                asset_code VARCHAR NOT NULL,
                fiscal_year INTEGER NOT NULL,
                fiscal_period VARCHAR DEFAULT 'FY',
                operating_cash_flow DOUBLE,
                investing_cash_flow DOUBLE,
                financing_cash_flow DOUBLE,
                capex DOUBLE,
                free_cash_flow DOUBLE,
                currency VARCHAR DEFAULT 'CNY',
                source VARCHAR DEFAULT 'akshare',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (asset_code, fiscal_year, fiscal_period)
            )
        """)
        
        # 财务比率
        conn.execute("""
            CREATE TABLE IF NOT EXISTS financial_ratios (
                asset_code VARCHAR NOT NULL,
                fiscal_year INTEGER NOT NULL,
                fiscal_period VARCHAR DEFAULT 'FY',
                roe DOUBLE,
                roic DOUBLE,
                gross_margin DOUBLE,
                net_margin DOUBLE,
                current_ratio DOUBLE,
                debt_to_equity DOUBLE,
                asset_turnover DOUBLE,
                revenue_growth DOUBLE,
                net_income_growth DOUBLE,
                source VARCHAR DEFAULT 'computed',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (asset_code, fiscal_year, fiscal_period)
            )
        """)
        
        # 一致预期
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consensus_estimates (
                asset_code VARCHAR NOT NULL,
                fiscal_year INTEGER NOT NULL,
                consensus_revenue DOUBLE,
                consensus_net_income DOUBLE,
                consensus_eps DOUBLE,
                analyst_buy_count INTEGER DEFAULT 0,
                analyst_hold_count INTEGER DEFAULT 0,
                analyst_sell_count INTEGER DEFAULT 0,
                target_price_avg DOUBLE,
                source VARCHAR DEFAULT 'consensus_crawler',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (asset_code, fiscal_year)
            )
        """)

        conn.commit()

    def store_income_statement(self, asset_code: str, fiscal_year: int,
                                data: dict, period: str = "FY"):
        """存储利润表"""
        if not self._available:
            return
        self.conn.execute("""
            INSERT OR REPLACE INTO income_statements
            (asset_code, fiscal_year, fiscal_period, revenue, cost_of_revenue,
             gross_profit, operating_expense, operating_income, net_income,
             eps, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            asset_code, fiscal_year, period,
            data.get("revenue"), data.get("cost_of_revenue"),
            data.get("gross_profit"), data.get("operating_expense"),
            data.get("operating_income"), data.get("net_income"),
            data.get("eps"), data.get("source", "akshare"),
        ))

    def store_balance_sheet(self, asset_code: str, fiscal_year: int,
                             data: dict, period: str = "FY"):
        """存储资产负债表"""
        if not self._available:
            return
        self.conn.execute("""
            INSERT OR REPLACE INTO balance_sheets
            (asset_code, fiscal_year, fiscal_period, total_assets, total_liabilities,
             total_equity, cash, accounts_receivable, inventory, goodwill,
             source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            asset_code, fiscal_year, period,
            data.get("total_assets"), data.get("total_liabilities"),
            data.get("total_equity"), data.get("cash"),
            data.get("accounts_receivable"), data.get("inventory"),
            data.get("goodwill"), data.get("source", "akshare"),
        ))

    def store_cash_flow(self, asset_code: str, fiscal_year: int,
                         data: dict, period: str = "FY"):
        """存储现金流量表"""
        if not self._available:
            return
        ocf = data.get("operating_cash_flow", 0)
        icf = data.get("investing_cash_flow", 0)
        fcf = data.get("financing_cash_flow", 0)
        capex = data.get("capex", abs(icf) if icf < 0 else 0)
        
        self.conn.execute("""
            INSERT OR REPLACE INTO cash_flows
            (asset_code, fiscal_year, fiscal_period, operating_cash_flow,
             investing_cash_flow, financing_cash_flow, capex, free_cash_flow,
             source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            asset_code, fiscal_year, period,
            ocf, icf, fcf, capex,
            ocf - capex,
            data.get("source", "akshare"),
        ))

    def store_consensus(self, asset_code: str, fiscal_year: int,
                         data: dict):
        """存储一致预期"""
        if not self._available:
            return
        self.conn.execute("""
            INSERT OR REPLACE INTO consensus_estimates
            (asset_code, fiscal_year, consensus_revenue, consensus_net_income,
             consensus_eps, analyst_buy_count, analyst_hold_count,
             analyst_sell_count, target_price_avg, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            asset_code, fiscal_year,
            data.get("consensus_revenue"), data.get("consensus_net_income"),
            data.get("consensus_eps"),
            data.get("analyst_buy", 0), data.get("analyst_hold", 0),
            data.get("analyst_sell", 0), data.get("target_price_avg"),
            data.get("source", "consensus_crawler"),
        ))

    def query_financials(self, asset_code: str, statement: str = "income",
                          years: int = 5) -> list[dict]:
        """查询历史财务数据"""
        if not self._available:
            return []
        
        table_map = {
            "income": "income_statements",
            "balance": "balance_sheets",
            "cash_flow": "cash_flows",
            "ratios": "financial_ratios",
            "consensus": "consensus_estimates",
        }
        table = table_map.get(statement, "income_statements")
        
        result = self.conn.execute(f"""
            SELECT * FROM {table}
            WHERE asset_code = ?
            ORDER BY fiscal_year DESC
            LIMIT ?
        """, (asset_code, years))
        
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    def query_peers(self, peer_codes: list[str], metric: str = "revenue",
                     year: int = 2024) -> list[dict]:
        """跨公司对比"""
        if not self._available:
            return []
        
        placeholders = ",".join("?" for _ in peer_codes)
        result = self.conn.execute(f"""
            SELECT asset_code, fiscal_year, {metric}
            FROM income_statements
            WHERE asset_code IN ({placeholders})
            AND fiscal_year = ?
            ORDER BY {metric} DESC
        """, [*peer_codes, year])
        
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    def get_all_tickers(self) -> list[str]:
        """获取数据库中所有股票代码"""
        if not self._available:
            return []
        result = self.conn.execute("""
            SELECT DISTINCT asset_code FROM income_statements
        """)
        return [row[0] for row in result.fetchall()]

    def get_coverage_stats(self) -> dict:
        """覆盖统计"""
        if not self._available:
            return {"error": "duckdb not installed"}
        stats = {}
        for name in ["income_statements", "balance_sheets", "cash_flows", "consensus_estimates"]:
            result = self.conn.execute(f"SELECT COUNT(*) as c FROM {name}").fetchone()
            stats[name] = result[0]
        return stats


    def backfill(self, asset_code: str, years: int = 5) -> dict:
        """从akshare回补历史财务数据
        
        Args:
            asset_code: 股票代码
            years: 回补年份数
            
        Returns:
            {'income': N, 'ratios': N} 写入的行数
        """
        if not self._available:
            return {'error': 'DuckDB not available'}
        try:
            import akshare as ak
        except ImportError:
            return {'error': 'akshare not installed'}
        
        results = {}
        current_year = 2026
        
        try:
            for yr in range(current_year - years, current_year + 1):
                try:
                    # 利润表
                    df = ak.stock_financial_abstract_em(symbol=asset_code)
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            rep_year = row.get('公告日期', '')
                            if str(yr) in str(rep_year):
                                self.store_income_statement(asset_code, yr, {
                                    'revenue': float(row.get('营业收入', 0) or 0),
                                    'net_income': float(row.get('净利润', 0) or 0),
                                    'source': 'akshare/backfill',
                                })
                                self.store_balance_sheet(asset_code, yr, {
                                    'total_assets': float(row.get('总资产', 0) or 0),
                                    'total_equity': float(row.get('净资产', 0) or 0),
                                    'source': 'akshare/backfill',
                                })
                                results['income'] = results.get('income', 0) + 1
                except Exception:
                    pass
            logger.info('Backfill %s: %d years', asset_code, results.get('income', 0))
        except Exception as e:
            logger.error('Backfill failed for %s: %s', asset_code, e)
        
        return results

    def backfill_watchlist(self, watchlist: list[str] = None, years: int = 5) -> dict:
        """批量回补多只股票
        
        Args:
            watchlist: 股票代码列表，默认使用WATCHLIST
            
        Returns:
            {asset_code: backfill_result}
        """
        if watchlist is None:
            watchlist = ['600519', '300750', '000858', '002594', '688981',
                         '601012', '002415', '603259', '000333', '600036',
                         '601318', '600276', '002475', '300124', '002371']
        
        results = {}
        for code in watchlist:
            try:
                result = self.backfill(code, years)
                results[code] = result
                logger.info('Backfill %s: %s', code, result)
            except Exception as e:
                logger.error('Backfill %s failed: %s', code, e)
                results[code] = {'error': str(e)}
        
        return results

    def to_postgresql(self, pg_url: str = '') -> bool:
        """迁移数据到PostgreSQL（可选）
        
        Args:
            pg_url: PostgreSQL连接URL。空则检测环境变量DATABASE_URL
            
        Returns:
            是否成功
        """
        if not pg_url:
            import os
            pg_url = os.environ.get('DATABASE_URL', '')
        if not pg_url:
            logger.warning('No PostgreSQL URL provided')
            return False
        
        try:
            import duckdb
            # DuckDB直接支持PostgreSQL ATTACH
            self.conn.execute(f"""
                ATTACH '{pg_url}' AS pg_db (TYPE POSTGRES)
            """)
            
            # 迁移每个表
            for table in ['income_statements', 'balance_sheets', 'cash_flows',
                          'financial_ratios', 'consensus_estimates']:
                self.conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS pg_db.public.{table} AS
                    SELECT * FROM {table}
                """)
                count = self.conn.execute(f"""SELECT COUNT(*) as c FROM pg_db.public.{table}""").fetchone()[0]
                logger.info('Migrated %s: %d rows', table, count)
            
            return True
        except Exception as e:
            logger.error('PostgreSQL migration failed: %s', e)
            return False

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


financial_db = FinancialDB()
