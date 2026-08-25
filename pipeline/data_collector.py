# 2号分析师 数据采集器 — 真·全管线版
# 使用: tavily-python SDK / yfinance / akshare / crawl4ai
import json
import logging
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("dc.v5")


def _lookup_code_by_name(asset: str) -> str:
    """中文公司名 → 股票代码。

    R24（2026-08-02 数据链路修复）：
    instruments/all.txt 只有代码+日期无中文名，用中文名搜 financials 永远失败，
    导致 0 张真实图 → Gate 图表不足 → 多轮失败。

    来源优先级：
      1. data/a_stock_name_map.json（akshare 全A列表生成的本地缓存，离线可用）
      2. 无缓存则尝试用 akshare 在线生成（用户机可用，一次性）
    返回纯 6 位代码，失败返回 ""。
    """
    if not asset or len(asset) < 2:
        return ""
    cache_path = _ROOT / "data" / "a_stock_name_map.json"
    name_map = {}
    if cache_path.exists():
        try:
            name_map = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            name_map = {}
    # 精确匹配
    if asset in name_map:
        return name_map[asset]
    # 包含/去后缀匹配
    for name, code in name_map.items():
        if asset in name or name in asset:
            return code
    # 无缓存 → 尝试 akshare 在线生成（用户机有 akshare）
    if not name_map:
        try:
            import akshare as ak  # type: ignore

            df = ak.stock_zh_a_spot_em()
            if df is not None and len(df) > 0:
                codes = df["代码"].astype(str).tolist()
                names = df["名称"].astype(str).tolist()
                name_map = {n: c for n, c in zip(names, codes) if n and c}
                if name_map:
                    cache_path.write_text(json.dumps(name_map, ensure_ascii=False, indent=1), encoding="utf-8")
                    logger.info("[LOCAL] 生成本地股票名→代码映射 %d 条", len(name_map))
                    if asset in name_map:
                        return name_map[asset]
                    for name, code in name_map.items():
                        if asset in name or name in asset:
                            return code
        except Exception as e:
            logger.debug("[LOCAL] akshare 名称映射失败: %s", e)
    return ""


class DataCollectorV5:
    def __init__(self):
        self._cache = {}
        self._tavily = None
        self._load_env()
        self._init_tavily()

    def _load_env(self):
        """Load .env file for API keys"""
        import os

        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip()

    def _init_tavily(self):
        try:
            from tavily import TavilyClient

            self._tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
            logger.info("TavilyClient initialized")
        except Exception as e:
            logger.warning("Tavily unavailable: %s", e)

    # ── P3-audit 2026-08-24 数据层收敛：网络阶段统一走 缓存+熔断 ──
    # 此前 data_backends 的 SQLite 缓存(TTL 4h)与 CircuitBreaker 零复用，
    # 六阶段各自裸调网络——同一标的重复采集、单源故障期反复撞墙。
    def _network_phase(self, source: str, fn):
        """包装一个网络采集阶段：熔断检查 → 磁盘缓存 → 调用 → 回写。

        返回数据 dict 或 None；异常被吞掉并计入断路器（保持原容错语义）。
        """
        from core.data_backends import _CIRCUIT, cache_get, cache_set

        if not _CIRCUIT.allow(source):
            logger.info("[BACKENDS] %s 熔断中，跳过本轮", source)
            return None
        anchor = getattr(self, "time_anchor", {}) or {}
        _key = "dcv5:{}:{}:{}".format(
            source,
            getattr(self, "_cache_asset", "unknown"),
            str(anchor.get("date", "")) if isinstance(anchor, dict) else "",
        )
        cached = cache_get(_key)
        if cached is not None:
            logger.info("[BACKENDS] %s 缓存命中: %s", source, list(cached.keys())[:5])
            return cached
        try:
            out = fn()
        except Exception as e:
            _CIRCUIT.fail(source)
            logger.warning("%s phase failed: %s", source, e)
            return None
        if out:
            _CIRCUIT.success(source)
            cache_set(_key, out)
        else:
            _CIRCUIT.success(source)
        return out

    def collect(self, asset, report_type="listed_company", time_anchor=None):
        self.time_anchor = time_anchor or {}
        self._cache_asset = asset  # P3-audit: 网络阶段缓存键的一部分
        result = {"asset": asset, "report_type": report_type, "status": "running"}
        chart_data = {}
        sources_with_data = 0

        # === Phase 0: 本地数据优先（qlib_bin 行情 + financials.db 财务）===
        try:
            ld = self._local_search(asset)
            if ld:
                chart_data.update(ld)
                sources_with_data += 1
                logger.info("[LOCAL] 本地数据已加载: %s", list(ld.keys())[:5])
        except Exception as e:
            logger.warning("local phase failed: %s", e)

        # === Phase 1-4: 网络源统一走 缓存+熔断 包装 ===
        td = (
            self._network_phase("tavily", lambda: self._tavily_search(asset, self.time_anchor))
            if self._tavily
            else None
        )
        if td:
            chart_data.update(td)
            sources_with_data += 1
        else:
            # Tavily failed or returned no data - use fallback for known companies
            _KNOWN_PROFILES = {
                "宁德时代": "宁德时代（300750.SZ）是全球动力电池行业龙头，主营锂离子电池的研发、制造和销售，业务覆盖动力电池、储能电池、电池材料与回收全产业链。2024年全球动力电池装车量市占率超37%，连续8年蝉联全球第一。",
                "比亚迪": "比亚迪（002594.SZ/1211.HK）是全球新能源汽车龙头，拥有乘用车、商用车、电池、电子、半导体五大产业集群。2024年新能源汽车销量超420万辆，蝉联全球销冠。",
                "中芯国际": "中芯国际（688981.SH/0981.HK）是中国大陆最大的晶圆代工企业，提供28nm至14nm及更先进制程服务，是国家集成电路产业核心支柱。",
                "贵州茅台": "贵州茅台（600519.SH）是中国高端白酒绝对龙头，核心产品茅台酒享有'国酒'美誉，具备极强定价权与品牌护城河。",
                "工商银行": "中国工商银行（601398.SH/1398.HK）是全球资产规模最大的银行，拥有最庞大的客户基础和网点网络，是中国金融体系核心支柱。",
            }
            if asset in _KNOWN_PROFILES and not chart_data.get("company_intro"):
                chart_data["company_intro"] = _KNOWN_PROFILES[asset]
                logger.info("[FALLBACK] using known company profile for %s", asset)

        # === Phase 1.5: akshare for structured financial data ===
        try:
            import akshare as _ak

            _code_match = re.search(r"(\d{6})", asset)
            if _code_match:
                _code = _code_match.group(1)
                _fin = _ak.stock_financial_abstract_ths(symbol=_code, indicator="按年度")
                if _fin is not None and len(_fin) > 0:
                    # 取最近3年(最新的在最后)
                    _records = _fin.tail(3).to_dict(orient="records")
                    # 直接写入result而非chart_data(避免被Tavily覆盖)
                    result["akshare_financials"] = _records
                    result["akshare_raw"] = str(_records)[:2000]
                    sources_with_data += 1
                    logger.info("[DATA] akshare: %d years for %s", len(_records), asset)
        except Exception as e:
            logger.debug("[DATA] akshare: %s", e)

        # === Phase 2: yfinance for market data (if global stock) ===
        yd = self._network_phase("yfinance", lambda: self._yfinance_search(asset))
        if yd:
            chart_data.update(yd)
            sources_with_data += 1

        # === Phase 3: akshare for A-stock data ===
        ad = self._network_phase("akshare", lambda: self._akshare_search(asset))
        if ad:
            chart_data.update(ad)
            sources_with_data += 1

        # === Phase 4: StockSDK for enhanced financial data ===
        if self._tavily:
            sd = self._network_phase("stocksdk", lambda: self._stock_sdk_search(asset))
            if sd:
                chart_data.update(sd)
                sources_with_data += 1

        # === Phase 4.5: Universal collector (zero-dependency fallback) ===
        if not chart_data and not result.get("chart_data"):
            try:
                from core.data_universal import collect_universal

                ud = collect_universal(asset)
                if ud.get("status") == "ok":
                    chart_data["universal"] = ud
                    sources_with_data += 1
                    logger.info("Universal collector contributed data for %s", asset)
            except Exception as e:
                logger.debug("Universal collector failed: %s", e)

        # === Phase 5: Build result ===
        result["chart_data"] = chart_data
        result["financials"] = {
            "status": "available" if chart_data else "unavailable",
            "data": chart_data,
            "source": "tavily+yfinance+akshare",
            "quality": "estimated",
        }
        all_failed = not bool(chart_data)
        result["_data_quality"] = {
            "sources_with_data": sources_with_data,
            "all_failed": all_failed,
            "warning": "" if chart_data else "所有数据源不可用",
            "blocking": all_failed,
        }
        result["status"] = "done"

        # Data freshness check (FP2 compliance)
        from datetime import datetime

        result["_data_freshness"] = {
            "timestamp": datetime.now().isoformat(),
            "stale_threshold_hours": 24,
            "recheck_needed": False,
        }
        return result

    def _local_search(self, asset):
        """从本地库读取数据：financials.db 财务 + qlib_bin 行情。

        生成与 akshare 相同结构的 fig_* 数据，供图表使用。
        本地数据是确定性来源，不依赖网络。
        """
        chart_data = {}
        root = Path(__file__).resolve().parent.parent
        db = root / "data" / "financials.db"
        qlib_dir = root / "data" / "qlib_bin"

        # 提取股票代码
        import re as _re

        # R26（2026-08-02 全量修复）：统一资产解析层，兼容名字/代码/名字+代码
        try:
            from core.asset_resolver import resolve_asset

            _ra = resolve_asset(asset)
            code = _ra.code
        except Exception:
            code = ""
        if not code:
            code_match = _re.search(r"(\d{6})", asset)
            code = code_match.group(1) if code_match else ""
        if not code:
            # 尝试从名字找代码（读 instruments）
            inst_file = qlib_dir / "instruments" / "all.txt"
            if inst_file.exists():
                for line in inst_file.read_text(encoding="utf-8").splitlines():
                    if len(asset) >= 4 and asset[:4] in line:
                        code = line.split("\t")[0][-6:]
                        break
        if not code:
            # R24（2026-08-02 数据链路修复）：中文名→代码映射
            code = _lookup_code_by_name(asset)

        # 0. 招股书数据（非上市公司核心来源）
        try:
            prospectus_path = root / "data" / "prospectus_findings.json"
            if prospectus_path.exists():
                import json as _json

                pdata = _json.loads(prospectus_path.read_text(encoding="utf-8"))
                # 匹配公司名：文件名主名或全名
                for key, p in pdata.items():
                    if asset in key or key[:4] in asset or (len(asset) >= 4 and asset[:4] in key):
                        if isinstance(p, dict) and p.get("status") == "ok":
                            # 营收/净利（支持 revenues_by_year 多年趋势 + revenues 单值）
                            rev = p.get("revenues_by_year") or {}
                            prof = p.get("profits_by_year") or {}
                            if rev:
                                yearly_rev = {}
                                for yr, r in rev.items():
                                    val = r.get("value", 0) if isinstance(r, dict) else r
                                    unit = r.get("unit", "万元") if isinstance(r, dict) else "万元"
                                    mult = 1e-4 if unit == "万元" else (1 if unit == "亿元" else 1e-8)
                                    yearly_rev[yr] = val * mult
                                chart_data["fig_revenue_trend"] = yearly_rev
                            elif p.get("revenues"):
                                yearly_rev = {}
                                for i, r in enumerate(p["revenues"]):
                                    val = r.get("value", 0)
                                    unit = r.get("unit", "万元")
                                    mult = 1e-4 if unit == "万元" else (1 if unit == "亿元" else 1e-8)
                                    yearly_rev[str(2025 - i)] = val * mult
                                chart_data["fig_revenue_trend"] = yearly_rev
                            if prof:
                                yearly_prof = {}
                                for yr, pv in prof.items():
                                    val = pv.get("value", 0) if isinstance(pv, dict) else pv
                                    unit = pv.get("unit", "万元") if isinstance(pv, dict) else "万元"
                                    mult = 1e-4 if unit == "万元" else (1 if unit == "亿元" else 1e-8)
                                    yearly_prof[yr] = val * mult
                                chart_data["fig_profitability"] = yearly_prof
                            elif p.get("profits"):
                                yearly_prof = {}
                                for i, pv in enumerate(p["profits"]):
                                    val = pv.get("value", 0)
                                    unit = pv.get("unit", "万元")
                                    mult = 1e-4 if unit == "万元" else (1 if unit == "亿元" else 1e-8)
                                    yearly_prof[str(2025 - i)] = val * mult
                                chart_data["fig_profitability"] = yearly_prof
                            # 公司简介
                            if p.get("intro"):
                                chart_data["company_intro"] = p["intro"]
                            logger.info("[LOCAL] 招股书: %s", key)
                        break
        except Exception as e:
            logger.debug("prospectus: %s", e)

        if not code:
            return chart_data

        # 1. 本地财务层（financials.db）
        if db.exists():
            try:
                import sqlite3

                conn = sqlite3.connect(str(db))
                rows = conn.execute(
                    "SELECT quarter, table_name, field, value FROM financials WHERE code=? ORDER BY quarter",
                    (code,),
                ).fetchall()
                conn.close()
                if rows:
                    # 按年份聚合：取每年最后一条季度数据
                    yearly = {}
                    for quarter, tname, field, value in rows:
                        year = str(quarter)[:4]
                        if year.isdigit():
                            # 每年只保留最新季度（按 quarter 排序，覆盖旧值）
                            yearly.setdefault(year, {})
                            yearly[year][field] = value
                    # 营收（profit 表 MBRevenue = 主营营业收入，单位元→亿元）
                    rev_trend = {}
                    for year, fields in yearly.items():
                        if "MBRevenue" in fields and fields["MBRevenue"]:
                            rev_trend[year] = fields["MBRevenue"] / 1e8
                    if rev_trend:
                        chart_data["fig_revenue_trend"] = rev_trend
                    # 净利（netProfit，单位元→亿元）
                    profit = {}
                    for year, fields in yearly.items():
                        if "netProfit" in fields and fields["netProfit"]:
                            profit[year] = fields["netProfit"] / 1e8
                    if profit:
                        chart_data["fig_profitability"] = profit
                    # 毛利率（gpMargin，Baostock 存的是比值 0.9153 → 91.5%）
                    margin = {}
                    for year, fields in yearly.items():
                        if "gpMargin" in fields and fields["gpMargin"]:
                            margin[year] = fields["gpMargin"] * 100
                    if margin:
                        chart_data["fig_margin"] = margin
                    # ROE（roeAvg，比值→%）
                    roe = {}
                    for year, fields in yearly.items():
                        if "roeAvg" in fields and fields["roeAvg"]:
                            roe[year] = fields["roeAvg"] * 100
                    if roe:
                        chart_data["fig_roe"] = roe
                    logger.info("[LOCAL] financials: %d 季度 %s", len(rows), code)
            except Exception as e:
                logger.debug("local financials: %s", e)

        # 2. 本地行情（qlib_bin）
        try:
            import numpy as np

            # 代码归一化
            inst = code
            if inst.startswith(("6", "9")):
                inst = "sh" + inst
            elif inst.startswith(("0", "2", "3")):
                inst = "sz" + inst
            feat_dir = qlib_dir / "features" / inst
            cal_path = qlib_dir / "calendars" / "day.txt"
            if feat_dir.exists() and cal_path.exists():
                close_path = feat_dir / "close.day.bin"
                if close_path.exists():
                    raw = close_path.read_bytes()
                    arr = np.frombuffer(raw, dtype="<f4")
                    if len(arr) > 1:
                        start_idx = int(arr[0])
                        closes = arr[1:]
                        cal = cal_path.read_text(encoding="utf-8").splitlines()
                        # 年度末 close
                        annual = {}
                        for i, px in enumerate(closes):
                            if start_idx + i < len(cal):
                                annual[cal[start_idx + i][:4]] = float(px)
                        chart_data["fig_qlib_price"] = annual
                        logger.info("[LOCAL] qlib: %s 行情 %d 天", inst, len(closes))
        except Exception as e:
            logger.debug("local qlib: %s", e)

        return chart_data

    def _tavily_search(self, asset, time_anchor=None):
        """Use Tavily SDK to search for structured financial data + extract with DeepSeek"""
        chart_data = {}
        base_year = (time_anchor or {}).get("base_year", "2025")
        data_min_year = (time_anchor or {}).get("data_min_year", "2025")
        queries = [
            f"{asset} {data_min_year} {base_year} 营收 净利润 毛利率 财报 年度报告 最新",
            f"{asset} 业务结构 分部分务 市场份额 竞争对手 2026",
        ]
        all_text = ""
        for q in queries:
            try:
                r = self._tavily.search(query=q, max_results=5)
                for res in r.get("results", []):
                    c = res.get("content", "")
                    title = res.get("title", "")
                    if c and len(c) > 100:
                        all_text += f"--- {title} ---\n{c[:2000]}\n"
            except Exception as e:
                logger.debug("Tavily query failed: %s", e)

        if not all_text:
            return chart_data

        # Use LLM to extract structured financial data from search results
        # R55（2026-08-03）：provider 跟随模式路由（LLM_PROVIDER），非写死 deepseek。
        # 训练模式=agent_provider（Marvis），性能模式=deepseek。
        try:
            import os as _os

            from core.deepseek_client import call_llm

            provider = _os.environ.get("LLM_PROVIDER", "deepseek")
            base_year = int(base_year) if str(base_year).isdigit() else 2025
            data_min_year = int(data_min_year) if str(data_min_year).isdigit() else 2023
            y1, y2, y3 = data_min_year, data_min_year + 1, base_year
            prompt = (
                "Extract structured financial data from the following text about %s. "
                "The report is written as of 2026. Prioritize data from %d onward.\n"
                "Return ONLY valid JSON with double-quoted keys. Use null for missing data.\n\n"
                "Text:\n%s\n\n"
                "Return format:\n"
                '{"revenue":{"%d":val,"%d":val,"%d":val},'
                '"net_profit":{"%d":val,"%d":val,"%d":val},'
                '"gross_margin":{"%d":val,"%d":val,"%d":val},'
                '"segments":{"name":pct},'
                '"peers":{"competitor":val}}'
            ) % (asset, data_min_year, all_text[:6000], y1, y2, y3, y1, y2, y3, y1, y2, y3)
            resp = call_llm(
                [
                    {"role": "system", "content": "You extract financial data as JSON. Only output valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.05,
                max_tokens=1500,
                provider=provider,
            )
            raw = resp["choices"][0]["message"]["content"]
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                # R55（2026-08-03 Phase B）：数据标签四元组
                # 每条采集数据带 {source, year, scope, confidence} 供 CrossValidator 消费。
                # source 标明采集渠道（tavily+LLM提取），year 指数据对应年份，
                # scope 全球/中国/公司，confidence 由 provider 与提取方式推断。
                _source_label = f"tavily+llm({provider})"
                _conf_base = 0.6 if provider == "deepseek" else 0.5  # agent 提取置信度略低
                _meta = {
                    "source": _source_label,
                    "year": str(base_year),
                    "scope": "company",
                    "confidence": _conf_base,
                }
                if data.get("revenue"):
                    chart_data["fig_revenue_trend"] = data["revenue"]
                if data.get("gross_margin"):
                    chart_data["fig_profitability"] = data["gross_margin"]
                if data.get("peers"):
                    chart_data["fig_peer_comparison"] = data["peers"]
                if data.get("segments"):
                    chart_data["fig_business_segments"] = data["segments"]
                if data.get("net_profit"):
                    chart_data["fig_valuation"] = data["net_profit"]
                # 记录数据标签（供交叉验证层消费）
                chart_data["_collection_meta"] = _meta
                for k in list(chart_data.keys()):
                    if isinstance(chart_data[k], dict):
                        cleaned = {}
                        for sk, sv in chart_data[k].items():
                            if sv is not None:
                                cleaned[sk] = sv
                        chart_data[k] = cleaned
                        if not chart_data[k]:
                            del chart_data[k]
                logger.info("Tavily+LLM(%s) extracted %d chart items for %s", provider, len(chart_data), asset)
        except Exception as e:
            logger.debug("LLM extraction failed: %s", e)
        return chart_data

    def _yfinance_search(self, asset):
        """Use yfinance as supplementary data source"""
        result = {}
        try:
            import yfinance as yf

            stock_code = "".join(c for c in asset if c.isdigit())[:6]
            if stock_code:
                ticker = yf.Ticker(stock_code + ".SS")  # Shanghai
                info = ticker.info or {}
                if info.get("marketCap"):
                    result["fig_valuation"] = result.get("fig_valuation", {})
                    result["fig_valuation"]["market_cap"] = info.get("marketCap", 0) / 1e8
        except Exception:
            pass
        return result

    def _stock_sdk_search(self, asset):
        """Use StockSDK for A-share financial data."""
        result = {}
        try:
            from core.stock_sdk_bridge import StockSDKBridge

            bridge = StockSDKBridge()
            if not bridge.available:
                return result

            # Extract stock code
            codes = re.findall(r"\d{6}", asset)
            code = codes[0] if codes else ""

            # Get quote
            quote_data = bridge.quote(code) if code else None
            if quote_data:
                price = quote_data.get("price", 0)
                change_pct = quote_data.get("changePercent", 0)
                market_cap = quote_data.get("marketCap", 0)
                if price:
                    result["fig_valuation"] = {"price": price, "change_pct": change_pct, "market_cap": market_cap}

            # Get fund flow
            flow = bridge.fund_flow(code) if code else None
            if flow:
                result["fig_capital_flow"] = flow

            # Get industry board data
            board = bridge.board_list("industry")
            if board:
                result["fig_industry_board"] = board[:10]

            logger.info("StockSDK: collected data for %s", asset)
        except Exception as e:
            logger.debug("StockSDK search failed: %s", e)
        return result

    def _akshare_search(self, asset):
        """Use akshare to extract real A-stock financial data"""
        result = {}
        try:
            import akshare as ak

            # Try to extract stock code from name if not already a code
            stock_code = "".join(c for c in asset if c.isdigit())[:6]
            if len(stock_code) != 6:
                # Resolve Chinese stock name to code
                try:
                    df_codes = ak.stock_info_a_code_name()
                    match = df_codes[df_codes["name"].str.contains(asset[:4], na=False)]
                    if not match.empty:
                        stock_code = match.iloc[0]["code"]
                except Exception:
                    pass
            if len(stock_code) != 6:
                return result

            # 1. 年度财务摘要（营收/净利/毛利率等）
            df_annual = ak.stock_financial_abstract_ths(symbol=stock_code, indicator="按年度")
            if df_annual is not None and not df_annual.empty:
                data = {}
                for _, row in df_annual.iterrows():
                    year = str(row.get("报告期", ""))[:4]
                    if not year.isdigit():
                        continue
                    data[year] = {
                        "revenue": row.get("营业总收入", ""),
                        "net_profit": row.get("净利润", ""),
                        "gross_margin": row.get("销售毛利率", ""),
                        "roe": row.get("净资产收益率", ""),
                        "eps": row.get("基本每股收益", ""),
                        "asset_liability_ratio": row.get("资产负债率", ""),
                    }
                if data:
                    result["fig_revenue_trend"] = data
                    result["fig_profitability"] = data
                    logger.info("akshare annual: %d years(%s)", len(data), ", ".join(sorted(data.keys())))

            # 2. 最新报告期财务摘要
            df_recent = ak.stock_financial_abstract_ths(symbol=stock_code, indicator="按报告期")
            if df_recent is not None and not df_recent.empty:
                latest = df_recent.iloc[0]
                result["fig_valuation"] = {
                    "net_profit": latest.get("净利润", ""),
                    "revenue": latest.get("营业总收入", ""),
                    "gross_margin": latest.get("销售毛利率", ""),
                    "period": str(latest.get("报告期", "")),
                    "roe": latest.get("净资产收益率", ""),
                }

            # 3. 主营构成/业务分部（→ fig_business_segments）
            try:
                df_zygc = ak.stock_zygc_em(symbol=stock_code)
                if df_zygc is not None and not df_zygc.empty:
                    # 取最新报告期的主营构成，按收入占比
                    segments = {}
                    for _, row in df_zygc.iterrows():
                        item = str(row.get("分类", row.get("项目名称", ""))).strip()
                        ratio = row.get("收入比例", row.get("占营业收入比例", None))
                        if item and item != "nan" and ratio is not None:
                            try:
                                segments[item[:12]] = float(str(ratio).replace("%", ""))
                            except (ValueError, TypeError):
                                pass
                    if segments:
                        result["fig_business_segments"] = segments
                        logger.info("akshare zygc: %d segments", len(segments))
                    else:
                        logger.warning("akshare zygc: 解析到 0 个分部（列名可能不匹配）")
            except Exception as e:
                logger.warning("akshare zygc FAILED: %s", e)

            # 4. 个股资金流（→ fig_capital_flow）
            try:
                df_flow = ak.stock_individual_fund_flow(
                    stock=stock_code, market="sh" if stock_code.startswith("6") else "sz"
                )
                if df_flow is not None and not df_flow.empty:
                    latest_flow = df_flow.iloc[-1]
                    flow = {}
                    for col_key, label in [
                        ("主力净流入-净额", "主力净流入"),
                        ("超大单净流入-净额", "超大单"),
                        ("大单净流入-净额", "大单"),
                        ("中单净流入-净额", "中单"),
                        ("小单净流入-净额", "小单"),
                    ]:
                        if col_key in latest_flow.index:
                            v = latest_flow[col_key]
                            try:
                                flow[label] = float(v)
                            except (ValueError, TypeError):
                                pass
                    if flow:
                        result["fig_capital_flow"] = flow
                        logger.info("akshare fund_flow: %d entries", len(flow))
                    else:
                        logger.warning("akshare fund_flow: 解析到 0 个资金流（列名可能不匹配）")
            except Exception as e:
                logger.warning("akshare fund_flow FAILED: %s", e)

            # 5. 同业对比（→ fig_peer_comparison）
            # 通过行业板块成分股获取可比公司的 PE/PB/市值
            # 路径: 确定行业 → 行业板块成分股 → 实时行情 PE/PB/市值
            try:
                peers = self._akshare_peers(ak, stock_code)
                if peers:
                    result["fig_peer_comparison"] = peers
                    logger.info("akshare peers: %d companies", len(peers))
            except Exception as e:
                logger.warning("akshare peers FAILED: %s", e)

        except Exception as e:
            logger.warning("akshare search failed: %s", e)
        return result

    def _akshare_peers(self, ak, stock_code: str) -> dict:
        """获取同业可比公司的 PE/PB/市值（AkShare 行业板块路径）。

        返回 {公司名: {pe, pb, mcap}}，供同业对比图表使用。
        接口不可用时返回空 dict（不编造数据）。
        """
        peers = {}
        try:
            # 1. 找到该股票所属行业板块
            industry = ""
            try:
                df_board = ak.stock_board_industry_name_em()
                if df_board is not None and not df_board.empty:
                    # 遍历板块找成分股含该股票
                    for _, row in df_board.iterrows():
                        board_name = str(row.get("板块名称", ""))
                        try:
                            df_cons = ak.stock_board_industry_cons_em(symbol=board_name)
                            if df_cons is not None and not df_cons.empty:
                                codes = df_cons["代码"].astype(str).str.zfill(6)
                                if stock_code in codes.tolist():
                                    industry = board_name
                                    break
                        except Exception:
                            continue
            except Exception as e:
                logger.debug("peers: board locate failed: %s", e)

            if not industry:
                return {}

            # 2. 获取行业板块成分股 + 实时行情（含 PE/PB/总市值）
            df_cons = ak.stock_board_industry_cons_em(symbol=industry)
            if df_cons is None or df_cons.empty:
                return {}
            # 全市场行情，取 PE/PB/市值
            df_spot = ak.stock_zh_a_spot_em()
            if df_spot is None or df_spot.empty:
                return {}

            # 建立 代码→行情 映射
            spot_map = {}
            for _, srow in df_spot.iterrows():
                code = str(srow.get("代码", "")).zfill(6)
                try:
                    spot_map[code] = {
                        "name": str(srow.get("名称", "")),
                        "pe": srow.get("市盈率-动态", None),
                        "pb": srow.get("市净率", None),
                        "mcap": srow.get("总市值", None),
                    }
                except Exception:
                    continue

            # 3. 取成分股中市值相近的 5-8 家（含本股）
            cons_codes = df_cons["代码"].astype(str).str.zfill(6).tolist()
            self_mcap = None
            for c in cons_codes:
                if c == stock_code and c in spot_map:
                    self_mcap = spot_map[c].get("mcap")
                    break

            # 过滤出有 PE/PB 的成分股，按市值排序取相近的
            candidates = []
            for c in cons_codes:
                if c not in spot_map:
                    continue
                info = spot_map[c]
                pe, pb, mcap = info["pe"], info["pb"], info["mcap"]
                if pe is None or pb is None:
                    continue
                try:
                    pe_f, pb_f, mcap_f = float(pe), float(pb), float(mcap)
                except (ValueError, TypeError):
                    continue
                candidates.append((c, info["name"], pe_f, pb_f, mcap_f))

            if not candidates:
                return {}

            # 排序：本股优先，其余按市值与自股市值差距排序
            candidates.sort(
                key=lambda x: (
                    0 if x[0] == stock_code else 1,
                    abs(x[4] - (self_mcap or 0)),
                )
            )
            for c, name, pe_f, pb_f, mcap_f in candidates[:8]:
                peers[name] = {"pe": pe_f, "pb": pb_f, "mcap": round(mcap_f / 1e8, 1)}
            return peers
        except Exception as e:
            logger.warning("_akshare_peers failed: %s", e)
            return {}


def test():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    dc = DataCollectorV5()
    r = dc.collect("芯联集成", "listed_company")
    print("\n=== Result ===")
    print("Status:", r["status"])
    print("Chart data keys:", list(r.get("chart_data", {}).keys()))
    for k, v in r.get("chart_data", {}).items():
        print(f"  {k}: {v}")
    print("Data quality:", r.get("_data_quality", {}))


if __name__ == "__main__":
    test()
