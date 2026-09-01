"Framework Injection module — 将外部方法论YAML注入SAC分析框架"

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("2hao.framework_injector")

FRAMEWORKS_DIR = Path(__file__).resolve().parent.parent / "core" / "frameworks"
REGISTRY_FILE = FRAMEWORKS_DIR / "frameworks_registry.yaml"


def load_registry() -> dict:
    """加载框架注册表"""
    if not REGISTRY_FILE.exists():
        logger.warning("Framework registry not found: %s", REGISTRY_FILE)
        return {"frameworks": {}}
    with open(REGISTRY_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"frameworks": {}}


def load_framework(framework_id: str) -> dict | None:
    """加载单个框架YAML"""
    path = FRAMEWORKS_DIR / f"{framework_id}.yaml"
    if not path.exists():
        logger.warning("Framework file not found: %s", path)
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_frameworks_for_report(report_type: str = "listed_company", industry_hint: str = "") -> list[dict]:
    """获取与报告类型匹配的框架。

    R81（2026-08-06）：增加行业关键词动态匹配——此前按 report_type 一刀切，
    油位等小行业匹配不到咨询/产业框架。现在行业关键词命中框架 tags/适用行业
    的框架优先排前。
    """
    registry = load_registry()
    frameworks = registry.get("frameworks", {})
    result = []
    for fid, fconfig in frameworks.items():
        fdata = load_framework(fid)
        if fdata:
            fdata["_priority"] = fconfig.get("priority", 9)
            fdata["_sac_mapping"] = fconfig.get("sac_dimension_mapping", [])
            # 行业动态匹配：框架 tags 或适用行业包含行业关键词 → 优先级提升
            if industry_hint:
                _tags = str(fdata.get("tags", "")) + str(fdata.get("适用行业", ""))
                _ind = industry_hint.lower()
                if _ind in _tags.lower() or any(t.lower() in _tags.lower() for t in _ind.split()):
                    fdata["_priority"] = min(fdata["_priority"] - 3, 0)  # 命中行业 → 排最前
            result.append(fdata)
    result.sort(key=lambda x: x.get("_priority", 9))
    return result


def inject_framework_prompt(
    report_type: str = "listed_company", biz_type: str = "", stage_summary: str = "", industry_hint: str = ""
) -> str:
    """生成框架注入文本，追加到写作prompt中"""
    frameworks = get_frameworks_for_report(report_type, industry_hint)
    if not frameworks:
        return ""

    parts = ["[外部分析方法论注入——必须用具体分析步骤应用于本报告标的]"]

    # S4-2: 数据驱动排序——如有实测数据，按 get_framework_ranking 排序
    _fw_by_id = {fw.get("id", ""): fw for fw in frameworks}
    _data_ranked_ids = []
    try:
        from core.method_reflection import get_framework_ranking
        ranking = get_framework_ranking(report_type)
        _data_ranked_ids = [r["framework"] for r in ranking]
    except Exception:
        pass

    def _sort_key(fw):
        fid = fw.get("id", "")
        # 有实测排名的排前面，按排名顺序
        if fid in _data_ranked_ids:
            return (0, _data_ranked_ids.index(fid))
        # 关键框架次优先
        _KEY_FRAMEWORKS = {
            "moat_analysis", "competition_demystified", "value_driver",
            "strategy_engine", "cycle_thinking", "expectations_investing",
            "signal_noise", "accounting_for_value",
        }
        if fid in _KEY_FRAMEWORKS:
            return (1, 0)
        # 其余按 YAML priority
        return (2, fw.get("_priority", 9))

    _sorted = sorted(frameworks[:8], key=_sort_key)
    for fw in _sorted[:6]:  # Top 6
        name = fw.get("name", "?")
        core = fw.get("core_thesis", "")[:150]
        chain = fw.get("logic_chain", [])
        chain_summary = " → ".join([s.get("step", "")[:20] for s in chain[:5]])
        mapping = fw.get("_sac_mapping", [])
        parts.append(f"  [{name}] {core}")
        parts.append(f"     分析链: {chain_summary}")
        if mapping:
            parts.append(f"     SAC映射: {', '.join(mapping)}")
        # R81（2026-08-06）：注入具体分析操作，而非只注入框架名——
        # 此前LLM看到框架名不知怎么用，导致"框架融入了但没生效"。
        # 现在把每个步骤的dimensions/indicators具体操作注入，LLM才能落地分析。
        for step in chain[:3]:
            step_name = step.get("step", "")
            desc = step.get("description", "")[:80]
            dims = step.get("dimensions", {})
            if dims and isinstance(dims, dict):
                dim_lines = []
                for dname, dcfg in list(dims.items())[:5]:
                    if isinstance(dcfg, dict):
                        ind = dcfg.get("indicators", [])
                        ind_str = "/".join(str(i)[:10] for i in ind[:3])
                        dim_lines.append(f"      - {dcfg.get('name', dname)}: 看{ind_str}")
                if dim_lines:
                    parts.append(f"     【{step_name}】{desc}")
                    parts.extend(dim_lines)
        parts.append("")
    if biz_type:
        parts.append(f"  商业模式类型: {biz_type}")
        parts.append("")
    if stage_summary:
        parts.append("")
        parts.append(stage_summary)
    parts.append("[/外部方法论注入]")
    parts.append(
        "要求：上述每个框架必须对本报告标的给出具体应用结论——如'用护城河框架分析柯力：转换成本中等、成本优势强'，禁止只提框架名不分析。"
    )
    return "\n".join(parts)


def framework_aware_prompt(report_type: str = "listed_company", biz_type: str = "") -> str:
    """整合框架注入和宏/商业背景的完整prompt前导"""
    parts = []
    # 框架注入
    fw = inject_framework_prompt(report_type, biz_type)
    if fw:
        parts.append(fw)
    return "\n".join(parts)


def list_available_frameworks() -> list[dict]:
    """列出所有可用框架"""
    registry = load_registry()
    result = []
    for fid, fconfig in registry.get("frameworks", {}).items():
        fdata = load_framework(fid)
        result.append(
            {
                "id": fid,
                "name": fconfig.get("name", fid),
                "author": fconfig.get("author", "?"),
                "priority": fconfig.get("priority", 9),
                "sac_mapping": fconfig.get("sac_dimension_mapping", []),
                "dimensions": list(fdata.get("analytical_dimensions", {}).keys()) if fdata else [],
            }
        )
    return result


def inject_framework_rationale(report_type: str | None = None) -> str:
    """生成数据驱动的框架选择依据说明（S4-3）。

    输出格式：
    > 本报告选用【{framework}】框架（依据：同行业此前 N 份报告用此框架 Gate 通过率 Y%，高于全量均值 Z%）。

    无实测数据时返回空字符串。
    """
    try:
        from core.method_reflection import get_framework_ranking
        ranking = get_framework_ranking(report_type)
    except Exception:
        return ""

    if not ranking:
        return ""

    top = ranking[0]
    fw_name = top["framework"]
    pass_rate = top["pass_rate"]
    avg_gate = top["avg_gate"]
    count = top["count"]

    # 计算全量均值
    all_rates = [r["pass_rate"] for r in ranking]
    overall_pass_rate = sum(all_rates) / len(all_rates) if all_rates else 0

    return (
        f"\n> 本报告选用【{fw_name}】框架"
        f"（依据：同行业此前 {count} 份报告用此框架 Gate 通过率 {pass_rate:.0%}，"
        f"平均 Gate 分 {avg_gate:.2f}，"
        f"{'高于' if pass_rate > overall_pass_rate else '接近'}"
        f"全量均值 {overall_pass_rate:.0%}）。\n"
    )
