"""会计穿透分析工具 — 四大会计事务所(KPMG/Deloitte/PwC/EY)方法论

超越表面财务数字, 穿透到会计政策层面:
1. 收入确认政策分析
2. 资本化 vs 费用化边界
3. 减值测试关键假设
4. 关联交易公允性
5. 表外负债与或有负债
6. 非经常性损益剔除

来源: 圆桌会议四大建议
"""

from dataclasses import dataclass, field


@dataclass
class AccountingPolicyFlag:
    """会计政策标记"""

    policy_name: str
    industry_practice: str  # 行业惯例
    company_practice: str  # 公司做法
    deviation: str  # 偏差分析: conservative/aggressive/standard
    risk_level: str  # 风险等级: high/medium/low
    impact_on_profit: str = ""  # 对利润的影响方向与幅度


@dataclass
class AccountingAnalysis:
    """会计穿透分析结果"""

    company: str = ""
    industry: str = ""
    flags: list[AccountingPolicyFlag] = field(default_factory=list)
    overall_quality: str = ""  # 会计质量: high/medium/low
    key_risks: list[str] = field(default_factory=list)
    earnings_quality_score: float = 0.0  # 盈利质量评分 0-10

    def summary(self) -> str:
        lines = [f"## 会计穿透分析: {self.company}"]
        lines.append(f"整体会计质量: {self.overall_quality}")
        lines.append(f"盈利质量评分: {self.earnings_quality_score}/10")
        lines.append("")
        for f in self.flags:
            icon = "!" if f.risk_level == "high" else "?" if f.risk_level == "medium" else "."
            lines.append(f"[{icon}] {f.policy_name}")
            lines.append(f"   公司做法: {f.company_practice}")
            lines.append(f"   行业惯例: {f.industry_practice}")
            lines.append(f"   偏差: {f.deviation} | 风险: {f.risk_level}")
            if f.impact_on_profit:
                lines.append(f"   利润影响: {f.impact_on_profit}")
        if self.key_risks:
            lines.append("\n关键风险:")
            for r in self.key_risks:
                lines.append(f"  - {r}")
        return "\n".join(lines)


class AccountingAnalyzer:
    """会计穿透分析引擎"""

    # 各行业典型会计政策风险点
    INDUSTRY_ACCOUNTING_RISKS = {
        "房地产": ["收入确认(预售vs完工)", "资本化利息", "存货减值", "联合营公司核算"],
        "医药": ["研发资本化率", "销售费用资本化", "商誉减值", "BD交易会计处理"],
        "TMT/软件": ["收入确认(SaaS/一次性)", "研发资本化", "用户获取成本资本化", "无形资产摊销"],
        "制造业": ["收入确认(时点vs时段)", "存货跌价准备", "固定资产折旧", "环保负债"],
        "金融": ["减值模型(预期信用损失)", "金融资产分类", "保险准备金", "表外风险敞口"],
        "零售/消费": ["收入确认(总额vs净额)", "退货准备", "积分/会员会计", "门店减值"],
        "新能源": ["补贴确认", "碳交易会计", "研发资本化率", "长期采购协议会计"],
    }

    def analyze(self, company: str, industry: str, policy_flags: list[dict] = None) -> AccountingAnalysis:
        """执行会计穿透分析"""
        analysis = AccountingAnalysis(company=company, industry=industry)

        risk_areas = self.INDUSTRY_ACCOUNTING_RISKS.get(industry, ["收入确认", "减值测试", "研发资本化"])

        if policy_flags:
            for f in policy_flags:
                analysis.flags.append(AccountingPolicyFlag(**f))
        else:
            # Default flags based on industry
            for area in risk_areas[:4]:
                analysis.flags.append(
                    AccountingPolicyFlag(
                        policy_name=area,
                        industry_practice=f"{area}: 行业标准做法(待核实)",
                        company_practice=f"{area}: 公司做法(待核实)",
                        deviation="待判断",
                        risk_level="medium",
                    )
                )

        # 计算整体评分
        high_risk = sum(1 for f in analysis.flags if f.risk_level == "high")
        medium_risk = sum(1 for f in analysis.flags if f.risk_level == "medium")
        total = len(analysis.flags)
        if total > 0:
            analysis.earnings_quality_score = 10 - (high_risk * 2.5 + medium_risk * 1.0) / total * 10
            analysis.earnings_quality_score = max(0, min(10, analysis.earnings_quality_score))

        analysis.overall_quality = (
            "high"
            if analysis.earnings_quality_score >= 8
            else "medium"
            if analysis.earnings_quality_score >= 5
            else "low"
        )

        if high_risk > 0:
            analysis.key_risks.append(f"{high_risk}项高风险会计政策需重点关注")
        if medium_risk > 2:
            analysis.key_risks.append(f"存在{medium_risk}项中等风险会计政策, 建议深入调查")

        return analysis

    def get_accounting_context_for_prompt(self, analysis: AccountingAnalysis) -> str:
        """生成会计分析上下文"""
        return analysis.summary()

    def check_accounting_in_report(self, report_text: str) -> dict[str, bool]:
        """检查报告中是否包含会计穿透分析"""
        import re

        checks = {
            "revenue_recognition": bool(re.search(r"收入确认|收入政策|收入准则", report_text)),
            "capitalization": bool(re.search(r"资本化|研发费用|费用化", report_text)),
            "impairment": bool(re.search(r"减值|商誉|减值测试", report_text)),
            "related_party": bool(re.search(r"关联交易|关联方", report_text)),
            "off_balance": bool(re.search(r"表外|或有负债", report_text)),
            "non_recurring": bool(re.search(r"非经常性损益|一次性收益", report_text)),
        }
        return checks
