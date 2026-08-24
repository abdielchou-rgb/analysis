"""relation_gate.py — 身份关系检测（2026-08-08 久通控股事故落地）

检测"分析对象身份错位"：标的是委托方子公司/关联方，但报告按"外部合作方"框架分析。

油位事故：久通物联是柯力传感控股子公司，但报告全程按"外部合作方"写
（谈判/签约/绑定/防换供应商），衍生了高盛"代工+股权绑定"等矫枉过正。

本 gate 检测外部关系词与内部关系词：
  外部关系词（谈判/签约/绑定/防换供应商/获取渠道/外部甲方）出现
  + 标的声明为子公司/关联方 → warning：身份可能错位

用法：
  from core.relation_gate import check_relation_consistency
  r = check_relation_consistency(report_text, asset_relation="subsidiary")
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("2hao.relation_gate")

# 外部合作框架词（若标的是子公司却出现这些 → 身份错位信号）
EXTERNAL_RELATION_WORDS = [
    "签约",
    "签署协议",
    "绑定",
    "防换供应商",
    "更换供应商",
    "获取渠道",
    "渠道许可",
    "谈判",
    "合作方",
    "甲方",
    "乙方",
    "股权绑定",
    "认股权",
    "可转债",
    "外部尽调",
]

# 内部整合框架词（正常应出现的）
INTERNAL_RELATION_WORDS = [
    "控股子公司",
    "子公司",
    "并表",
    "集团",
    "内部整合",
    "统筹",
    "少数股东",
    "内部交易",
    "集团内部",
    "整合",
    "协同",
]

# 内部关系类型
RELATION_TYPES = {"subsidiary", "associate", "parent", "group", "sibling"}


def check_relation_consistency(report_text: str, asset_relation: str = "") -> dict:
    """检测报告是否把子公司/关联方当外部合作方。

    Args:
        report_text: 报告正文
        asset_relation: 标的关系类型（subsidiary/associate/...），空则自动推断
    """
    text = report_text or ""

    # 否定性表述豁免：外部词前有"无/无需/不存在/不是/避免/防止"等否定/规避前缀 → 不计为外部框架
    def _is_negated(word, pos):
        window = text[max(0, pos - 12) : pos]
        return any(neg in window for neg in ("无", "无需", "不存在", "不是", "避免", "防止", "不", "无外部"))

    external_hits = []
    for w in EXTERNAL_RELATION_WORDS:
        for m in re.finditer(re.escape(w), text):
            if not _is_negated(w, m.start()):
                external_hits.append(w)
                break
    internal_hits = [w for w in INTERNAL_RELATION_WORDS if w in text]

    # 推断关系：若报告自己声明"控股子公司/子公司/并表" → subsidiary
    inferred = asset_relation
    if not inferred:
        if "控股子公司" in text or "并表" in text:
            inferred = "subsidiary"
        elif "子公司" in text:
            inferred = "subsidiary"
        elif "关联方" in text or "关联交易" in text:
            inferred = "associate"

    issues = []
    # 若标的是子公司，但出现大量外部合作词且少内部整合词 → 身份错位
    if inferred == "subsidiary" or inferred == "associate":
        ext_count = len(external_hits)
        if ext_count >= 2:
            # 看是否有内部整合表述平衡
            balance = "内部整合" in text or "统筹" in text or "整合" in text or "集团" in text
            issues.append(
                {
                    "type": "relation_misalignment",
                    "severity": "warning" if balance else "error",
                    "external_hits": external_hits[:5],
                    "internal_hits": internal_hits[:5],
                    "inferred_relation": inferred,
                    "issue": f"标的推断为{inferred}，但报告出现 {ext_count} 处外部合作框架词"
                    f"（{', '.join(external_hits[:3])}）"
                    + (
                        "，虽有内部整合表述但需确认"
                        if balance
                        else "——若标的是子公司，应按集团内部整合视角分析，而非外部合作谈判"
                    ),
                }
            )

    return {
        "passed": not any(i["severity"] == "error" for i in issues),
        "inferred_relation": inferred,
        "external_hits": external_hits,
        "internal_hits": internal_hits,
        "issues": issues,
    }


def relation_gate_node(node_id: str, context: dict) -> dict:
    """IronGate 集成节点。"""
    text = context.get("final_text") or context.get("report_text", "")
    if not text:
        return {"relation_passed": True}
    try:
        asset = context.get("asset", "")
        relation = context.get("asset_relation", "")  # 可注入
        result = check_relation_consistency(text, relation)
        context["relation_gate_result"] = result
        logger.info(
            "[RELATION-GATE] inferred=%s passed=%s ext=%d",
            result["inferred_relation"],
            result["passed"],
            len(result["external_hits"]),
        )
        return {
            "relation_passed": result["passed"],
            "relation_errors": sum(1 for i in result["issues"] if i["severity"] == "error"),
            "inferred_relation": result["inferred_relation"],
        }
    except Exception as e:
        logger.debug("[RELATION-GATE] %s", str(e)[:60])
        return {"relation_passed": True}
