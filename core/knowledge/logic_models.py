# 西村克己 Logic Models - Thinking, Expression, Writing Logic
# Source: E:/9728/logic_models.md
# Core: MECE Pyramid, Logic Tree, Induction/Deduction, Matrix Analysis

from dataclasses import dataclass
from typing import List


@dataclass
class LogicAuditResult:
    mece_score: float  # MECE completeness
    logic_tree_depth: int  # Logic tree depth
    induction_used: bool  # Induction
    deduction_used: bool  # Deduction
    pyramid_principle: float  # Pyramid principle score
    matrix_count: int  # Matrix analysis count
    recommendations: List[str]


def audit_logic(text: str) -> LogicAuditResult:
    import re

    # MECE check: mutually exclusive, collectively exhaustive
    mece_kw = ["MECE", "相互独立", "完全穷尽", "分类", "维度"]
    mece_score = sum(1 for kw in mece_kw if kw in text) / len(mece_kw)

    # Logic tree check
    tree_kw = ["逻辑树", "问题树", "假设树", "决策树", "原因", "结果", "如果", "那么"]
    logic_depth = sum(1 for kw in tree_kw if kw in text)

    # Induction/Deduction
    induction = bool(re.search(r"归纳|从.*到.*|案例|经验|模式|规律|趋势", text))
    deduction = bool(re.search(r"演绎|大前提|小前提|结论|推理|必然", text))

    # Pyramid principle
    pyramid_kw = ["金字塔", "结论先行", "以上统下", "归类分组", "逻辑递进"]
    pyramid_score = sum(1 for kw in pyramid_kw if kw in text) / len(pyramid_kw)

    # Matrix analysis
    matrix_kw = ["矩阵", "二维", "象限", "坐标", "对比", "组合"]
    matrix_count = sum(1 for kw in matrix_kw if kw in text)

    recs = []
    if mece_score < 0.5:
        recs.append("建议使用MECE原则重新组织分析维度")
    if logic_depth < 3:
        recs.append("建议使用逻辑树展开因果链")
    if not deduction:
        recs.append("建议加入演绎推理(大前提->小前提->结论)")
    if pyramid_score < 0.3:
        recs.append("建议使用金字塔原理:结论先行,以上统下")
    if matrix_count < 2:
        recs.append("建议使用矩阵分析(如BCG矩阵/GE矩阵)进行多维度交叉")
    if not recs:
        recs.append("逻辑结构完整")

    return LogicAuditResult(
        mece_score=round(mece_score, 2),
        logic_tree_depth=logic_depth,
        induction_used=induction,
        deduction_used=deduction,
        pyramid_principle=round(pyramid_score, 2),
        matrix_count=matrix_count,
        recommendations=recs,
    )


def generate_writing_template(report_type: str) -> str:
    """Generate writing template based on logic models"""
    templates = {
        "industry_deep": chr(10).join(
            [
                "### [MECE Pyramid] 行业分析逻辑框架",
                "1. 结论先行: 核心判断(Bold Call)",
                "2. 以上统下: 稀缺层定位 > 利润迁移 > 竞争重构 > 市场空间",
                "3. 归类分组: 供给/需求/政策/技术/资本 五维并行",
                "4. 逻辑递进: 原因 -> 机制 -> 影响 -> 含义 -> 行动",
            ]
        ),
        "listed_company": chr(10).join(
            [
                "### [Logic Tree] 上市公司分析逻辑树",
                "1. 核心分歧定位(根节点)",
                "2. 分歧原因分支: 商业模式/财务验证/竞争位置/增长驱动",
                "3. 每层展开: 证据 -> 判断 -> 可信度",
                "4. 收敛到: 估值映射 + 证伪条件",
            ]
        ),
        "unlisted_company": chr(10).join(
            [
                "### [Matrix Analysis] 非上市企业分析矩阵",
                "1. 公司x行业矩阵: 定位公司在产业地图上的位置",
                "2. 估值三角矩阵: 三种估值方法的交叉验证",
                "3. 风险x回报矩阵: 不同情景下的回报分布",
            ]
        ),
    }
    return templates.get(report_type, templates["industry_deep"])


def check_writing_quality(text: str) -> dict:
    """Check writing quality against logic model standards"""
    import re

    issues = []
    # Check for conclusion-first
    if not re.search(r"核心判断|我们认为|Bold Call|核心观点", text[:500]):
        issues.append("前500字缺少核心判断(违反金字塔原理)")
    # Check for logic flow
    if not re.search(r"因此|这意味着|所以|引申", text):
        issues.append("缺少逻辑承接词(因果链不完整)")
    # Check So What chain
    if not re.search(r"因此建议|投资建议|操作策略|布局|关注", text):
        issues.append("缺少So What行动建议")
    return {"issues": issues, "quality": "pass" if len(issues) <= 1 else "needs_improvement"}
