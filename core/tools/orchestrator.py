"""工具编排器 - 统一调用所有分析工具

在SAC框架的每一步骤, 编排器决定调用哪些工具, 组合结果。

[R60 维护决策 2026-08-03]：本编排器当前 0 处主管线引用——5 个核心工具
（elasticity/signal_chain/moat/life_cycle/multi_model）已在 R59 直接接入
compute_engine._run_tool_modules，此处作为**工具初始化与组合的参考实现**保留，
便于未来扩展（如需按 SAC 步骤批量编排工具）。删除需经架构评审。
"""

import json

from core.tools.accounting_analyzer import AccountingAnalyzer
from core.tools.capital_flow_analyzer import CapitalFlowAnalyzer
from core.tools.decision_gate import DecisionGateBuilder
from core.tools.elasticity_analyzer import ElasticityAnalyzer
from core.tools.industry_chain_analyzer import IndustryChainAnalyzer
from core.tools.life_cycle_mapper import LifeCycleMapper
from core.tools.moat_analyzer import MoatAnalyzer
from core.tools.multi_model_validator import MultiModelValidator
from core.tools.policy_scorer import PolicyScorer
from core.tools.signal_chain import SignalChainBuilder
from core.tools.track_record import TrackRecordManager


class ToolOrchestrator:
    """工具编排器

    根据SAC步骤, 自动调用对应的分析工具, 输出结构化的分析上下文。
    """

    def __init__(self):
        self.elasticity = ElasticityAnalyzer()
        self.signal = SignalChainBuilder()
        self.life_cycle = LifeCycleMapper()
        self.moat = MoatAnalyzer()
        self.multi_model = MultiModelValidator()
        self.decision_gate = DecisionGateBuilder()
        self.capital_flow = CapitalFlowAnalyzer()
        self.industry_chain = IndustryChainAnalyzer()
        self.accounting = AccountingAnalyzer()
        self.policy_scorer = PolicyScorer()
        self.track_record = TrackRecordManager()

    def run_industry_tools(self, industry: str, report_type: str = "industry", **kwargs) -> dict[str, str]:
        """行业分析全工具"""
        results = {}

        # 1. 弹性分析
        try:
            ep = self.elasticity.full_analysis(
                industry=industry,
                gdp_growth=kwargs.get("gdp_growth"),
                industry_growth=kwargs.get("industry_growth"),
                market_structure=kwargs.get("market_structure", "competitive"),
            )
            results["elasticity"] = ep.summary()
            results["is_cyclical"] = str(ep.is_cyclical) if ep.is_cyclical is not None else "unknown"
        except Exception as e:
            results["elasticity"] = f"弹性分析跳过: {e}"

        # 2. 信号链
        try:
            chain = self.signal.build_chain(
                industry=industry,
                theme=kwargs.get("theme", "行业趋势判断"),
                driver=kwargs.get("driver", ""),
                decision=kwargs.get("decision", ""),
            )
            results["signal_chain"] = chain.summary()
            results["signal_chain_count"] = str(chain.total_count)
        except Exception as e:
            results["signal_chain"] = f"信号链跳过: {e}"

        # 3. 生命周期
        try:
            lc = self.life_cycle.analyze(
                industry=industry,
                stage=kwargs.get("stage", "成长期"),
                penetration_rate=kwargs.get("penetration_rate"),
                growth_rate=kwargs.get("growth_rate"),
                market_share_cr3=kwargs.get("market_share_cr3"),
            )
            results["life_cycle"] = lc.summary()

            # 周期股五条件
            cycle_check = self.life_cycle.get_cycle_stocks_five_conditions(
                industry=industry,
                price_level=kwargs.get("price_level", "中等"),
                industry_sentiment=kwargs.get("industry_sentiment", "正常"),
                demand_rigidity=kwargs.get("demand_rigidity", "中等"),
                supply_elasticity=kwargs.get("supply_elasticity", "中等"),
                catalyst=kwargs.get("catalyst", ""),
            )
            results["cycle_check"] = json.dumps(cycle_check, ensure_ascii=False, indent=2)
        except Exception as e:
            results["life_cycle"] = f"生命周期跳过: {e}"

        # 4. 多模型校验
        try:
            validator_menu = self.multi_model.get_model_menu()
            results["model_menu"] = validator_menu
        except Exception as e:
            results["model_menu"] = f"模型校验跳过: {e}"

        # 5. Decision Gate
        try:
            tree = self.decision_gate.build_tree(industry, "industry")
            results["decision_gates"] = tree.summary()
        except Exception as e:
            results["decision_gates"] = "Decision gate: " + str(e)

        # 6. Industry Chain
        try:
            chain = self.industry_chain.analyze(industry)
            results["industry_chain"] = chain.summary()
        except Exception as e:
            results["industry_chain"] = "Industry chain: " + str(e)

        # 7. Policy Score
        try:
            ps = self.policy_scorer.score_policy(
                industry,
                policy_direction=kwargs.get("policy_direction", "neutral"),
                execution_rate=kwargs.get("execution_rate", 0.5),
                subsidy_phase=kwargs.get("subsidy_phase", "mature"),
            )
            results["policy_score"] = ps.summary()
        except Exception as e:
            results["policy_score"] = "Policy score: " + str(e)

        # 8. Track Record
        try:
            tr = self.track_record.record.summary(industry)
            results["track_record"] = tr
        except Exception as e:
            results["track_record"] = "Track record: " + str(e)

        return results

    def run_company_tools(self, company: str, report_type: str = "listed_company", **kwargs) -> dict[str, str]:
        """公司分析全工具"""
        results = {}

        # 1. 护城河分析
        try:
            moat_data = kwargs.get("moat_data", {})
            if moat_data:
                profile = self.moat.assess(company, moat_data)
                results["moat"] = profile.summary()
            else:
                results["moat"] = "护城河数据未提供, 请在writing提示中要求分析师自行评估"
        except Exception as e:
            results["moat"] = f"护城河分析跳过: {e}"

        # 2. 杜邦分析
        try:
            if all(k in kwargs for k in ("roe", "profit_margin", "turnover", "leverage")):
                dupont = self.moat.get_dupond_analysis(
                    roe=kwargs["roe"],
                    profit_margin=kwargs["profit_margin"],
                    turnover=kwargs["turnover"],
                    leverage=kwargs["leverage"],
                )
                results["dupont"] = json.dumps(dupont, ensure_ascii=False, indent=2)
        except Exception as e:
            results["dupont"] = f"杜邦分析跳过: {e}"

        # 3. 多模型分歧校验
        try:
            if "consensus" in kwargs and "our_view" in kwargs:
                check = self.multi_model.check_disagreement(
                    consensus=kwargs["consensus"], our_view=kwargs["our_view"], report_type=report_type
                )
                results["multi_model_check"] = check.summary()
        except Exception as e:
            results["multi_model_check"] = f"多模型校验跳过: {e}"

        # 4. 格林沃德竞争优势
        try:
            gw = self.moat.greenwald_competitive_advantage(
                entry_barrier=kwargs.get("entry_barrier", "中"),
                customer_loyalty=kwargs.get("customer_loyalty", "中"),
                scale_economy=kwargs.get("scale_economy", "中"),
            )
            results["greenwald"] = json.dumps(gw, ensure_ascii=False, indent=2)
        except Exception as e:
            results["greenwald"] = f"格林沃德分析跳过: {e}"

        # 5. Decision Gate
        try:
            tree = self.decision_gate.build_tree(company, report_type)
            results["decision_gates"] = tree.summary()
        except Exception as e:
            results["decision_gates"] = "Decision gate: " + str(e)

        # 6. Accounting
        try:
            acct = self.accounting.analyze(company, kwargs.get("industry", ""))
            results["accounting"] = acct.summary()
        except Exception as e:
            results["accounting"] = "Accounting: " + str(e)

        # 7. Capital Flow
        try:
            cf = self.capital_flow.analyze_industry_flow(kwargs.get("industry", ""))
            results["capital_flow"] = cf.summary()
        except Exception as e:
            results["capital_flow"] = "Capital flow: " + str(e)

        # 8. Industry Chain
        try:
            chain = self.industry_chain.analyze(kwargs.get("industry", ""))
            results["industry_chain"] = chain.summary()
        except Exception as e:
            results["industry_chain"] = "Industry chain: " + str(e)

        # 9. Track Record
        try:
            tr = self.track_record.record.summary(kwargs.get("industry", ""))
            results["track_record"] = tr
        except Exception as e:
            results["track_record"] = "Track record: " + str(e)

        return results

    def get_tool_context_for_prompt(self, tools_output: dict[str, str], tool_types: list[str] = None) -> str:
        """生成用于注入writing prompt的工具上下文"""
        if tool_types is None:
            tool_types = list(tools_output.keys())

        parts = ["## 分析工具输出"]
        for k in tool_types:
            v = tools_output.get(k, "")
            if v:
                parts.append(f"\n### {k}\n{v}")
        return "\n".join(parts)
