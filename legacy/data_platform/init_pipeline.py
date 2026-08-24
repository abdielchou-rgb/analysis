"""init_pipeline.py — 数据管道初始化脚本

运行一次即可完成：
1. 注册所有数据源到AcquisitionOrchestrator
2. 初始化DuckDB财务数据库
3. 发现并注册全球数据源
4. 打印健康报告

用法:
    python data/init_pipeline.py
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("v57.init_pipeline")


def step1_register_existing_sources():
    """注册现有数据源到采集框架"""
    logger.info("[1/5] 注册现有数据源...")
    try:
        from legacy.data_platform.acquisition.framework import registry, DataSource, DataSourceResult

        # EastMoney
        class EastMoneySource(DataSource):
            name = "eastmoney"
            priority = 1

            def _do_fetch(self, params):
                try:
                    from legacy.data_platform.__init__ import fetch_realtime

                    codes = params.get("codes", ["600519"])
                    points = fetch_realtime(codes)
                    return DataSourceResult(success=True, data=points, source="eastmoney", confidence="high")
                except Exception as e:
                    return DataSourceResult(success=False, source="eastmoney", error=str(e))

        # Consensus Crawler
        class ConsensusSource(DataSource):
            name = "consensus"
            priority = 2

            def _do_fetch(self, params):
                try:
                    from legacy.data_platform.consensus_crawler import ConsensusCrawler

                    code = params.get("code", "600519")
                    cc = ConsensusCrawler()
                    points = cc.fetch(code)
                    return DataSourceResult(
                        success=len(points) > 0, data=points, source="consensus", confidence="medium"
                    )
                except Exception as e:
                    return DataSourceResult(success=False, source="consensus", error=str(e))

        # Consensus Connector (akshare fallback)
        class ConsensusConnectorSource(DataSource):
            name = "consensus_connector"
            priority = 3

            def _do_fetch(self, params):
                try:
                    from legacy.data_platform.consensus_connector import fetch_consensus

                    code = params.get("code", "600519")
                    points = fetch_consensus(code)
                    return DataSourceResult(
                        success=len(points) > 0, data=points, source="consensus_connector", confidence="medium"
                    )
                except Exception as e:
                    return DataSourceResult(success=False, source="consensus_connector", error=str(e))

        # Policy Crawler
        class PolicySource(DataSource):
            name = "policy"
            priority = 5

            def _do_fetch(self, params):
                try:
                    from legacy.data_platform.__init__ import fetch_policy

                    industry = params.get("industry", "新能源")
                    points = fetch_policy(industry, 90)
                    return DataSourceResult(success=len(points) > 0, data=points, source="policy", confidence="medium")
                except Exception as e:
                    return DataSourceResult(success=False, source="policy", error=str(e))

        # Macro
        class MacroSource(DataSource):
            name = "macro"
            priority = 4

            def _do_fetch(self, params):
                try:
                    from legacy.data_platform.__init__ import fetch_macro

                    points = fetch_macro("all")
                    return DataSourceResult(success=len(points) > 0, data=points, source="macro", confidence="high")
                except Exception as e:
                    return DataSourceResult(success=False, source="macro", error=str(e))

        # Industry Crawlers
        class IndustrySource(DataSource):
            name = "industry"
            priority = 6

            def _do_fetch(self, params):
                try:
                    from legacy.data_platform.industry_crawlers import fetch_industry_data

                    industry = params.get("industry", "光伏")
                    points = fetch_industry_data(industry)
                    return DataSourceResult(
                        success=len(points) > 0, data=points, source="industry", confidence="medium"
                    )
                except Exception as e:
                    return DataSourceResult(success=False, source="industry", error=str(e))

        # akshare deep
        class AkshareDeepSource(DataSource):
            name = "akshare_deep"
            priority = 7

            def _do_fetch(self, params):
                try:
                    from legacy.data_platform.akshare_deep import akshare_deep

                    method = params.get("method", "capital_flow")
                    code = params.get("code", "600519")
                    if method == "capital_flow":
                        points = akshare_deep.get_capital_flow(code)
                    elif method == "northbound":
                        points = akshare_deep.get_northbound_flow()
                    elif method == "margin":
                        points = akshare_deep.get_margin(code)
                    elif method == "industry_board":
                        points = akshare_deep.get_industry_board(params.get("industry", "光伏"))
                    else:
                        points = []
                    return DataSourceResult(
                        success=len(points) > 0, data=points, source="akshare_deep", confidence="high"
                    )
                except Exception as e:
                    return DataSourceResult(success=False, source="akshare_deep", error=str(e))

        # Register all
        for src in [
            EastMoneySource(),
            ConsensusSource(),
            ConsensusConnectorSource(),
            PolicySource(),
            MacroSource(),
            IndustrySource(),
            AkshareDeepSource(),
        ]:
            registry.register(src)

        logger.info("  Registered %d sources", len(registry.list_sources()))
        return registry
    except Exception as e:
        logger.error("Source registration failed: %s", e)
        return None


def step2_init_financial_db():
    """初始化DuckDB财务数据库"""
    logger.info("[2/5] 初始化财务数据库...")
    try:
        from legacy.data_platform.financial_db import financial_db

        if financial_db._available:
            stats = financial_db.get_coverage_stats()
            logger.info("  FinancialDB active: %s", stats)
        else:
            logger.info("  FinancialDB not available (install duckdb)")
        return financial_db
    except Exception as e:
        logger.error("FinancialDB init failed: %s", e)
        return None


def step3_register_global_sources():
    """注册全球数据源"""
    logger.info("[3/5] 注册全球数据源...")
    try:
        from legacy.data_platform.global_sources import register_global_sources

        register_global_sources()
        logger.info("  Global sources registered")
    except Exception as e:
        logger.debug("Global source registration: %s", e)


def step4_verify_cache():
    """验证缓存系统"""
    logger.info("[4/5] 验证缓存系统...")
    try:
        from legacy.data_platform.cache_manager import persistent_cache

        stats = persistent_cache.stats()
        logger.info("  Cache: %d entries (%d active)", stats.get("total_entries", 0), stats.get("active_entries", 0))
    except Exception as e:
        logger.debug("Cache verification: %s", e)


def step5_print_health_report():
    """打印健康报告"""
    logger.info("[5/5] 数据管道健康报告...")
    print()
    print("=" * 60)
    print("  1号分析师 数据管道初始化报告")
    print("=" * 60)

    try:
        from legacy.data_platform.acquisition.framework import registry

        sources = registry.list_sources()
        print(f"  注册数据源: {len(sources)}")
        for s in sorted(sources):
            print(f"    - {s}")
    except Exception as e:
        print(f"  Source listing failed: {e}")

    try:
        from legacy.data_platform.financial_db import financial_db

        if financial_db._available:
            print(f"  财务数据库: DuckDB (active)")
        else:
            print(f"  财务数据库: DuckDB (pip install duckdb)")
    except Exception:
        print(f"  财务数据库: 未初始化")

    try:
        from legacy.data_platform.cache_manager import persistent_cache

        cs = persistent_cache.stats()
        print(f"  缓存: {cs.get('active_entries', 0)} active / {cs.get('total_entries', 0)} total")
    except Exception:
        print(f"  缓存: 不可用")

    try:
        import importlib

        checks = [
            ("akshare", "akshare"),
            ("crawl4ai", "crawl4ai"),
            ("duckdb", "duckdb"),
            ("apscheduler", "apscheduler"),
            ("yfinance", "yfinance"),
            ("requests", "requests"),
            ("jieba", "jieba"),
            ("matplotlib", "matplotlib"),
        ]
        print()
        print("  依赖检查:")
        for name, module in checks:
            try:
                importlib.import_module(module)
                print(f"    ✅ {name}")
            except ImportError:
                print(f"    ❌ {name} (pip install)")
    except Exception:
        pass

    print()
    print("=" * 60)
    print("  init_pipeline.py 完成")
    print("  下一步: python scheduler.py --daemon  (启动定时采集)")
    print("         python scheduler.py --once    (立即采集一次)")
    print("         python data/pipe_dashboard.py  (查看仪表盘)")
    print("=" * 60)


def main():
    logger.info("=" * 50)
    logger.info("  V57 数据管道初始化")
    logger.info("=" * 50)

    step1_register_existing_sources()
    step2_init_financial_db()
    step3_register_global_sources()
    step4_verify_cache()
    step5_print_health_report()


if __name__ == "__main__":
    main()
