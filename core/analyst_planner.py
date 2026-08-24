# -*- coding: utf-8 -*-
"""
分析方案规划器（Analyst Planner）— FP8 元认知选择层

**定位**：在 scheduler 前插入的"智能层"——决定用什么框架、聚焦哪些维度、如何降级。
产出 `analysis_plan` JSON（非报告正文，FP2 合规），管线按方案执行但不豁免 Gate。

**设计原则（FP8）**：
- 选择层负责"聪明"（用什么方法/聚焦什么），执行层负责"可靠"（过 Gate）
- 任何选择路径不豁免 IronGate / FP2a 数据溯源 / FP2b 反方论证
- 维度裁剪须数据驱动（有理由），非为省事砍维度
- 方法选择可解释（method_rationale 记录为什么选这个框架）

**与 report_planner 的关系**：report_planner（R28）生成"必答问题清单"（写什么）；
本模块生成"分析方案"（用什么框架/聚焦什么维度）。二者互补，本模块更上游。

用法：
    from core.analyst_planner import AnalystPlanner
    plan = AnalystPlanner().plan(asset="气体传感器", report_type="industry_deep",
                                  data_sufficiency={"sufficient": True}, industry_hint="传感器")
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.analyst_planner")

_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = _ROOT / "data" / "framework_registry.json"


def load_framework_registry() -> dict:
    """加载子框架注册表。"""
    if not REGISTRY_PATH.exists():
        logger.warning("[PLANNER] framework_registry.json 不存在，返回空注册表")
        return {"frameworks": [], "dimension_focus_rules": []}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("[PLANNER] registry 解析失败: %s", e)
        return {"frameworks": [], "dimension_focus_rules": []}


class AnalystPlanner:
    """分析方案规划器 — FP8 元认知选择。"""

    def __init__(self, registry: dict | None = None):
        self.registry = registry or load_framework_registry()
        self.frameworks = self.registry.get("frameworks", [])
        self.focus_rules = self.registry.get("dimension_focus_rules", [])

    # ── 框架选择 ─────────────────────────────────────────────
    def select_frameworks(self, report_type: str, data_sufficiency: dict | None,
                          industry_hint: str = "") -> list[dict]:
        """根据报告类型/数据充足度/行业线索选择适用的子框架组合。"""
        data_sufficiency = data_sufficiency or {}
        sufficient = bool(data_sufficiency.get("sufficient", True))
        semantic_gaps = data_sufficiency.get("semantic_gap", []) or []
        partial = data_sufficiency.get("missing_partial", []) or []
        # R81 修复：scheduler gaps.json 降级解析可能使 semantic_gap 为字符串（detail 兜底），
        # 归一化为 list，避免下方 (semantic_gaps or []) + (partial or []) 的 str+list 报错
        if isinstance(semantic_gaps, str):
            semantic_gaps = [semantic_gaps]
        if isinstance(partial, str):
            partial = [partial]

        # 数据充足度判定
        data_rich = sufficient and not semantic_gaps and not partial
        data_poor = bool(semantic_gaps) or bool(partial)

        selected = []
        # R81（2026-08-06）：数据不足不再一刀切排除框架——仅当框架的数据依赖类别
        # 与当前缺失清单（semantic_gaps/missing_partial）明确冲突时才跳过。
        _missing_txt = " ".join(str(x) for x in (semantic_gaps or []) + (partial or []))
        _DEP_KEYWORDS = ("产业链", "并购", "敏感性", "宏观", "价格", "信号",
                         "目标价", "预测", "调研", "估值", "高频")
        for fw in self.frameworks:
            cond = fw.get("适用条件", {})
            # 报告类型匹配
            if report_type not in cond.get("report_types", []):
                continue
            # 排除条件：exclude 命中的缺失类别与当前缺失清单有交集才排除
            excl = str(cond.get("exclude", ""))
            if data_poor and any(kw in excl and kw in _missing_txt for kw in _DEP_KEYWORDS):
                continue
            # 数据要求：rich 时全选；poor 时也保留框架（R81 框架应用强制），
            # 仅当 data_requirement 依赖的数据类别与缺失清单冲突时跳过。
            _req = str(cond.get("data_requirement", ""))
            if data_poor and "data_requirement" in cond and any(
                    kw in _req and kw in _missing_txt for kw in _DEP_KEYWORDS):
                continue
            score = fw.get("效果", {}).get("平均Gate分", 0.5)
            selected.append({
                "id": fw["id"], "名称": fw.get("名称", fw["id"]),
                "score": score,
                "reason": f"匹配 {report_type} + 数据充足度={ '充足' if data_rich else '受限'}",
            })
        # 按效果评分排序
        selected.sort(key=lambda x: x["score"], reverse=True)
        return selected[:4]  # 最多组合 4 个

    # ── 维度聚焦 ─────────────────────────────────────────────
    def focus_dimensions(self, report_type: str, data_sufficiency: dict | None,
                         all_dimensions: list[str] | None = None,
                         industry_hint: str = "") -> dict:
        """根据数据充足度决定维度聚焦：哪些重点、哪些精简。

        R78（2026-08-05 Phase4.4）：数据充足时注入行业×维度权重——
        权重高的维度进入 focus 前列（section_writer 优先深写），权重低的
        可能进入 slim。数据受限时仍走核心判断链裁剪（FP8-3）。
        """
        data_sufficiency = data_sufficiency or {}
        semantic_gaps = data_sufficiency.get("semantic_gap", []) or []
        partial = data_sufficiency.get("missing_partial", []) or []
        # R81 修复：semantic_gap 可能为字符串（scheduler detail 兜底），归一化为 list
        if isinstance(semantic_gaps, str):
            semantic_gaps = [semantic_gaps]
        if isinstance(partial, str):
            partial = [partial]
        data_poor = bool(semantic_gaps) or bool(partial)

        # 核心判断链维度（各报告类型都必需）——用 SAC 英文 ID（与权重表一致）
        core_dims = {
            "industry_deep": ["market_size", "competitive", "industry_chain", "profit_pool"],
            "listed_company": ["business_model", "financial_analysis", "valuation_assessment", "competitive_position"],
            "unlisted_company": ["business_model", "scarcity", "commercialization", "valuation"],
        }.get(report_type, [])

        all_dims = all_dimensions or core_dims
        if data_poor:
            focus = [d for d in all_dims if d in core_dims]
            slim = [d for d in all_dims if d not in core_dims]
            rationale = "数据受限：聚焦核心判断链，精简辅助维度（FP8-3 数据驱动裁剪）"
        else:
            # 数据充足：行业权重优先排列（高权重维度靠前 = 优先深写）
            # R78（2026-08-05 Phase4.4）：权重表键是 industry_deep 维度体系，
            # 只在 industry_deep 下生效；其他类型保持 SAC 原始顺序。
            weights = self._load_industry_weights(industry_hint) if report_type == "industry_deep" else {}
            if weights:
                def _w(dim_id):
                    return weights.get(dim_id, 5)  # 默认中权
                focus = sorted(all_dims, key=_w, reverse=True)
                rationale = "数据充足：全维度覆盖，按行业权重排序（FP3+FP8-4）"
            else:
                focus = list(all_dims)
                rationale = "数据充足：全维度覆盖（FP3 深度最大化）"
            slim = []
        return {"focus": focus, "slim": slim, "rationale": rationale}

    @staticmethod
    def _load_industry_weights(industry_hint: str = "") -> dict:
        """加载行业×维度权重（data/industry_dimension_weights.json）。

        industry_hint 命中行业键 → 返回该行业维度权重；
        未命中 → 返回空（fallback 全维度中权 5）。
        """
        try:
            import json
            p = Path(__file__).resolve().parent.parent / "data" / "industry_dimension_weights.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            for key in (industry_hint,):
                for k in data:
                    if key and (key in k or k in key):
                        return {k2: v for k2, v in data[k].items()}
            return {}
        except Exception:
            return {}

    # ── 降级策略 ─────────────────────────────────────────────
    def plan_degradation(self, data_sufficiency: dict | None) -> list[dict]:
        """根据数据缺口声明诚实降级策略。"""
        data_sufficiency = data_sufficiency or {}
        gaps = data_sufficiency.get("semantic_gap", []) or []
        partial = data_sufficiency.get("missing_partial", []) or []
        plan = []
        for g in gaps:
            plan.append({"维度": str(g), "策略": "估算标注 confidence=E，明确不可得", "FP依据": "FP2a 诚实标注"})
        for p in partial:
            plan.append({"维度": str(p), "策略": "缩小范围/标注数据不足，不硬凑", "FP依据": "FP8-4 诚实降级"})
        return plan

    # ── 主入口 ───────────────────────────────────────────────
    def plan(self, asset: str, report_type: str = "listed_company",
             data_sufficiency: dict | None = None,
             industry_hint: str = "") -> dict:
        """生成完整分析方案。"""
        frameworks = self.select_frameworks(report_type, data_sufficiency, industry_hint)
        # R78（2026-08-05 Phase4.4）：all_dimensions 从 SAC 读完整维度（非 core_dims 4 个）
        try:
            from core.sacs import SACLoader
            _all_dims = SACLoader(report_type).get_dimension_ids()
        except Exception:
            _all_dims = None
        focus = self.focus_dimensions(report_type, data_sufficiency,
                                      all_dimensions=_all_dims, industry_hint=industry_hint)
        degradation = self.plan_degradation(data_sufficiency)

        method_rationale = (
            f"标的={asset}, 类型={report_type}, 数据充足度="
            f"{'充足' if (data_sufficiency or {}).get('sufficient', True) else '受限'}。"
            f"选择框架={[f['id'] for f in frameworks]}，"
            f"理由={[f['reason'] for f in frameworks][:2]}。"
            f"维度聚焦={len(focus['focus'])}个核心, 精简={len(focus['slim'])}个。"
        )

        return {
            "asset": asset,
            "report_type": report_type,
            "frameworks": frameworks,
            "sac_focus": focus,
            "degradation": degradation,
            "method_rationale": method_rationale,
            "fp8_compliant": {
                "no_gate_exemption": True,
                "no_data_fabrication": True,
                "rationale_recorded": True,
            },
        }


def build_analysis_plan(asset: str, report_type: str = "listed_company",
                        data_sufficiency: dict | None = None,
                        industry_hint: str = "") -> dict:
    """便捷入口。"""
    return AnalystPlanner().plan(asset, report_type, data_sufficiency, industry_hint)


if __name__ == "__main__":
    import sys
    test_asset = sys.argv[1] if len(sys.argv) > 1 else "气体传感器"
    test_type = sys.argv[2] if len(sys.argv) > 2 else "industry_deep"
    plan = build_analysis_plan(test_asset, test_type)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
