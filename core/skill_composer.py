# -*- coding: utf-8 -*-
"""skill_composer.py — 柔性化定制写作：技能组合 + 框架注册表动态组装（2026-08-07）

从"固定 SAC 模板"升级为"技能组合动态组装"：
  1. 需求解析：用户需求 → (报告类型, 侧重维度, 深度, 受众)
  2. 技能匹配：需求 → 框架注册表里选技能组合
  3. 柔性参数：深度 → 模块数；侧重 → 维度加权；受众 → 风格
  4. 技能自演化：效果记录 → 下次优先选效果好的（GEIS 式）

用法：
  from core.skill_composer import compose_skill_plan, parse_requirement
  req = parse_requirement("侧重并购的尽调报告")
  plan = compose_skill_plan(req)
  # plan: {"frameworks": [...], "focus_dims": [...], "depth": "mid", "params": {...}}
"""
from __future__ import annotations
import os, json, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.skill_composer")

_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = _ROOT / "core" / "frameworks" / "frameworks_registry.yaml"
EFFECT_FILE = _ROOT / "data" / "skill_effects.json"  # 效果记录（技能自演化）

# 需求关键词 → (侧重维度, 框架偏好, 报告类型)
_REQ_INTENT_MAP = {
    "并购": ("ma_valuation", "industry_consolidation", "listed_company"),
    "估值": ("valuation_assessment", "value_driver", "listed_company"),
    "尽调": ("governance_esg", "accounting_for_value", "listed_company"),
    "审计": ("financial_analysis", "accounting_for_value", "listed_company"),
    "风险": ("falsification", "mental_models", "listed_company"),
    "竞争": ("competitive_position", "moat_analysis", "industry_deep"),
    "行业": ("industry_chain", "cycle_thinking", "industry_deep"),
    "非上市": ("unlisted_scarcity", "reference_class", "unlisted_company"),
    "股权": ("governance_esg", "mental_models", "unlisted_company"),
    "ESG": ("esg_materiality", "cfa_standards", "listed_company"),
    "成长": ("growth_drivers", "expectations_investing", "listed_company"),
    "催化剂": ("catalyst", "signal_noise", "listed_company"),
}

# 深度 → 模块数/篇幅
_DEPTH_CONFIG = {
    "shallow": {"modules": 8, "chars_per_dim": 500, "rounds": 2},
    "mid": {"modules": 20, "chars_per_dim": 800, "rounds": 3},
    "deep": {"modules": 40, "chars_per_dim": 1200, "rounds": 5},
}


def parse_requirement(requirement: str, report_type: str = "") -> dict:
    """解析用户需求 → (报告类型, 侧重维度, 框架偏好, 深度, 受众)。

    requirement: 自然语言需求，如"侧重并购的尽调报告""简版行业分析"
    """
    req = requirement or ""
    focus_dims = set()
    fw_prefs = set()
    rtype = report_type or "listed_company"
    for kw, (dim, fw, rt) in _REQ_INTENT_MAP.items():
        if kw in req:
            focus_dims.add(dim)
            fw_prefs.add(fw)
            rtype = rt  # 需求指定报告类型
    # 深度检测
    if any(k in req for k in ("简版", "快速", "概要", "短")):
        depth = "shallow"
    elif any(k in req for k in ("深度", "详版", "全面", "尽调")):
        depth = "deep"
    else:
        depth = "mid"
    # 受众检测
    if any(k in req for k in ("对外", "发布", "客户")):
        audience = "external"
    elif any(k in req for k in ("内部", "决策", "汇报")):
        audience = "internal"
    else:
        audience = "general"
    return {
        "requirement": req,
        "report_type": rtype,
        "focus_dims": sorted(focus_dims) if focus_dims else [],
        "framework_prefs": sorted(fw_prefs) if fw_prefs else [],
        "depth": depth,
        "audience": audience,
    }


def compose_skill_plan(req: dict, registry: Optional[dict] = None) -> dict:
    """按需求组装技能方案：选框架 + 定参数 + 加权维度。

    registry: 框架注册表（默认 load_registry）。效果记录用于权重调整（自演化）。
    """
    if registry is None:
        registry = _load_registry()
    frameworks = registry.get("frameworks", {})

    # 效果记录（技能自演化：效果好的框架优先）
    effects = _load_effects()

    # 候选框架：需求偏好优先，否则全量按 priority
    fw_ids = req.get("framework_prefs") or list(frameworks.keys())
    chosen = []
    for fid in fw_ids:
        cfg = frameworks.get(fid)
        if not cfg:
            continue
        eff = effects.get(fid, {})
        score = cfg.get("priority", 9) - eff.get("penalty", 0)
        chosen.append({"id": fid, "name": cfg.get("name", fid),
                       "priority": score, "effect": eff})
    chosen.sort(key=lambda x: x["priority"])

    depth = req.get("depth", "mid")
    dcfg = _DEPTH_CONFIG.get(depth, _DEPTH_CONFIG["mid"])

    # 侧重维度加权
    focus = req.get("focus_dims", [])
    dim_weights = {}
    for dim in focus:
        dim_weights[dim] = 2.0  # 侧重维度权重翻倍

    return {
        "report_type": req.get("report_type", "listed_company"),
        "depth": depth,
        "audience": req.get("audience", "general"),
        "frameworks": chosen[:dcfg["modules"] // 4 + 3],  # 模块数驱动框架数
        "focus_dims": focus,
        "dim_weights": dim_weights,
        "params": dcfg,
        "requirement": req.get("requirement", ""),
    }


def record_effect(framework_id: str, success: bool, delta_score: float = 0.0):
    """技能自演化：记录某框架的使用效果（Gate 通过加分，失败扣分）。"""
    effects = _load_effects()
    eff = effects.setdefault(framework_id, {"uses": 0, "wins": 0, "penalty": 0})
    eff["uses"] += 1
    if success:
        eff["wins"] += 1
        eff["penalty"] = max(0, eff.get("penalty", 0) - 0.5)  # 成功 → 减少惩罚
    else:
        eff["penalty"] = eff.get("penalty", 0) + 1.0  # 失败 → 惩罚增加
    _save_effects(effects)
    logger.info("[SKILL-COMPOSER] 框架 %s 效果记录: uses=%d wins=%d penalty=%.1f",
                framework_id, eff["uses"], eff["wins"], eff["penalty"])


# ── 内部工具 ─────────────────────────────────────────

def _load_registry() -> dict:
    try:
        import yaml
        with open(REGISTRY_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("[SKILL-COMPOSER] 注册表加载失败: %s", e)
        return {"frameworks": {}}


def _load_effects() -> dict:
    try:
        if EFFECT_FILE.exists():
            return json.loads(EFFECT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_effects(effects: dict):
    try:
        EFFECT_FILE.parent.mkdir(parents=True, exist_ok=True)
        EFFECT_FILE.write_text(json.dumps(effects, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    except OSError as e:
        logger.warning("[SKILL-COMPOSER] 效果记录写盘失败: %s", e)
