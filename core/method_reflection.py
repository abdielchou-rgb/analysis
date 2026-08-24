"""
方法反思闭环（Method Reflection）— FP5 + FP8 演化接线

**定位**：报告完成后记录"用了什么框架、效果如何"，回写 framework_registry 效果字段，
供下次 analyst_planner 更准地选框架。这是 FP5 智能演化在"方法选择"维度的落地。

用法：
    from core.method_reflection import record_reflection
    record_reflection(asset="气体传感器", report_type="industry_deep",
                      frameworks=["bottleneck_engine"], gate_score=0.92,
                      data_sufficiency={"sufficient": True}, notes="卡点分析有效")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("2hao.method_reflection")

_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = _ROOT / "data" / "framework_registry.json"
REFLECTION_LOG_PATH = _ROOT / "data" / "method_reflection_log.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_reflection(
    asset: str,
    report_type: str,
    frameworks: list[str],
    gate_score: float,
    data_sufficiency: dict | None = None,
    notes: str = "",
) -> bool:
    """记录一次报告的方法选择效果，回写 registry 效果字段。"""
    try:
        # 1. 追加到反思日志
        log = _load_json(REFLECTION_LOG_PATH)
        entries = log.get("entries", [])
        entries.append(
            {
                "timestamp": datetime.now().isoformat(),
                "asset": asset,
                "report_type": report_type,
                "frameworks": frameworks,
                "gate_score": round(float(gate_score), 4),
                "data_sufficiency": (data_sufficiency or {}).get("sufficient"),
                "notes": notes[:200],
            }
        )
        log["entries"] = entries[-200:]  # 最多保留 200 条
        _save_json(REFLECTION_LOG_PATH, log)

        # 2. 回写 registry 效果字段
        registry = _load_json(REGISTRY_PATH)
        fw_list = registry.get("frameworks", [])
        for fw in fw_list:
            if fw.get("id") in frameworks:
                eff = fw.setdefault("效果", {})
                # R77（2026-08-05 P0-3）：区分估算基线与实测值。
                # 此前效果字段是手工填的估算（"已用次数3/均分0.92"），若混进滑动平均
                # 会让真实数据被假数据污染。首次实测记录时直接覆盖估算，此后才滑动平均。
                _is_estimate = eff.get("数据来源", "") == "估算基线(2026-08-05 R77 标记，非实测)"
                if _is_estimate:
                    eff["已用次数"] = 1
                    eff["平均Gate分"] = round(float(gate_score), 4)
                    eff.pop("数据来源", None)
                    eff["数据来源"] = "实测(e2e出口自动记录)"
                else:
                    eff["已用次数"] = int(eff.get("已用次数", 0)) + 1
                    # 滑动平均 Gate 分
                    old_avg = float(eff.get("平均Gate分", 0.5))
                    n = int(eff.get("已用次数", 1))
                    eff["平均Gate分"] = round((old_avg * (n - 1) + float(gate_score)) / n, 4)
                # 评分更新（简单阈值）
                if eff["平均Gate分"] >= 0.9:
                    eff["评分"] = "high"
                elif eff["平均Gate分"] >= 0.85:
                    eff["评分"] = "medium"
                else:
                    eff["评分"] = "low"
        registry["frameworks"] = fw_list
        _save_json(REGISTRY_PATH, registry)

        logger.info("[REFLECT] 已记录 %s 框架效果, gate=%.2f", frameworks, gate_score)
        return True
    except Exception as e:
        logger.warning("[REFLECT] 反思记录失败: %s", str(e)[:80])
        return False


def get_reflection_stats() -> dict:
    """查看反思统计。"""
    log = _load_json(REFLECTION_LOG_PATH)
    entries = log.get("entries", [])
    return {
        "total_reports": len(entries),
        "avg_gate_score": round(sum(e.get("gate_score", 0) for e in entries) / len(entries), 4) if entries else 0,
        "frameworks_used": sorted({fw for e in entries for fw in e.get("frameworks", [])}),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        print(json.dumps(get_reflection_stats(), ensure_ascii=False, indent=2))
    else:
        print("用法: python core/method_reflection.py --stats")
