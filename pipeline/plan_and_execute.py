"""Plan-and-Execute 编排器模块。

Phase 3: Plan-and-Execute 模式 + Human-in-the-loop 接口
"""
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger("2hao.plan_and_execute")


@dataclass
class ReportPlan:
    """报告计划"""
    asset: str
    report_type: str
    dimensions: list[dict]  # [{"id": "headline", "weight": 1.5, "focus": True}]
    estimated_time: int  # 预计耗时（秒）
    data_requirements: list[str]  # 数据需求
    user_feedback: Optional[str] = None  # 用户反馈


class PlanAndExecuteOrchestrator:
    """Plan-and-Execute 编排器"""

    def __init__(self, asset: str, report_type: str = "industry_deep", **kwargs):
        self.asset = asset
        self.report_type = report_type
        self.kwargs = kwargs
        self.plan: Optional[ReportPlan] = None

    def plan(self) -> ReportPlan:
        """规划阶段"""
        # 1. 意图解析
        intent = self._parse_intent()

        # 2. 生成报告大纲
        dimensions = self._generate_outline(intent)

        # 3. 估算时间
        estimated_time = self._estimate_time(dimensions)

        # 4. 生成数据需求
        data_requirements = self._identify_data_needs(dimensions)

        self.plan = ReportPlan(
            asset=self.asset,
            report_type=self.report_type,
            dimensions=dimensions,
            estimated_time=estimated_time,
            data_requirements=data_requirements,
        )

        return self.plan

    def execute(self, plan: ReportPlan = None) -> str:
        """执行阶段"""
        plan = plan or self.plan
        if not plan:
            raise ValueError("必须先调用 plan() 生成计划")

        # 1. 并行数据采集
        collected_data = self._collect_data_parallel(plan.data_requirements)

        # 2. 并行分析
        analysis_results = self._analyze_parallel(collected_data, plan.dimensions)

        # 3. 并行写作
        report_text = self._write_parallel(analysis_results, plan.dimensions)

        # 4. 合成
        final_report = self._synthesize(report_text)

        return final_report

    def review(self, report: str) -> tuple[bool, str]:
        """审查阶段"""
        # 1. Iron Gate 校验
        gate_result = self._validate(report)

        # 2. 如果失败，生成反馈
        if not gate_result.get("passed", False):
            feedback = self._generate_feedback(gate_result)
            return False, feedback

        return True, report

    def _parse_intent(self) -> dict:
        """解析意图"""
        return {
            "asset": self.asset,
            "report_type": self.report_type,
            "requirements": self.kwargs.get("requirements", ""),
        }

    def _generate_outline(self, intent: dict) -> list[dict]:
        """生成报告大纲"""
        from core.sacs import SACLoader

        sac = SACLoader(self.report_type)
        dimensions = sac.get_dimensions()

        # 为每个维度添加权重和焦点标记
        outline = []
        for dim in dimensions:
            if isinstance(dim, dict):
                outline.append({
                    "id": dim.get("id", ""),
                    "weight": 1.0,
                    "focus": False,
                })

        return outline

    def _estimate_time(self, dimensions: list[dict]) -> int:
        """估算耗时"""
        # 基础时间：数据采集 + 分析 + 写作
        base_time = 30 + 30 + 120  # 秒
        # 每个维度增加写作时间
        dim_time = len(dimensions) * 35
        return base_time + dim_time

    def _identify_data_needs(self, dimensions: list[dict]) -> list[str]:
        """识别数据需求"""
        # 基础数据需求
        needs = ["financial_data", "market_data"]

        # 根据维度添加特定数据需求
        for dim in dimensions:
            dim_id = dim.get("id", "")
            if "valuation" in dim_id:
                needs.append("valuation_data")
            if "competitive" in dim_id:
                needs.append("competitive_data")
            if "growth" in dim_id:
                needs.append("growth_data")

        return list(set(needs))

    def _collect_data_parallel(self, data_requirements: list[str]) -> dict:
        """并行数据采集"""
        # 简化实现：实际应调用数据采集模块
        collected = {}
        for req in data_requirements:
            collected[req] = {}  # 占位
        return collected

    def _analyze_parallel(self, collected_data: dict, dimensions: list[dict]) -> dict:
        """并行分析"""
        # 简化实现：实际应调用分析模块
        results = {}
        for dim in dimensions:
            dim_id = dim.get("id", "")
            results[dim_id] = {}  # 占位
        return results

    def _write_parallel(self, analysis_results: dict, dimensions: list[dict]) -> str:
        """并行写作"""
        # 简化实现：实际应调用写作模块
        return f"# {self.asset} 深度研究报告\n\n[待实现]"

    def _synthesize(self, report_text: str) -> str:
        """合成最终报告"""
        # 简化实现：实际应调用合成模块
        return report_text

    def _validate(self, report: str) -> dict:
        """验证报告"""
        # 简化实现：实际应调用 Iron Gate
        return {"passed": True, "score": 0.8}

    def _generate_feedback(self, gate_result: dict) -> str:
        """生成反馈"""
        # 简化实现
        return "报告需要改进"


class HumanInTheLoop:
    """人工审批节点"""

    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve

    def approve_plan(self, plan: ReportPlan) -> bool:
        """审批报告计划"""
        if self.auto_approve:
            return True

        # 生成计划摘要
        summary = self._format_plan_summary(plan)

        # 输出给用户
        print("\n" + "=" * 60)
        print("  报告计划审批")
        print("=" * 60)
        print(summary)
        print("=" * 60)

        # 等待用户输入
        response = input("\n是否继续执行？(y/n/修改建议): ")

        if response.lower() == 'y':
            return True
        elif response.lower() == 'n':
            return False
        else:
            # 用户提供修改建议
            plan.user_feedback = response
            return self.approve_plan(plan)  # 递归重新审批

    def approve_report(self, report: str) -> tuple[bool, str]:
        """审批报告初稿"""
        if self.auto_approve:
            return True, report

        print("\n" + "=" * 60)
        print("  报告初稿审批")
        print("=" * 60)
        print(report[:2000] + "..." if len(report) > 2000 else report)
        print("=" * 60)

        response = input("\n是否通过？(y/n/修改建议): ")

        if response.lower() == 'y':
            return True, report
        elif response.lower() == 'n':
            return False, report
        else:
            return False, response  # 返回修改建议

    def _format_plan_summary(self, plan: ReportPlan) -> str:
        """格式化计划摘要"""
        lines = [
            f"标的: {plan.asset}",
            f"报告类型: {plan.report_type}",
            f"维度数: {len(plan.dimensions)}",
            f"预计耗时: {plan.estimated_time}秒 ({plan.estimated_time // 60}分钟)",
            f"数据需求: {', '.join(plan.data_requirements)}",
        ]
        if plan.user_feedback:
            lines.append(f"用户反馈: {plan.user_feedback}")
        return "\n".join(lines)
