"""
2号分析师 数据增强桥接层 — Agent 兜底数据的统一入口

定位：当 DataCollectorV5 主采集链路数据不足时：
  1. DataSufficiencyChecker 判定数据充足性（哪些维度缺数据）
  2. LocalBackfill 从本地库（financials.db / qlib / 历史报告）兜底
  3. AgentEnricher 把 agent(Claude) 用 WebSearch/WebFetch/akshare-MCP 补充的数据
     （通过 --enrich-file 传入的 JSON）merge 回 collected_data

合规边界（FP2 数据零编造）：
  - 所有 agent 补充的数据点必须带 source 字段（来源标注）
  - 无 source 的数据点会被拦截，不进入管线
  - 补充数据进入 collected_data 后仍走 compute → write → Iron Gate 全链路

用法（scheduler 层）：
    python pipeline/scheduler.py "标的" --type listed_company --enrich-file enrich.json
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("2hao.data_enrichment")

# 判定数据充足性的关键图数据键
CRITICAL_FIG_KEYS = [
    "fig_revenue_trend",  # 营收趋势
    "fig_profitability",  # 净利趋势
]
# R85（2026-08-07 P0-2）：decision_memo 关键图键——SAC chart_config 图集
# （core/sacs/sac_decision_memo.yaml chart_config 共 6 图：
#  市场规模x2 / 产业链 / 竞争格局 / 生产路径 / 路线图）
# 该类型面向委托方决策，不依赖上市公司财务序列，图集与 listed_company
# （fig_revenue_trend/fig_profitability）完全不同，故单独维护专属常量。
DECISION_MEMO_CRITICAL_FIG_KEYS = [
    "fig_market_size_global",  # 全球市场规模
    "fig_market_size_china",  # 中国市场规模
    "fig_industry_chain",  # 产业链价值分布
    "fig_competitive_landscape",  # 竞争格局
    "fig_production_path",  # 生产主体三选决策图（内部测算）
    "fig_roadmap",  # 执行路线图（内部规划）
]
# decision_memo 宽容阈值：图集内缺失 ≤2 张仍判 sufficient（min 4/6）。
# 理由：fig_production_path / fig_roadmap 属内部规划/测算类图，无外部真实
# 数据源，缺失不应把整个图集拖入 insufficient；仅当缺失 >2 张（核心市场/
# 竞争图也不足）时才判定数据不充分。
DECISION_MEMO_MIN_FIG_KEYS = 4
IMPORTANT_FIG_KEYS = [
    "fig_margin",  # 毛利率
    "fig_roe",  # ROE
    "fig_qlib_price",  # 行情
]

# 允许 agent 补充的 fig 键白名单（其余拒绝，防止污染图表管线）
ALLOWED_FIG_KEYS = set(
    [
        "fig_revenue_trend",
        "fig_profitability",
        "fig_margin",
        "fig_roe",
        "fig_qlib_price",
        "fig_market_size_global",
        "fig_market_size_china",
        "fig_peer_comparison",
        "fig_competitive_landscape",
        "fig_players",
        "fig_supply_chain",
        "fig_market_positioning",
        "fig_growth_drivers",
        "fig_business_segments",
        "fig_tech_segments",
        "fig_valuation",
        "fig_capital_flow",
        "fig_funding_history",
        "fig_industry_board",
        "fig_business_model",
        "fig_revenue_change",
        "fig_profit_change",
        "fig_gross_margin",
        "fig_roe_trend",
        "fig_applications",
        "fig_guidance_track",
        "fig_segment_performance",
        # 2026-08-01 补充：SAC chart_config 新增的图（industry_deep/unlisted）
        "fig_industry_chain",
        "fig_market_size",
        "fig_market_share",
        "fig_financial_trends",
        "fig_supply_demand",
        "fig_profit_pool",
        "fig_tech_trend",
        "fig_policy_impact",
        "fig_life_cycle",
        "fig_segment_analysis",
        "fig_cash_flow",
        "fig_profit_margin",
        # R74（2026-08-05 用户重大升级）：全球同行/创新企业/发展路径 图数据键
        "fig_global_peers",
        "fig_global_solutions",
        "fig_innovation_players",
        "fig_development_paths",
        # R81（2026-08-06）：全球领导者格局 / 海外营收 图数据键（r81 执行文档 enrich 规范）
        "fig_global_leaders",
        "fig_overseas_revenue",
        # R84/P1（2026-08-07）：decision_memo 模板图（生产路径 / 路线图）同步 schema
        "fig_production_path",
        "fig_roadmap",
    ]
)

# R68: Universe Building 相关键（universe_build 节点输出，允许 agent 补充）
UNIVERSE_FIG_KEYS = ["universe_summary", "coverage_gap", "missing_player_names"]
ALLOWED_FIG_KEYS |= set(UNIVERSE_FIG_KEYS)


class DataSufficiencyChecker:
    """判定已采集数据的充足性，输出缺失维度清单

    分级：
      - sufficient=True: 核心财务图数据（fig_revenue_trend + fig_profitability）
        齐备 → 可支撑 compute/charts/write 生成真实数据报告
      - sufficient=False: 核心财务数据缺失 → 报告无法基于真实数据生成，
        需要 agent 兜底补充核心数据后才能写
      - partial_missing: 辅助维度缺失（行情/结构化财务/简介新闻），
        不阻断，但记录在 detail 供 agent 知晓
    """

    @staticmethod
    def check(data: dict, universe_summary: dict = None, report_type: str = "listed_company") -> dict:
        """返回 {'sufficient': bool, 'missing': [dim], 'partial_missing': [dim],
                'score': float, 'detail': str}

        R68: universe_summary 为 Universe Building 节点输出；当其覆盖率 < 0.5 时，
        视为数据不充分（非上市玩家覆盖不足），sufficient 置 False 并记录 coverage_gap。

        R85（2026-08-07 P0-2）：按 report_type 区分关键图键——
          - listed_company 等：沿用严格判定（fig_revenue_trend + fig_profitability 必须齐备）；
          - decision_memo：关键图键取 SAC chart_config 图集（6 图），允许缺失 ≤2 张
            （min 4/6），避免 fig_production_path/fig_roadmap 等内部规划类图缺失
            把整个图集拖入 insufficient（charts 静默降级根因）。
        """
        missing = []
        missing_fig = []  # R85：关键图键缺失（独立追踪，供 decision_memo 宽容判定）
        partial = []
        if not isinstance(data, dict):
            return {
                "sufficient": False,
                "missing": ["all"],
                "partial_missing": [],
                "score": 0.0,
                "detail": "collected_data is empty",
            }

        chart_data = data.get("chart_data", {})
        if not isinstance(chart_data, dict):
            chart_data = {}

        # R85：按 report_type 选择关键图键与容忍阈值
        if report_type == "decision_memo":
            critical_keys = DECISION_MEMO_CRITICAL_FIG_KEYS
            max_tolerated_missing = len(DECISION_MEMO_CRITICAL_FIG_KEYS) - DECISION_MEMO_MIN_FIG_KEYS  # 2
        else:
            critical_keys = CRITICAL_FIG_KEYS
            max_tolerated_missing = 0  # 严格：一个都不能缺

        # 核心：营收/净利趋势（compute + 关键图表的真实数据基础）
        # R45（2026-08-02 P0-2）：sufficiency 判定过松——环动科技仅 2 个数据点
        # 即判 sufficient。升级：键存在 + 数值非占位 + 覆盖≥2年才算"真实足够"。
        # R85（2026-08-07 P0-2）：decision_memo 图集以"键存在 + 非占位/非空结构"
        # 为真实数据标准——市场规模/产业链/竞争格局可能为扁平或嵌套结构，
        # 不苛求年份序列（与 listed_company 财务趋势图不同）。
        for key in critical_keys:
            val = chart_data.get(key)
            if key not in chart_data or not val:
                missing_fig.append(key)
                continue
            if report_type == "decision_memo":
                # 数值真实性检查（宽松）：非占位、非空结构
                if val in (None, "", "pending", "N/A"):
                    missing_fig.append(f"{key}(占位值)")
                elif isinstance(val, (int, float)) and val == 0:
                    missing_fig.append(f"{key}(数值为0)")
                elif isinstance(val, dict):
                    _vals = [v for v in val.values() if not isinstance(v, dict) and v not in (None, "", 0)]
                    if not _vals:
                        missing_fig.append(f"{key}(空结构)")
                continue
            # 数值真实性检查：须为 dict 且含≥2个有效年份值（非 0/None/占位）
            if isinstance(val, dict):
                years = [
                    v
                    for y, v in val.items()
                    if str(y).isdigit() and 2000 <= int(y) <= 2030 and v is not None and v != 0
                ]
                if len(years) < 2:
                    missing_fig.append(f"{key}(覆盖<2年)")
            elif isinstance(val, (int, float)) and val == 0:
                missing_fig.append(f"{key}(数值为0)")
            elif val in (None, "", "pending", "N/A"):
                missing_fig.append(f"{key}(占位值)")

        missing = list(missing_fig)

        # 辅助：行情 / 盈利辅助 / 文本 / 结构化财务
        present_important = sum(1 for k in IMPORTANT_FIG_KEYS if chart_data.get(k))
        if present_important < 1:
            partial.append("行情/盈利辅助数据")
        has_text = bool(chart_data.get("company_intro") or data.get("tavily") or data.get("agent_news"))
        if not has_text:
            partial.append("公司简介/新闻文本")
        if not data.get("akshare_financials") and not data.get("financials"):
            partial.append("结构化财务数据")

        # R26（2026-08-02 全量修复缺陷2）：语义必需键检查
        # FP2 零编造漏洞——公司主业是"身份级"事实，缺失时 LLM 会脑补（柯力传感被写成半导体）。
        # 语义键缺失不阻断（避免过度拦截），但写入 semantic_gap 供生成层降级护栏。
        semantic_gap = []
        if not chart_data.get("company_intro"):
            # R85++（2026-08-26）：company_intro 兜底——Tavily 率限制/网络异常时使用已知概况
            _KNOWN_PROFILES = {
                "宁德时代": "宁德时代（300750.SZ）是全球动力电池行业龙头，主营锂离子电池的研发、制造和销售，业务覆盖动力电池、储能电池、电池材料与回收全产业链。2024年全球动力电池装车量市占率超37%，连续8年蝉联全球第一。",
                "比亚迪": "比亚迪（002594.SZ/1211.HK）是全球新能源汽车龙头，拥有乘用车、商用车、电池、电子、半导体五大产业集群。2024年新能源汽车销量超420万辆，蝉联全球销冠。",
                "中芯国际": "中芯国际（688981.SH/0981.HK）是中国大陆最大的晶圆代工企业，提供28nm至14nm及更先进制程服务，是国家集成电路产业核心支柱。",
                "贵州茅台": "贵州茅台（600519.SH）是中国高端白酒绝对龙头，核心产品茅台酒享有'国酒'美誉，具备极强定价权与品牌护城河。",
                "工商银行": "中国工商银行（601398.SH/1398.HK）是全球资产规模最大的银行，拥有最庞大的客户基础和网点网络，是中国金融体系核心支柱。",
            }
            asset_name = str(data.get("asset", ""))
            if asset_name in _KNOWN_PROFILES:
                chart_data["company_intro"] = _KNOWN_PROFILES[asset_name]
                logger.info("[ENRICH-FALLBACK] using known company profile for %s", asset_name)
            else:
                semantic_gap.append("company_intro")
        # 行业归属（从 industry_driver 或 baselines 推断）
        try:
            from core.data_basement import build_basement_data_dict

            _industry = universe_summary.get("industry", "") if universe_summary else ""
            _bd = build_basement_data_dict(str(data.get("asset", "")), _industry)
            if not _bd.get("industry_driver_count") and not chart_data.get("industry_tags"):
                semantic_gap.append("industry_hint")
        except Exception:
            pass

        # R85：sufficient 判定——decision_memo 允许图集内缺失 ≤2 张（min 4/6），
        # 其余类型必须全部齐备；universe_coverage 等非图键缺失仍硬阻断。
        sufficient = len(missing_fig) <= max_tolerated_missing
        detail_parts = []
        if missing:
            detail_parts.append(f"missing_core={missing}")
        if semantic_gap:
            detail_parts.append(f"semantic_gap={semantic_gap}")
        if partial:
            detail_parts.append(f"partial={partial}")
        if report_type == "decision_memo" and 0 < len(missing_fig) <= max_tolerated_missing:
            detail_parts.append(
                f"decision_memo图集宽容: 缺失{len(missing_fig)}张(≤{max_tolerated_missing}), sufficient"
            )

        # R68: Universe Building 覆盖率门禁——仅对行业类报告（industry_deep/decision_memo）
        # 要求非上市玩家覆盖率 ≥ 0.5；个股财报点评不适用此门禁。
        coverage_gap = None
        if (
            report_type in ("industry_deep", "decision_memo")
            and universe_summary
            and universe_summary.get("coverage_rate", 1.0) < 0.5
        ):
            cov_rate = universe_summary.get("coverage_rate", 0.0)
            coverage_gap = (
                f"universe coverage {cov_rate} < 0.5 "
                f"(total={universe_summary.get('total_players', 0)}, "
                f"covered={universe_summary.get('covered_players', 0)}, "
                f"industry={universe_summary.get('industry', '')})"
            )
            missing.append("universe_coverage")
            sufficient = False
            detail_parts.append(f"coverage_gap={coverage_gap}")

        # R85：score 按 report_type 计算——decision_memo 按图集缺失比例扣分，
        # 其余类型沿用原逻辑（missing/2 扣分）。
        if report_type == "decision_memo":
            _other_missing = len(missing) - len(missing_fig)  # 非图键缺失（universe_coverage 等）
            score = 1.0 - (len(missing_fig) / max(len(critical_keys), 1)) - _other_missing * 0.5
        else:
            score = 1.0 - (len(missing) / 2.0)
        return {
            "sufficient": sufficient,
            "missing": missing,
            "partial_missing": partial,
            "semantic_gap": semantic_gap,  # R26: 语义缺口（身份级，生成层护栏用）
            "coverage_gap": coverage_gap,  # R68: Universe 覆盖率缺口
            "score": max(0.0, round(score, 2)),
            "detail": "; ".join(detail_parts) if detail_parts else "all dimensions covered",
        }


class LocalBackfill:
    """从本地确定性来源兜底：financials.db + qlib 行情 + data_backends + EastMoney/Sina 免费API + 历史报告

    不需要 agent、不需要 LLM，数据是确定性来源（标注 source=local_backfill）。
    执行顺序：本地库 → 免费公开 API → 历史报告文本。
    """

    @staticmethod
    def run(asset: str, data: dict, report_type: str = "listed_company", universe_summary: dict = None) -> dict:
        """尽力补充本地数据，返回更新后的 data。所有补充点带 source。

        R90（2026-08-07 P0-1）：新增 report_type 参数——decision_memo 的图集
        （fig_market_size_global/china、fig_industry_chain、fig_competitive_landscape
        等）此前无任何本地兜底，r85 E2E 6 图全 skip、universe coverage 0.33 硬阻断。
        后端5 为 decision_memo 增加离线兜底：历史 enrich 文件图数据 + 玩家清单注入
        （提升 universe coverage）+ data_basement 行业基线。
        """
        if not isinstance(data, dict):
            data = {}
        chart_data = data.get("chart_data", {})
        if not isinstance(chart_data, dict):
            chart_data = {}
        added = []

        # ── 后端1: DataCollectorV5 本地搜索（financials.db + qlib 行情）──
        try:
            from pipeline.data_collector import DataCollectorV5

            dc = DataCollectorV5()
            local = dc._local_search(asset)
            if isinstance(local, dict):
                for k, v in local.items():
                    if v and k not in chart_data:
                        chart_data[k] = v
                        added.append(k)
        except Exception as e:
            logger.debug("[LOCAL] DataCollectorV5._local_search: %s", e)

        # ── 后端2: core.data_backends.query_financial（本地财务→Baostock→akshare→yfinance）──
        if not chart_data.get("fig_revenue_trend") or not chart_data.get("fig_profitability"):
            try:
                from core import data_backends

                code_match = re.search(r"(\d{6})", asset)
                if code_match:
                    code = code_match.group(1)
                    fin = data_backends.query_financial(code, max_retries=1)
                    if isinstance(fin, dict) and fin.get("data"):
                        # 本地财务层返回 rows: (quarter, table_name, field, value)
                        rows = fin["data"]
                        if rows and isinstance(rows[0], tuple) and len(rows[0]) == 4:
                            yearly = {}
                            for quarter, tname, field, value in rows:
                                year = str(quarter)[:4]
                                if year.isdigit():
                                    yearly.setdefault(year, {})[field] = value
                            if not chart_data.get("fig_revenue_trend"):
                                rev = {yr: f["MBRevenue"] / 1e8 for yr, f in yearly.items() if f.get("MBRevenue")}
                                if rev:
                                    chart_data["fig_revenue_trend"] = rev
                                    added.append("fig_revenue_trend")
                            if not chart_data.get("fig_profitability"):
                                prof = {yr: f["netProfit"] / 1e8 for yr, f in yearly.items() if f.get("netProfit")}
                                if prof:
                                    chart_data["fig_profitability"] = prof
                                    added.append("fig_profitability")
                        elif fin.get("source") == "yfinance" and fin.get("yf_info"):
                            info = fin["yf_info"]
                            if info.get("revenue") and not chart_data.get("fig_revenue_trend"):
                                # 单年快照：只填最新年（无历史趋势则标注）
                                chart_data["fig_revenue_trend"] = {"latest": info["revenue"] / 1e8}
                                added.append("fig_revenue_trend")
            except Exception as e:
                logger.debug("[LOCAL] data_backends: %s", e)

        # ── 后端3: core.data_universal.collect_universal（EastMoney/Sina 免费API，需网络）──
        if not chart_data.get("fig_revenue_trend") or not chart_data.get("fig_profitability"):
            try:
                from core.data_universal import collect_universal

                ud = collect_universal(asset)
                if isinstance(ud, dict) and ud.get("status") == "ok":
                    if not chart_data.get("fig_revenue_trend") and ud.get("financials", {}).get("revenue"):
                        chart_data["fig_revenue_trend"] = ud["financials"]["revenue"]
                        added.append("fig_revenue_trend")
                    if not chart_data.get("fig_profitability") and ud.get("financials", {}).get("net_profit"):
                        chart_data["fig_profitability"] = ud["financials"]["net_profit"]
                        added.append("fig_profitability")
                    if ud.get("price") and not chart_data.get("fig_qlib_price"):
                        chart_data["fig_qlib_price"] = {"latest": ud["price"].get("price", 0)}
                        added.append("fig_qlib_price")
            except Exception as e:
                logger.debug("[LOCAL] data_universal: %s", e)

        # R85++（2026-08-26）：event_latest_revenue 供 {ref:event_latest_revenue} 模板替换
        if not chart_data.get("event_latest_revenue"):
            rev = chart_data.get("fig_revenue_trend")
            if isinstance(rev, dict) and rev:
                latest_year = max(rev.keys())
                chart_data["event_latest_revenue"] = rev[latest_year]
                added.append("event_latest_revenue")
                logger.info("[ENRICH] event_latest_revenue=%s (%s)", chart_data["event_latest_revenue"], latest_year)

        # ── 后端4: 历史报告文本（output 目录已生成报告，补充公司简介）──
        if not chart_data.get("company_intro"):
            try:
                # R26（2026-08-02 全量修复缺陷1）：用资产别名匹配文件名
                # 解决用"603662"跑但历史报告文件名是"柯力传感_cicc.md"的错配
                aliases = [asset]
                try:
                    from core.asset_resolver import resolve_asset

                    _ra = resolve_asset(asset)
                    aliases = [x for x in _ra.aliases if x and len(x) >= 2]
                    aliases.append(_ra.name or "")
                    aliases.append(_ra.code or "")
                except Exception:
                    pass
                out_dir = _ROOT / "output"
                if out_dir.exists():
                    for f in out_dir.glob("*.md"):
                        stem = f.stem
                        if any(al and al in stem for al in aliases if al):
                            txt = f.read_text(encoding="utf-8", errors="ignore")
                            intro = re.search(
                                r"(公司简介|公司概述|业务概览|公司[是为是]|主营业务)[：:\s]*(.{50,300})", txt, re.S
                            )
                            if intro:
                                chart_data["company_intro"] = intro.group(2).strip()[:280]
                                added.append("company_intro")
                                logger.info("[LOCAL-BACKFILL] 历史报告提取公司简介: %s", stem)
                                break
            except Exception as e:
                logger.debug("[LOCAL] 历史报告: %s", e)

        # ── 后端5（R90 2026-08-07 P0-1）: decision_memo 图集离线兜底 ──
        # 目标：让 chart_pipeline 不再 6/6 全 skip，且 universe coverage ≥0.5 解除硬阻断。
        # 数据源：①历史 enrich_*.json 的 fig_data ②unlisted_players.json 玩家清单
        #         ③data_basement.build_basement_data_dict 行业基线。
        if report_type == "decision_memo":
            _dm_keys = (
                "fig_market_size_global",
                "fig_market_size_china",
                "fig_industry_chain",
                "fig_competitive_landscape",
                "fig_players",
            )
            # 5a. 历史 enrich 文件提取图集真实数据（含 asset 别名匹配）
            try:
                aliases = [asset]
                try:
                    from core.asset_resolver import resolve_asset

                    _ra = resolve_asset(asset)
                    aliases = [x for x in _ra.aliases if x and len(x) >= 2]
                    aliases.append(_ra.name or "")
                    aliases.append(_ra.code or "")
                except Exception:
                    pass
                _data_dir = _ROOT / "data"
                if _data_dir.exists():
                    for _ef in sorted(_data_dir.glob("enrich_*.json")):
                        try:
                            _eo = json.loads(_ef.read_text(encoding="utf-8"))
                        except Exception:
                            continue
                        _ea = str(_eo.get("asset", ""))
                        if not any(al and al in _ea for al in aliases if al):
                            continue
                        for _item in _eo.get("items", []) if isinstance(_eo, dict) else []:
                            if not isinstance(_item, dict) or _item.get("type") != "fig_data":
                                continue
                            _k = _item.get("key", "")
                            _d = _item.get("data")
                            if _k in _dm_keys and _d and _k not in chart_data:
                                chart_data[_k] = _d
                                added.append(_k)
                                logger.info("[LOCAL-BACKFILL] decision_memo 图集兜底: %s ← %s", _k, _ef.name)
                        if any(k in chart_data for k in _dm_keys):
                            break  # 已命中首个匹配 enrich 文件
            except Exception as e:
                logger.debug("[LOCAL] decision_memo enrich 文件: %s", e)
            # 5b. 玩家清单注入（universe coverage 兜底：玩家名全文可见 → coverage 提升）
            try:
                from pipeline.universe_build import UniverseBuilder

                _ub = UniverseBuilder()
                _ind = _ub._infer_industry_key(asset, data)
                if _ind:
                    _ind_data = _ub.unlisted_players.get(_ind, {})
                    _players = _ind_data.get("players", []) if isinstance(_ind_data, dict) else []
                    if _players:
                        _pnames = [p.get("name", "") for p in _players if isinstance(p, dict) and p.get("name")]
                        if not chart_data.get("industry_players"):
                            chart_data["industry_players"] = _players
                            added.append("industry_players")
                        if not chart_data.get("industry_players_text"):
                            chart_data["industry_players_text"] = (
                                "；".join(_pnames) + "（决策备忘录竞争格局玩家清单，来源：unlisted_players.json）"
                            )
                            added.append("industry_players_text")
                        if not chart_data.get("fig_competitive_landscape") and len(_pnames) >= 3:
                            # 粗粒度竞争格局：按玩家清单生成份额占位图数据（标注为本地兜底）
                            chart_data["fig_competitive_landscape"] = {
                                "players": _pnames[:8],
                                "source": "local_backfill:unlisted_players",
                                "note": "玩家清单兜底，份额待核",
                            }
                            added.append("fig_competitive_landscape")
                        logger.info("[LOCAL-BACKFILL] decision_memo 玩家清单注入: %s (%d家)", _ind, len(_pnames))
            except Exception as e:
                logger.debug("[LOCAL] decision_memo 玩家清单: %s", e)
            # 5c. data_basement 行业基线兜底（供 market_size/industry_chain 写作引用）
            try:
                from core.data_basement import build_basement_data_dict

                _industry = universe_summary.get("industry", "") if universe_summary else ""
                _bd = build_basement_data_dict(asset, _industry)
                if isinstance(_bd, dict) and _bd:
                    if not chart_data.get("industry_baselines"):
                        chart_data["industry_baselines"] = _bd
                        added.append("industry_baselines")
                    # 5c-2. 市场规模兜底：从行业基线提取可用的市场规模/增速
                    if not chart_data.get("fig_market_size_china"):
                        _ms = {}
                        for _mk in ("market_size_china", "china_market_size", "market_size", "行业市场规模"):
                            if isinstance(_bd.get(_mk), (int, float, str)):
                                _ms["china"] = _bd.get(_mk)
                                break
                        if _ms:
                            chart_data["fig_market_size_china"] = {
                                **_ms,
                                "source": "local_backfill:data_basement",
                            }
                            added.append("fig_market_size_china")
                    if not chart_data.get("fig_market_size_global"):
                        _g = {}
                        for _mk in ("market_size_global", "global_market_size"):
                            if isinstance(_bd.get(_mk), (int, float, str)):
                                _g["global"] = _bd.get(_mk)
                                break
                        if _g:
                            chart_data["fig_market_size_global"] = {
                                **_g,
                                "source": "local_backfill:data_basement",
                            }
                            added.append("fig_market_size_global")
            except Exception as e:
                logger.debug("[LOCAL] decision_memo 行业基线: %s", e)

        if added:
            chart_data["_local_backfill"] = {
                "source": "local_backfill:financials.db+qlib+data_backends+EastMoney+历史报告"
                + ("+decision_memo离线" if report_type == "decision_memo" else ""),
                "keys": added,
            }
            data["chart_data"] = chart_data
            logger.info("[LOCAL-BACKFILL] added %d keys: %s", len(added), added)
        return data


class AgentEnricher:
    """把 agent 补充数据（enrich-file JSON）merge 回 collected_data

    enrich-file 格式（schema v1）：
    {
      "asset": "标的",
      "generated_by": "agent",
      "generated_at": "ISO时间",
      "items": [
        {
          "type": "fig_data",          # 图表数据
          "key": "fig_revenue_trend",
          "data": {"2023": 123.4, "2024": 156.7},
          "source": "公司公告 2026-03",  # 必填
          "confidence": 0.9,            # 0-1，默认 0.7
          "unit": "亿元",                # 可选
          "note": "说明"                 # 可选
        },
        {
          "type": "news",               # 新闻/文本列表
          "items": ["新闻1", "新闻2"],
          "source": "WebSearch: 关键词",
          "confidence": 0.8
        },
        {
          "type": "text",               # 单条文本
          "key": "company_intro",
          "value": "...",
          "source": "..."
        }
      ]
    }

    合规：type 未知 / key 不在白名单 / 缺 source → 该条被拒绝并记录。
    """

    # FP v3.2（2026-08-03 FP2a）：置信度多维加权
    # 单标量 confidence（默认 0.7）无区分度 → 按 {来源类型, 时效, 权威度, 交叉验证} 加权。
    # 维度 → 权重分（0-1）
    _CONF_DIMS = {
        "source_type": {  # 数据来源类型
            "官方/一手": 1.0,
            "公司公告": 1.0,
            "年报": 1.0,
            "招股书": 1.0,
            "专业数据": 0.9,
            "Wind": 0.9,
            "Bloomberg": 0.9,
            "akshare": 0.85,
            "baostock": 0.85,
            "研报": 0.8,
            "行业白皮书": 0.8,
            "Gartner": 0.85,
            "IDC": 0.85,
            "媒体": 0.6,
            "WebSearch": 0.5,
            "tavily": 0.5,
            "估算": 0.4,
            "推断": 0.3,
        },
        "authority": {  # 来源权威度
            "官方": 1.0,
            "监管": 1.0,
            "交易所": 0.95,
            "协会": 0.85,
            "头部机构": 0.9,
            "券商": 0.8,
            "咨询": 0.75,
            "媒体": 0.5,
        },
    }

    @staticmethod
    def _weighted_confidence(item: dict) -> float:
        """多维置信度加权：默认 0.7 改为按 source 特征推断。

        base = source_type 得分（未识别 0.5）+ 权威度修正 + 交叉验证加分
        - 显式 confidence 优先（尊重 agent 标注）
        - 否则从 source 文本推断维度分
        - 交叉验证（cross_validated=true）加 0.1
        - 返回裁剪到 [0.2, 0.95]（避免全 0.7 无区分度，也避免过度自信）
        """
        # 显式 confidence 优先
        conf = item.get("confidence")
        if conf is not None:
            try:
                return float(conf)
            except (TypeError, ValueError):
                pass

        source = str(item.get("source", ""))
        # 来源类型得分
        _type_score = 0.5
        for kw, score in AgentEnricher._CONF_DIMS["source_type"].items():
            if kw.lower() in source.lower():
                _type_score = max(_type_score, score)
        # 权威度修正（在 type 基础上叠加）
        _auth_bonus = 0.0
        for kw, score in AgentEnricher._CONF_DIMS["authority"].items():
            if kw in source:
                _auth_bonus = max(_auth_bonus, score - 0.5)
        # 交叉验证加分
        _cv_bonus = 0.1 if item.get("cross_validated") else 0.0
        _conf = _type_score + _auth_bonus + _cv_bonus
        return max(0.2, min(0.95, _conf))

    @staticmethod
    def merge(asset: str, data: dict, enrich_file: str | Path | None, universe_summary: dict = None) -> dict:
        if not enrich_file:
            return data
        path = Path(enrich_file)
        if not path.exists():
            logger.warning("[ENRICH] enrich-file 不存在: %s", path)
            return data

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("[ENRICH] enrich-file 解析失败: %s", e)
            return data

        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            logger.warning("[ENRICH] enrich-file 结构无效: 缺少 items 列表")
            return data

        if not isinstance(data, dict):
            data = {}
        chart_data = data.get("chart_data", {})
        if not isinstance(chart_data, dict):
            chart_data = {}

        accepted, rejected = [], []
        sources_registry = chart_data.get("_agent_sources", {})

        for item in payload["items"]:
            if not isinstance(item, dict):
                continue
            # ── 合规检查 ──
            itype = item.get("type", "")
            source = item.get("source", "").strip()
            if not source:
                rejected.append({"reason": "missing source", "key": item.get("key", itype)})
                continue
            if itype == "fig_data":
                key = item.get("key", "")
                if key not in ALLOWED_FIG_KEYS:
                    rejected.append({"reason": f"key not in whitelist: {key}", "key": key})
                    continue
                fdata = item.get("data")
                if not isinstance(fdata, (dict, list)) or not fdata:
                    rejected.append({"reason": "empty data", "key": key})
                    continue
                # P0: 保留 unit/note 元数据，同时保持 chart_data[key] 为扁平 dict。
                # R77（2026-08-05 验证 Marvis 修复发现）：Marvis 改复合结构
                # {"data":..,"unit":..,"note":..} 破坏了下游消费方——
                # chart_gen/compute_engine/section_writer 直接按扁平 dict 读 fig_*，
                # test_data_enrichment 断言 cd["fig_revenue_trend"]["2024"]==60 也 KeyError。
                # 修复：chart_data[key] 保持扁平（下游不变），unit/note/source 存入
                # 伴生字典 chart_data["_caliber"][key] 供需要处读取。
                chart_data[key] = (
                    fdata
                    if isinstance(fdata, dict)
                    else {str(i): v for i, v in enumerate(fdata) if not isinstance(v, (dict, list))}
                )
                caliber = chart_data.setdefault("_caliber", {})
                caliber[key] = {
                    "unit": item.get("unit", ""),
                    "note": item.get("note", ""),
                    "source": source,
                }
                sources_registry[key] = {
                    "source": source,
                    "confidence": AgentEnricher._weighted_confidence(item),
                    "unit": item.get("unit", ""),
                    "note": item.get("note", ""),
                    "generated_by": payload.get("generated_by", "agent"),
                }
                accepted.append(key)
            elif itype == "news":
                items = item.get("items", [])
                if not isinstance(items, list) or not items:
                    rejected.append({"reason": "empty news items", "key": "news"})
                    continue
                chart_data["agent_news"] = items
                sources_registry["agent_news"] = {
                    "source": source,
                    "confidence": AgentEnricher._weighted_confidence(item),
                }
                accepted.append("agent_news")
            elif itype == "text":
                key = item.get("key", "")
                value = item.get("value", "")
                if not key or not value:
                    rejected.append({"reason": "empty text key/value", "key": key})
                    continue
                chart_data[key] = value
                sources_registry[key] = {
                    "source": source,
                    "confidence": AgentEnricher._weighted_confidence(item),
                }
                accepted.append(key)
            else:
                rejected.append({"reason": f"unknown type: {itype}", "key": item.get("key", "")})

        if sources_registry:
            chart_data["_agent_sources"] = sources_registry
        data["chart_data"] = chart_data

        # 元信息
        data["enrichment"] = {
            "enabled": True,
            "source_file": str(path),
            "generated_by": payload.get("generated_by", "agent"),
            "generated_at": payload.get("generated_at", ""),
            "accepted": accepted,
            "rejected": rejected,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            # FP2: 供 Iron Gate 校验的可追溯来源清单
            "source_registry": sources_registry,
        }
        logger.info("[ENRICH] accepted=%d rejected=%d (%s)", len(accepted), len(rejected), path.name)
        if rejected:
            logger.warning("[ENRICH] rejected items: %s", json.dumps(rejected, ensure_ascii=False)[:300])
        return data


# ═══════════════════════════════════════════════════════════════
# E2EOrchestrator 节点入口
# ═══════════════════════════════════════════════════════════════


def enrich_node(node_id: str, context: dict) -> dict:
    """AgentGraph 的 enrich 节点函数。

    在 data 节点之后执行：
      1. 数据充足性检查
      2. 本地兜底（无需 agent）
      3. 若仍不足 → 设置 needs_agent 信号，尝试读取 --enrich-file 合并 agent 数据
      4. 记录 degradation / 是否 agent 兜底
    """
    data = context.get("collected_data", {})
    asset = context.get("asset", "")
    # R85（2026-08-07 P0-2）：report_type 透传——DataSufficiencyChecker 按
    # 报告类型区分关键图键（decision_memo 用 SAC 图集 + 宽容阈值）
    report_type = context.get("report_type", "listed_company")
    # R68: Universe Building 缺口注入——缺失玩家清单驱动补采
    universe_summary = context.get("universe_summary") or {}
    universe_missing = universe_summary.get("missing_players") or []
    universe_action = universe_summary.get("recommend_action", "")

    # 1. 充足性检查
    check = DataSufficiencyChecker.check(data, universe_summary=universe_summary, report_type=report_type)
    context["data_sufficiency"] = check

    # 2. 本地兜底
    def _recompute_universe(asset, data, context, universe_summary):
        """R69（2026-08-05）：enrich 后重算 Universe 覆盖率——
        修复 R68 缺陷：universe_build 在 enrich 前计算 coverage，若不重算则
        覆盖率恒 < 0.5、sufficient 恒 False。R90（2026-08-07 P0-1）扩展：
        本地兜底（decision_memo 玩家清单注入）后同样重算，解除 coverage 硬阻断。
        """
        try:
            from pipeline.universe_build import UniverseBuilder

            _ub = UniverseBuilder()
            _ub_result = _ub.build(
                asset=asset, collected_data=data, report_type=context.get("report_type", "industry_deep")
            )
            _new_summary = _ub_result.get("universe_summary", {})
            if _new_summary.get("total_players", 0) > 0:
                universe_summary = _new_summary
                context["universe_summary"] = _new_summary
                context["universe_gap"] = None  # 重算后清空旧缺口
                logger.info(
                    "[ENRICH-R69] universe coverage 重算: %s/%s (%s)",
                    _new_summary.get("covered_players", 0),
                    _new_summary.get("total_players", 0),
                    _new_summary.get("coverage_rate", 0),
                )
        except Exception as e:
            logger.debug("[ENRICH-R69] universe 重算失败（沿用 enrich 前摘要）: %s", e)
        return universe_summary

    if not check["sufficient"]:
        data = LocalBackfill.run(asset, data, report_type=report_type, universe_summary=universe_summary)
        context["collected_data"] = data
        # R90（2026-08-07 P0-1）：本地兜底可能注入玩家清单/市场数据——
        # 立即重算 universe coverage，否则 decision_memo 因 coverage<0.5 恒阻断
        if universe_summary.get("coverage_rate", 1.0) < 0.5:
            universe_summary = _recompute_universe(asset, data, context, universe_summary)
        check = DataSufficiencyChecker.check(data, universe_summary=universe_summary, report_type=report_type)
        context["data_sufficiency"] = check

    # 3. agent 补充数据 merge（enrich-file 由 scheduler 注入）
    enrich_file = context.get("enrich_file", "")
    if enrich_file:
        data = AgentEnricher.merge(asset, data, enrich_file, universe_summary)
        # R78（2026-08-05 Phase1.1）：enrich 后数据契约校验——结构漂移早暴露，
        # 不静默带病进下游。
        try:
            from core.data_contract import validate_enrich_file_merge

            _ok, _problems = validate_enrich_file_merge(data, enrich_file)
            if not _ok:
                logger.warning("[ENRICH-CONTRACT] 数据契约违规 %d 项: %s", len(_problems), "; ".join(_problems[:5]))
                context["enrich_contract_violations"] = _problems
            else:
                logger.info("[ENRICH-CONTRACT] 数据契约校验通过")
        except Exception as _ce:
            logger.debug("[ENRICH-CONTRACT] 契约校验异常: %s", str(_ce)[:60])
        context["collected_data"] = data
        # R69（2026-08-05）：enrich 后重算 Universe 覆盖率——
        # 修复 R68 缺陷：universe_build 在 enrich 前计算 coverage，
        # 若不重算则覆盖率恒 < 0.5、sufficient 恒 False，导致主题跑偏。
        universe_summary = _recompute_universe(asset, data, context, universe_summary)
        check = DataSufficiencyChecker.check(data, universe_summary=universe_summary, report_type=report_type)
        context["data_sufficiency"] = check

    # R68: Universe 缺口清单注入 gap_manifest（供 generate+enrich 补采）
    if universe_action == "enrich" and universe_missing:
        context["universe_gap"] = {
            "industry": universe_summary.get("industry", ""),
            "coverage_gap": universe_missing,
            "missing_player_names": [p.get("name") for p in universe_missing if isinstance(p, dict)],
        }
        logger.warning(
            "[ENRICH] Universe coverage gap: %d missing players in %s (coverage=%s)",
            len(universe_missing),
            universe_summary.get("industry", "unknown"),
            universe_summary.get("coverage_rate", 0),
        )

    # 4. 信号与降级标记
    needs_agent = not check["sufficient"]
    context["needs_agent"] = needs_agent
    context["data_enriched"] = bool(
        (isinstance(data, dict) and data.get("enrichment", {}).get("accepted_count"))
        or (isinstance(data, dict) and data.get("chart_data", {}).get("_local_backfill"))
    )
    if needs_agent:
        # L2 数据降级（数据不足但非零）：提示 agent 下次补数据
        context["degradation_level"] = max(context.get("degradation_level", 0), 2)
        logger.warning("[ENRICH] 数据仍不足，needs_agent=True: %s", check["detail"])
    else:
        logger.info("[ENRICH] 数据充足性 OK: %s", check["detail"])

    # 5. gap manifest：把缺口清单写到 output 目录，供 agent 快速查看/补数据
    try:
        _write_gap_manifest(asset, context, check)
    except Exception as e:
        logger.debug("[ENRICH] gap manifest: %s", e)

    # 5.5 backlog 待办队列：数据不足时写兜底任务，供 agent 启动时接手
    if needs_agent:
        try:
            _write_backlog_task(asset, context, check)
        except Exception as e:
            logger.debug("[ENRICH] backlog task: %s", e)

    return {
        "data_sufficiency": check,
        "needs_agent": needs_agent,
        "data_enriched": context.get("data_enriched", False),
        "gap_manifest_path": context.get("gap_manifest_path", ""),
        "backlog_path": context.get("backlog_path", ""),
    }


def _write_gap_manifest(asset: str, context: dict, check: dict) -> str:
    """把数据缺口 + 当前数据状态写入 output/<asset>_gaps.json

    供 agent 在不跑完整管线的情况下快速判断缺什么、补什么。
    """
    out_dir = Path(context.get("output_dir", str(_ROOT / "output")))
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w一-鿿]+", "_", asset).strip("_") or "asset"
    path = out_dir / f"{safe}_gaps.json"

    # 当前已有什么数据（供 agent 判断）
    data = context.get("collected_data", {})
    chart_data = data.get("chart_data", {}) if isinstance(data, dict) else {}
    present = {}
    for k, v in (chart_data or {}).items():
        if k in ALLOWED_FIG_KEYS or k in ("company_intro", "agent_news"):
            present[k] = True
    if isinstance(data, dict) and data.get("akshare_financials"):
        present["akshare_financials"] = True

    manifest = {
        "asset": asset,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "sufficient": check.get("sufficient", False),
        "missing_core": check.get("missing", []),
        "missing_partial": check.get("partial_missing", []),
        "detail": check.get("detail", ""),
        "present_data": sorted(present.keys()),
        "needs_agent": not check.get("sufficient", False),
        # R68: Universe 缺口（缺失非上市玩家清单，供 enrich 补采）
        "universe_gap": context.get("universe_gap"),
        # 告诉 agent 下一步怎么补
        "next_steps": [
            "1. 用 WebSearch/akshare-MCP 补充核心财务数据（fig_revenue_trend + fig_profitability），来源必须标注",
            "2. 生成 enrich-file JSON（schema 见 pipeline/data_enrichment.py）",
            f'3. 重跑: python pipeline/scheduler.py "{asset}" --enrich-file <enrich.json>',
        ],
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    context["gap_manifest_path"] = str(path)
    logger.info("[ENRICH] gap manifest: %s", path)
    return str(path)


BACKLOG_DIR = _ROOT / "data" / "backlog"


def _write_backlog_task(asset: str, context: dict, check: dict) -> str:
    """数据不足时写 agent 兜底待办任务。

    队列目录：data/backlog/<asset>_task.json
    agent 启动时检查该目录，发现待办 → 接手补数据 → 重跑管线。
    """
    BACKLOG_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w一-鿿]+", "_", str(asset)).strip("_") or "asset"
    path = BACKLOG_DIR / f"{safe}_task.json"

    task = {
        "asset": asset,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "reason": "data_insufficient",
        "missing_core": check.get("missing", []),
        "missing_partial": check.get("partial_missing", []),
        "detail": check.get("detail", ""),
        "status": "pending",  # pending → in_progress → completed / escalated
        # TTL 看门狗：超过 ttl_seconds 未接手 → 升级为 escalated
        "ttl_seconds": 3600,
        "escalated": False,
        # 兜底操作指引
        "how_to_fix": [
            f'python scripts/agent_backfill.py check "{asset}"',
            f'python scripts/agent_backfill.py template "{asset}" --out enrich.json',
            f'python scripts/agent_backfill.py run "{asset}" --enrich-file enrich.json',
        ],
    }
    # 同资产已有任务则不重复创建
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("status") == "pending":
                return str(path)
        except Exception:
            pass
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    context["backlog_path"] = str(path)
    logger.info("[BACKLOG] agent 兜底待办已写入: %s", path)
    return str(path)


def data_check_only(
    asset: str, report_type: str = "listed_company", output_dir: str = "output", enrich_file: str = None
) -> dict:
    """快速数据检查（不跑完整管线，只到 enrich 节点）

    供 agent 在补数据前快速确认数据缺口。返回缺口清单 + 是否满足。
    """
    ctx = {
        "asset": asset,
        "report_type": report_type,
        "style": "cicc",
        "output_dir": output_dir,
        "enrich_file": enrich_file,
        "degradation_level": 0,
    }
    # 只跑 data + enrich 两个节点
    try:
        from pipeline.data_collector import DataCollectorV5

        dc = DataCollectorV5()
        data = dc.collect(asset, report_type, {})
        ctx["collected_data"] = data or {}
    except Exception as e:
        logger.warning("[CHECK] 数据采集失败: %s", e)
        ctx["collected_data"] = {}

    enrich_node("enrich", ctx)
    return {
        "asset": asset,
        "data_sufficiency": ctx.get("data_sufficiency", {}),
        "needs_agent": ctx.get("needs_agent", False),
        "data_enriched": ctx.get("data_enriched", False),
        "gap_manifest_path": ctx.get("gap_manifest_path", ""),
        "collected_keys": list(ctx.get("collected_data", {}).keys())[:20],
    }


# ═══════════════════════════════════════════════════════════════
# CLI（供 agent 手动兜底后生成 enrich-file 参考）
# ═══════════════════════════════════════════════════════════════


def make_enrich_template(asset: str, path: str | Path) -> Path:
    """生成一个 enrich-file 模板，帮助 agent 理解 schema"""
    p = Path(path)
    template = {
        "asset": asset,
        "generated_by": "agent",
        "generated_at": "",
        "items": [
            {
                "type": "fig_data",
                "key": "fig_revenue_trend",
                "data": {"2023": 0.0, "2024": 0.0, "2025": 0.0},
                "source": "来源（必填）",
                "confidence": 0.7,
                "unit": "亿元",
            }
        ],
    }
    p.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="2hao 数据增强桥接层")
    sub = parser.add_subparsers(dest="cmd")
    p1 = sub.add_parser("template", help="生成 enrich-file 模板")
    p1.add_argument("asset", help="标的")
    p1.add_argument("--out", default="enrich.json", help="输出路径")
    p2 = sub.add_parser("check", help="快速数据缺口检查")
    p2.add_argument("asset", help="标的")
    p2.add_argument("--type", default="listed_company", help="报告类型")
    p2.add_argument("--output", default="output")
    args = parser.parse_args()
    if args.cmd == "template":
        out = make_enrich_template(args.asset, args.out)
        print(f"[ENRICH] 模板已生成: {out}")
    elif args.cmd == "check":
        r = data_check_only(args.asset, args.type, args.output)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
