"""失败段定位 — R78 Phase3.1 拆分上帝模块。

从 e2e_orchestrator.py 抽出的 _locate_failed_segments（103 行模块级函数），
保持行为不变。主文件 import 并转发，测试兼容。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("2hao.e2e.fail_locator")


def locate_failed_segments(context: dict, sw) -> list | None:
    """R13 Phase4 + R26 强化：从 gate 反馈定位要重写的段索引。

    处理三类失败（R26 修复缺陷3 打地鼠）：
      1. SAC 维度缺失 → 定位到所属段（原逻辑）
      2. 图表完整性（chart_completeness/图嵌入）→ 全局问题，返回 None 触发全写
         （图表嵌入是全文性的，无法定位到单段；全写 + 护栏 prompt 才能补图引用）
      3. COMPLIANCE（核心分歧/合规）→ 定位到判断段（bold_call/core_disagreement 所属段）
    同时把失败类型写回 context['_gate_fail_types']，供 section_writer 决定重写策略。
    """
    import re as _re

    fb = context.get("gate_feedback", "")
    if not fb:
        return None
    seg_map = {}  # dimension_id -> segment index
    for i, s in enumerate(sw.segments):
        for d in s.get("dimension_ids", []):
            seg_map[d] = i
    indices = set()
    fail_types = []

    # 1. SAC 维度缺失 → 定位段
    m = _re.search(r"\[必需维度缺失=([^\]]+)\]", fb)
    if m:
        dims = [x.strip() for x in m.group(1).split(",")]
        for dim in dims:
            if dim in seg_map:
                indices.add(seg_map[dim])
        if dims:
            fail_types.append("sac_dims")

    # 2. 图表完整性（chart_completeness / 图嵌入）
    # R66（2026-08-04）修复：图表失败不再短路全量重写。
    # 旧逻辑 return None 触发全量重写 → 每轮重新掷骰子（柯力 0.81→0.80→0.77 退化）。
    # 改为：标记 charts 失败类型 + 定位全部段，让 section_writer 补图引用（局部重写）。
    # 图表引用缺失本质是"每段都该嵌图"→ 全段局部重写比全量重写更保收敛。
    if _re.search(r"(chart_completeness|图嵌入|图表不足|charts)", fb):
        fail_types.append("charts")
        context["_gate_fail_types"] = fail_types
        if sw.segments:
            all_seg = list(range(len(sw.segments)))
            logger.info("[REVISE-LOCAL] 图表类失败 → 全段局部重写补图引用（非全量，保收敛）")
            return all_seg
        return None

    # 3. COMPLIANCE 核心分歧 / Bold Call / 说服力架构
    # R67（2026-08-04）：加 persuasion_architecture（说服力架构）——此前该失败项
    # 不在正则里，既不定位段也不触发局部修订，只能靠全量重写（柯力 12/13 三轮不变）。
    if _re.search(r"(核心分歧|bold_call|合规|compliance|说服力架构|persuasion_architecture|反方观点)", fb):
        fail_types.append("compliance")
        # 定位到 bold_call / core_disagreement 段
        for dim in ("bold_call", "core_disagreement"):
            if dim in seg_map:
                indices.add(seg_map[dim])
        # 若没定位到，靠段 label 匹配
        for i, s in enumerate(sw.segments):
            label = str(s.get("label", ""))
            if "判断" in label or "核心" in label or "分歧" in label or "共识" in label:
                indices.add(i)

    # 4. 通用：feedback 提到段 label
    for i, s in enumerate(sw.segments):
        label = str(s.get("label", ""))
        if label[:4] in fb:
            indices.add(i)

    # 5. R51（2026-08-02 收敛机制）：全局质量失败——无法定位到单段，须全量重写。
    #    这些失败本质是"报告整体问题"（文字深度/格式/一致性），不是某段缺失。
    #    触发全量重写 + 记录 fail_type，让 section_writer 知道是全局问题。
    #    不牺牲质量：全量重写时 prompt 明确失败原因，避免盲目重写。
    # R77（2026-08-06 P0）：归因正则收窄——"口径"误匹配 market_size_consistency，
    #   "来源标注"误匹配 source_entity。去掉宽泛词，保留精确匹配。
    #   data_conflicts 只匹配 data_conflicts/数据字典冲突，annotation_types 只匹配
    #   annotation_types/标注类型，新增 market_size_consistency 和 source_entity 独立归属。
    _global_fail_pats = {
        "content_volume": r"(content_volume|内容量|文字量|篇幅不足)",
        "annotation_types": r"(annotation_types|标注类型(?!\s*达标))",
        "排版一致性": r"(排版一致性|format_consistency)",
        "data_conflicts": r"(data_conflicts|数据字典冲突)",
        "template_repeat": r"(template_repeat|模板句|重复句)",
        "so_what_chain": r"(so_what|So What|推理链)",
        "market_size_consistency": r"(market_size_consistency|市场规模.*口径|市场规模.*不一致)",
        "source_entity": r"(source_entity|来源标注空泛)",
    }
    # R77（2026-08-06 P0）：失败指纹检测——同一指纹连续出现>2次降级为警告
    # AgentGuard-LLM 模式：fault-signature-based retry，防无效全量重写
    _fail_fingerprints = context.get("_fail_fingerprints", {})
    for ftype, pat in _global_fail_pats.items():
        if _re.search(pat, fb):
            fp_key = f"{ftype}:{_re.search(pat, fb).group(0)[:30]}"
            _fail_fingerprints[fp_key] = _fail_fingerprints.get(fp_key, 0) + 1
            if _fail_fingerprints[fp_key] >= 3:
                logger.warning("[REVISE-LOCAL] 失败指纹重复%d次→降级警告: %s", _fail_fingerprints[fp_key], fp_key)
                continue  # skip this fail_type, don't trigger full rewrite
            fail_types.append(ftype)
            logger.info("[REVISE-LOCAL] 全局失败 %s → 全量重写 (指纹#%d)", ftype, _fail_fingerprints[fp_key])
    context["_fail_fingerprints"] = _fail_fingerprints

    # 6. R77（2026-08-06 P0）：so_what_chain 死角段定位——从 Gate feedback 提取
    # "死角段: xxx" 标记，用段标题/首句匹配段索引，返回段级重写而非全量重写
    _dead_seg = _re.search(r"死角段:\s*(.+)", fb)
    if _dead_seg:
        _dead_names = _dead_seg.group(1).split(";")
        for _dn in _dead_names:
            _dn = _dn.strip()[:30]
            for i, s in enumerate(sw.segments):
                _label = str(s.get("label", ""))
                if _dn in _label or _label[:6] in _dn:
                    indices.add(i)
                    break
        if indices:
            logger.info("[REVISE-LOCAL] 死角段定位=%s → 重写段 %s", _dead_names, sorted(indices))
            fail_types.append("so_what_chain")

    context["_gate_fail_types"] = fail_types
    _global_types = (
        "content_volume",
        "annotation_types",
        "排版一致性",
        "data_conflicts",
        "template_repeat",
        "so_what_chain",
    )
    _has_global = any(ft in _global_types for ft in fail_types)
    # R53 审计（2026-08-03）：sac_dims + 全局失败并存时，不再直接短路为全量重写。
    # 分离处理：
    #   - 全局失败且无 sac_dims → 全量重写（return None）
    #   - 全局失败 + sac_dims → 返回 sac_dims 定位的段，让 section_writer 组级局部重写
    #     先修复缺失维度；全局问题（内容量/格式）由 prompt 附加说明，避免 3 轮无效全量重写。
    if _has_global and not any(ft == "sac_dims" for ft in fail_types):
        logger.info("[REVISE-LOCAL] 纯全局失败 %s → 全量重写", fail_types)
        return None
    if indices:
        logger.info(
            "[REVISE-LOCAL] 失败类型=%s → 重写段 %s%s",
            fail_types,
            sorted(indices),
            "（含全局失败，段级优先）" if _has_global else "",
        )
        return sorted(indices)
    if _has_global:
        # 有全局失败但无 sac_dims 也无定位段 → 全量重写
        logger.info("[REVISE-LOCAL] 全局失败 %s 且无法定位段 → 全量重写", fail_types)
        return None
    return None
