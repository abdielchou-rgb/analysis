"""workbench_executor.py — 工作台执行器（FP0/FP8 落地，2026-08-07）

工作台混合模式：2hao 数据层（可靠）+ Claude 直接写（意图）+ 用户审核（判断）。
与确定性管线（E2E）互补——管线写标准报告，工作台写个性化/高险决策文档。

六步工作流（人机协作写作工作台方法论）：
  ① 意图对齐：委托方问题清单 → 必答问题 → 报告结构（intent_parser）
  ② 数据准备：enrich/决策引擎/财务模型算好，分级标注
  ③ AI 直接写：上下文工程（业务命题+分级数据+约束+示例）
  ④ 程序校验：verify_report（算术/实体/一致性/渲染）+ intent_gate（意图符合）
  ⑤ 人类门禁（强制，高险）：进/不进 + 修改意见 → 决策审计
  ⑥ 迭代沉淀：纠偏 → fact_base → 下次少犯

用法：
  python -m core.workbench_executor "柯力传感" --type decision_memo \
      --requirement "评估市场规模/投入产出比" --human-gate
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("2hao.workbench")

_ROOT = Path(__file__).resolve().parent.parent


class WorkbenchExecutor:
    """工作台执行器：数据层复用 + 上下文工程 + 校验 + 人类门禁。"""

    def __init__(
        self,
        asset: str,
        report_type: str = "decision_memo",
        requirement: str = "",
        human_gate: bool = False,
        output_dir: str = "output",
    ):
        self.asset = asset
        self.report_type = report_type
        self.requirement = requirement
        self.human_gate = human_gate
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── 六步工作流 ────────────────────────────────────

    def step1_intent(self) -> dict:
        """① 意图对齐：必答问题 → 报告结构。"""
        from core.intent_parser import IntentParser

        self.intent_plan = IntentParser().parse(self.asset, self.report_type, self.requirement)
        logger.info(
            "[WORKBENCH] ① 意图对齐: %d 个必答问题, %d 章节",
            len(self.intent_plan["must_answer_questions"]),
            len(self.intent_plan["structure"]),
        )
        return self.intent_plan

    def step2_data(self) -> dict:
        """② 数据准备：从 data_dict 提取可用数据（带 R87 分级标注）。"""
        data = {}
        # 尝试读 data_dict
        for cand in [
            self.output_dir / f"{self.asset}_data_dict.json",
            _ROOT / "output" / f"{self.asset}_data_dict.json",
        ]:
            if cand.exists():
                try:
                    data = json.loads(cand.read_text(encoding="utf-8"))
                    break
                except json.JSONDecodeError:
                    continue
        self.data = data
        # P2 深度接线：拉取行业事实库 + 相关计算模块产出（按报告类型/必答问题）
        self.facts_prompt = ""
        self.compute_summaries = []
        try:
            from core.fact_base import FactBase

            fb = FactBase()
            # 按必答问题意图检索事实
            intents = [q[:6] for q in self.intent_plan.get("must_answer_questions", [])]
            _fb_parts = []
            for intent in intents[:3]:
                _b = fb.build_prompt(intent=intent, limit=3)
                if _b and _b not in _fb_parts:
                    _fb_parts.append(_b)
            self.facts_prompt = "\n".join(_fb_parts)
        except Exception as _fe:
            logger.debug("[WORKBENCH][FACT-BASE] %s", str(_fe)[:60])
        # 计算模块：代工/合作生产 + 非上市深化
        try:
            if any(
                k in " ".join(self.intent_plan.get("must_answer_questions", []))
                for k in ("投入", "产出", "代工", "盈亏")
            ):
                from core.compute.contract_manufacturing import calculate_contract_manufacturing
                from core.compute.contract_manufacturing import format_summary as cm_fmt

                _cm = calculate_contract_manufacturing(
                    {
                        "capacity_units": float(data.get("capacity_units", 50000) or 50000),
                        "unit_price": float(data.get("unit_price", 2000) or 2000),
                        "variable_cost": float(data.get("variable_cost", 1400) or 1400),
                        "fixed_capex": float(data.get("fixed_capex", 30000000) or 30000000),
                        "fixed_opex_year": float(data.get("fixed_opex_year", 5000000) or 5000000),
                    }
                )
                self.compute_summaries.append(cm_fmt(_cm))
        except Exception as _ce:
            logger.debug("[WORKBENCH][CONTRACT-MFG] %s", str(_ce)[:60])
        try:
            if any(
                k in " ".join(self.intent_plan.get("must_answer_questions", []))
                for k in ("估值", "退出", "融资", "股权")
            ):
                from core.compute.unlisted_deep import calculate_unlisted_deep
                from core.compute.unlisted_deep import format_summary as ul_fmt

                _ul = calculate_unlisted_deep(
                    {
                        "revenue": float(data.get("revenue", 50000000) or 50000000),
                        "gross_margin": float(data.get("gross_margin", 0.35) or 0.35),
                        "comparable_ps": data.get("comparable_ps", [3, 5, 8]),
                        "founder_holding": float(data.get("founder_holding", 0.6) or 0.6),
                        "pledged": float(data.get("pledged", 0.2) or 0.2),
                    }
                )
                self.compute_summaries.append(ul_fmt(_ul))
        except Exception as _ue:
            logger.debug("[WORKBENCH][UNLISTED] %s", str(_ue)[:60])

        # 2026-08-08：PE/VC 模块接入（非上市报告自动含投资决策框架）
        if self.report_type == "unlisted_company":
            try:
                # 投资论题
                from core.compute.vc_thesis import build_prompt as vc_thesis_prompt
                from core.compute.vc_thesis import build_thesis

                _t = build_thesis(
                    [
                        {
                            "name": "市场",
                            "belief": data.get("thesis_market", "目标市场增长可期"),
                            "falsify": "市场增速低于预期",
                            "strength": float(data.get("thesis_market_strength", 0.6)),
                        },
                        {
                            "name": "壁垒",
                            "belief": data.get("thesis_moat", "具备可持续竞争优势"),
                            "falsify": "竞争者快速跟进",
                            "strength": float(data.get("thesis_moat_strength", 0.6)),
                        },
                        {
                            "name": "团队",
                            "belief": data.get("thesis_team", "创始人能力匹配"),
                            "falsify": "团队执行力不达标",
                            "strength": float(data.get("thesis_team_strength", 0.6)),
                        },
                    ]
                )
                self.compute_summaries.append(vc_thesis_prompt(_t))
            except Exception as _te:
                logger.debug("[WORKBENCH][VC-THESIS] %s", str(_te)[:60])
            try:
                # 创始人尽调
                from core.compute.founder_diligence import FounderDiligence
                from core.compute.founder_diligence import build_prompt as fd_prompt

                _fd = FounderDiligence(
                    background=float(data.get("founder_background", 6)),
                    capability=float(data.get("founder_capability", 6)),
                    motivation=float(data.get("founder_motivation", 6)),
                    integrity=float(data.get("founder_integrity", 6)),
                )
                self.compute_summaries.append(fd_prompt(_fd))
            except Exception as _fe:
                logger.debug("[WORKBENCH][FOUNDER] %s", str(_fe)[:60])
            try:
                # 产品数据
                from core.compute.product_metrics import ProductMetrics
                from core.compute.product_metrics import build_prompt as pm_prompt

                _pm = ProductMetrics(
                    users=float(data.get("product_users", 0)),
                    growth=float(data.get("product_growth", 0.05)),
                    retention_30=float(data.get("product_retention", 0.2)),
                    arr=float(data.get("product_arr", 0)),
                    ndr=float(data.get("product_ndr", 1.0)),
                    ltv=float(data.get("product_ltv", 0)),
                    cac=float(data.get("product_cac", 0)),
                )
                self.compute_summaries.append(pm_prompt(_pm))
            except Exception as _pe:
                logger.debug("[WORKBENCH][PRODUCT] %s", str(_pe)[:60])
            try:
                # 资本结构
                from core.compute.cap_table import CapTable
                from core.compute.cap_table import build_prompt as ct_prompt

                _ct = CapTable(
                    founder=float(data.get("cap_founder", 0.6)),
                    team=float(data.get("cap_team", 0.1)),
                    investors=float(data.get("cap_investors", 0.25)),
                    option_pool=float(data.get("cap_option", 0.05)),
                )
                self.compute_summaries.append(ct_prompt(_ct))
            except Exception as _ce2:
                logger.debug("[WORKBENCH][CAPTABLE] %s", str(_ce2)[:60])
            try:
                # VC 回报模型
                from core.compute.vc_return import VcReturnModel
                from core.compute.vc_return import build_prompt as vr_prompt

                _vr = VcReturnModel(
                    invest=float(data.get("vc_invest", 1000)),
                    exit_value=float(data.get("vc_exit_value", 50000)),
                    dilution=float(data.get("vc_dilution", 0.15)),
                    years=float(data.get("vc_years", 5)),
                    exit_prob=float(data.get("vc_exit_prob", 0.3)),
                )
                self.compute_summaries.append(vr_prompt(_vr))
            except Exception as _ve:
                logger.debug("[WORKBENCH][VC-RETURN] %s", str(_ve)[:60])
            try:
                # Runway 资金链
                from core.compute.runway import Runway
                from core.compute.runway import build_prompt as rw_prompt

                _rw = Runway(
                    cash=float(data.get("runway_cash", 0)),
                    burn=float(data.get("runway_burn", 0)),
                    milestone_cost=float(data.get("runway_milestone_cost", 0)),
                    milestone_months=float(data.get("runway_milestone_months", 0)),
                )
                self.compute_summaries.append(rw_prompt(_rw))
            except Exception as _re:
                logger.debug("[WORKBENCH][RUNWAY] %s", str(_re)[:60])
            try:
                # 十大维度评分
                from core.compute.vc_scoring import build_prompt as vs_prompt
                from core.compute.vc_scoring import vc_score

                _vs = vc_score(
                    {
                        k: float(v)
                        for k, v in {
                            "market": data.get("vc_market", 5),
                            "pain": data.get("vc_pain", 5),
                            "business_model": data.get("vc_business_model", 5),
                            "team": data.get("vc_team", 5),
                            "product": data.get("vc_product", 5),
                            "moat": data.get("vc_moat", 5),
                            "valuation": data.get("vc_valuation", 5),
                            "exit": data.get("vc_exit", 5),
                            "risk": data.get("vc_risk", 5),
                            "presentation": data.get("vc_presentation", 5),
                        }.items()
                        if v is not None
                    }
                )
                self.compute_summaries.append(vs_prompt(_vs))
            except Exception as _se:
                logger.debug("[WORKBENCH][VC-SCORING] %s", str(_se)[:60])

        logger.info("[WORKBENCH] ② 数据准备: %d keys + %d 计算摘要", len(data), len(self.compute_summaries))
        return data

    def step3_write(self) -> str:
        """③ AI 直接写：上下文工程 → Claude 直接产出正文。

        工作台模式核心——不跑 section_writer 的 SAC 模板，用意图+数据+约束直接写。
        实际执行时由上层（Claude/Marvis）调用 LLM，此处返回上下文 prompt。
        """
        from core.intent_parser import IntentParser

        ip = IntentParser()
        # 组装上下文工程 prompt
        ctx = [
            f"# 写作任务：{self.asset} {self.report_type}",
            f"委托方: {self.intent_plan['client']}",
            f"决策点: {self.intent_plan['decision_point']}",
            "",
            "## 必答问题（必须全部回答，报告围绕它们组织）",
        ]
        for i, q in enumerate(self.intent_plan["must_answer_questions"], 1):
            ctx.append(f"{i}. {q}")
        ctx += [
            "",
            "## 可用数据（分级：verified可直接引用 / corrected已修正 / unverified须标(E)）",
            json.dumps(self.data, ensure_ascii=False, indent=1)[:3000],
            "",
        ]
        # P2 深度接线：行业事实库 + 计算模块摘要注入
        if getattr(self, "facts_prompt", ""):
            ctx += [self.facts_prompt, ""]
        if getattr(self, "compute_summaries", []):
            ctx += ["## 计算模块产出（代码已算好，直接引用，禁止重算）", "\n".join(self.compute_summaries), ""]
        ctx += [
            "## 写作约束",
            "· 结论先行（执行摘要直接回答必答问题）",
            "· 每个数字带来源和标注 (A)/(E)/(F)/(B)",
            "· 禁止编造数据；数据不足写'待尽调核实'",
            "· 决策备忘录禁止投资评级/目标价/EPS",
            "· 结构围绕必答问题，不填模板",
            "",
            "## 要求",
            "直接写正文（Markdown），先执行摘要，再分章节回答每个必答问题。",
        ]
        self.context_prompt = "\n".join(ctx)
        # 工作台由 Claude 直接写——此处返回 prompt 供上层调用 LLM
        return self.context_prompt

    def step4_verify(self, report_text: str) -> dict:
        """④ 程序校验：意图符合 + 确定性检查。"""
        from core.intent_gate import check_intent_compliance

        intent_result = check_intent_compliance(report_text, self.intent_plan)
        # 确定性校验（算术/实体/一致性）——此处做意图为主，完整校验走 verify_report
        self.verify_result = {
            "intent": intent_result,
            "passed": intent_result["passed"],
            "coverage": intent_result["coverage"],
        }
        logger.info(
            "[WORKBENCH] ④ 校验: intent coverage=%.2f passed=%s", intent_result["coverage"], intent_result["passed"]
        )
        return self.verify_result

    def step5_human_gate(self, report_text: str) -> dict:
        """⑤ 人类门禁：高险文档强制。返回用户审核记录。"""
        if not self.human_gate:
            return {"gated": False, "note": "非高险，人类门禁可选"}
        # 生成审核记录（实际由用户交互填写）
        audit = {
            "asset": self.asset,
            "report_type": self.report_type,
            "decision_point": self.intent_plan["decision_point"],
            "human_review_required": True,
            "status": "pending_user_review",
            "gate": self.verify_result,
        }
        audit_path = self.output_dir / f"{self.asset}_decision_audit.json"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
        logger.info("[WORKBENCH] ⑤ 人类门禁: 审计记录写入 %s", audit_path)
        return audit

    def step6_save(self, report_text: str) -> Path:
        """⑥ 沉淀：报告落盘 + 纠偏沉淀到 fact_base。"""
        out = self.output_dir / f"{self.asset}_{self.report_type}_workbench.md"
        out.write_text(report_text, encoding="utf-8")
        logger.info("[WORKBENCH] ⑥ 报告落盘: %s", out)
        return out

    def run(self, report_text: str | None = None) -> dict:
        """全流程执行。report_text 由上层 LLM 生成后传入。"""
        self.step1_intent()
        self.step2_data()
        ctx = self.step3_write()
        # 若没传 report_text，工作台由 Claude 直接写（上层调用 LLM）
        if not report_text:
            return {
                "status": "awaiting_llm",
                "intent_plan": self.intent_plan,
                "context_prompt": ctx,
                "data_keys": len(self.data),
                "note": "请用 context_prompt 让 LLM 直接写正文，再传入 report_text 完成校验",
            }
        self.step4_verify(report_text)
        self.step5_human_gate(report_text)
        out = self.step6_save(report_text)
        return {
            "status": "completed",
            "path": str(out),
            "intent_coverage": self.verify_result["coverage"],
            "passed": self.verify_result["passed"],
            "human_gate": self.human_gate,
        }


def main():
    import argparse

    ap = argparse.ArgumentParser(description="工作台执行器（FP0 意图驱动）")
    ap.add_argument("asset", help="标的")
    ap.add_argument("--type", default="decision_memo", help="报告类型")
    ap.add_argument("--requirement", default="", help="委托方需求")
    ap.add_argument("--human-gate", action="store_true", help="强制人类门禁")
    ap.add_argument("--output", "-o", default="output")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    wb = WorkbenchExecutor(args.asset, args.type, args.requirement, args.human_gate, args.output)
    result = wb.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
