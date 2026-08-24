# -*- coding: utf-8 -*-
"""content_precheck.py — 内容包预检（P2-1，2026-08-07）

治"空维硬写幻觉"：写正文前先统计每 SAC 维度的数据充足度，空维降级/合并，
不硬写（诚实留白优于伪造）。

用法：
  checker = ContentPrechecker()
  report = checker.check(collected_data, sac_dims)   # 每维打充足度
  verdict = checker.decide(report)                    # 降级/精简/全写仲裁

仲裁规则（圆桌批判 F2 修订）：
  - 充足度 < 0.3 → 降级（诚实留白，禁止硬写）
  - 0.3-0.6     → 精简（只写有数据的子项）
  - > 0.6       → 全写
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("2hao.content_precheck")


class ContentPrechecker:
    """按 SAC 维度评估数据充足度，输出每维分级与降级建议。"""

    # 数据充足度的代理指标：collected_data / data_dict 中该维度相关键的覆盖率
    # 维度名 → 数据键模式（子串匹配）
    DIM_KEY_HINTS = {
        "founder_ri": ["founder", "股权", "实控", "质押"],
        "milestone": ["里程碑", "milestone", "产能", "扩产", "项目进度"],
        "industry_chain": ["产业链", "上游", "下游", "供应商", "客户"],
        "market_size": ["市场规模", "market_size", "渗透率", "space"],
        "competition": ["竞争", "市占率", "份额", "competitor", "同行"],
        "financial": ["营收", "净利", "毛利率", "ROE", "负债", "现金流", "balance", "cashflow",
                      "revenue", "net_profit", "profit", "margin", "income", "asset", "debt"],
        "valuation": ["PE", "PS", "DCF", "估值", "目标价", "市值", "market_cap", "target_price",
                      "fair_value", "eps", "pricing"],
        "policy": ["政策", "regulation", "监管", "合规"],
        "technology": ["专利", "研发", "R&D", "技术路线", "卡脖子"],
        "risk": ["风险", "不确定性", "downside"],
        "management": ["管理层", "高管", "治理", "ESG"],
        "scarcity": ["稀缺", "卡点", "bottleneck", "环节"],
    }

    # 阈值
    DEGRADE_THRESHOLD = 0.3   # 低于 → 降级
    FULL_THRESHOLD = 0.6      # 高于 → 全写

    def check(self, data: dict, dims: list[str]) -> dict:
        """为每个维度返回充足度评分 0-1 与缺失提示。"""
        if not isinstance(data, dict):
            data = {}
        flat = self._flatten(data)
        report = {}
        for dim in dims:
            hints = self.DIM_KEY_HINTS.get(dim, [])
            if not hints:
                # 无提示词的维度：默认 0.5（未知，交给 LLM 判断）
                report[dim] = {"score": 0.5, "present": [], "missing": []}
                continue
            present = [h for h in hints if any(h.lower() in str(k).lower() for k in flat.keys())]
            score = len(present) / len(hints)
            missing = [h for h in hints if h not in present]
            report[dim] = {"score": round(score, 2), "present": present, "missing": missing}
        return report

    def decide(self, report: dict) -> dict:
        """按阈值仲裁每维：degrade / slim / full。"""
        verdict = {}
        for dim, r in report.items():
            score = r.get("score", 0.5)
            if score < self.DEGRADE_THRESHOLD:
                verdict[dim] = "degrade"
            elif score < self.FULL_THRESHOLD:
                verdict[dim] = "slim"
            else:
                verdict[dim] = "full"
        return verdict

    def build_prompt(self, verdict: dict, report: dict) -> str:
        """生成给 section_writer 的内容包预检指令。"""
        lines = ["=== 内容包预检（数据充足度驱动，防空维硬写）==="]
        for dim, mode in verdict.items():
            r = report.get(dim, {})
            if mode == "degrade":
                lines.append(
                    f"- {dim}: 数据不足(score={r.get('score', 0)}), 降级处理——"
                    f"只写已有数据的子项, 其余明确写'数据有限/待尽调核实', 禁止编造")
            elif mode == "slim":
                lines.append(
                    f"- {dim}: 数据部分(score={r.get('score', 0)}), 精简——只写有数据的点, 不铺开")
            else:
                lines.append(f"- {dim}: 数据充足(score={r.get('score', 0)}), 正常展开")
        return "\n".join(lines)

    @staticmethod
    def _flatten(data: dict, prefix: str = "") -> dict:
        """扁平化嵌套 dict（key 用 . 连接），便于子串匹配。"""
        out = {}
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(ContentPrechecker._flatten(v, key))
            else:
                out[key] = v
        return out


def run_content_precheck(data: dict, dims: list[str]) -> Optional[str]:
    """便捷入口：返回内容包预检 prompt（无数据/无维度时返回 None）。"""
    if not dims:
        return None
    checker = ContentPrechecker()
    report = checker.check(data, dims)
    verdict = checker.decide(report)
    return checker.build_prompt(verdict, report)
