"""S6-3: 免责合规条款自动生成

按报告类型自动附加合规免责（替换现在 LLM 生成的免责）。
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

CLAUSES: dict[str, str] = {
    "listed_company": (
        "免责声明：本报告基于公开信息编制，所引用数据来源于公司公告、"
        "交易所披露及第三方数据服务商。报告中的分析和观点仅代表研究团队"
        "在报告发布日期的判断，不构成任何投资建议或承诺。投资者应独立"
        "做出投资决策并自行承担投资风险。过往业绩不代表未来表现。"
    ),
    "unlisted_company": (
        "免责声明：本报告基于公开资料及尽职调查信息编制，估值模型涉及"
        "多项假设，实际结果可能与预测存在重大差异。报告中的分析和观点"
        "仅代表研究团队在报告发布日期的判断，不构成任何投资建议或承诺。"
        "非上市公司信息透明度有限，投资者应充分关注相关风险。"
    ),
    "earnings_notes": (
        "免责声明：本报告基于公司已披露的财务数据编制，所引用数据以"
        "公司公告为准。报告中的分析和观点仅代表研究团队在报告发布日期"
        "的判断，不构成任何投资建议。投资者应结合自身情况独立判断。"
    ),
    "industry_deep": (
        "免责声明：本报告基于公开信息和行业数据编制，行业预测受宏观"
        "经济、政策变化、技术进步等多重因素影响，实际发展可能与预测"
        "存在差异。报告中的分析和观点仅代表研究团队在报告发布日期的"
        "判断，不构成任何投资建议或行业推荐。"
    ),
    "decision_memo": (
        "免责声明：本备忘录为内部决策参考材料，基于截至报告日期的"
        "可获取信息编制，仅供内部讨论使用，不对外披露。备忘录中的"
        "分析和建议不构成最终决策依据，决策者应综合多方信息做出判断。"
    ),
    "valuation": (
        "免责声明：本报告中的估值结果基于多项假设和模型参数，实际价值"
        "可能因市场环境、经营状况等因素变化而与估值结果存在重大差异。"
        "估值结果仅供参考，不构成买卖建议。"
    ),
}

DEFAULT_CLAUSE = (
    "免责声明：本报告基于公开信息编制，分析和观点仅代表研究团队"
    "在报告发布日期的判断，不构成任何投资建议。投资者应独立判断。"
)


def get_clause(report_type: str) -> str:
    """获取指定报告类型的合规条款。"""
    return CLAUSES.get(report_type, DEFAULT_CLAUSE)


def inject_compliance_footer(report_text: str, report_type: str) -> str:
    """在报告尾部注入合规条款（如尚未包含）。"""
    clause = get_clause(report_type)

    # 检查是否已有免责声明
    if "免责声明" in report_text and clause[:20] in report_text:
        return report_text

    footer = f"\n\n---\n\n{clause}\n"
    return report_text + footer


def main():
    for rt in CLAUSES:
        print(f"[{rt}] {CLAUSES[rt][:50]}...")


if __name__ == "__main__":
    main()
