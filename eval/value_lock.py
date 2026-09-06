"""
eval/value_lock.py — 写作期数值锁定硬校验（2026-09-06，Phase E 补全）。

对标 DeepEval/CrewAI 的"guardrail 前置而非事后"理念 + 本项目引擎哲学：
"目标价/估值数字必须来自确定性引擎，LLM 不得自造"。

本模块做可重复跑的硬断言（区别于每次发布才跑的 IronGate）：
    1. 报告中的目标价类声明必须落在 engine_ib fair_value 家族
       （fair_value / scenario_weighted / mc_median，±3% 容差）内；
       落不上的 → "疑似自造目标价"，硬 error。
    2. 估值段若出现引擎未产出的绝对金额级声明（元/股、亿元）且无来源
       标注（E/F/A/据…）→ "无源估值声明"，warning。

用法（独立 CLI / 可进 CI / 可被 pytest 驱动）：
    python -m eval.value_lock <report.md> <compute_results.json>
    python -m eval.value_lock <report.md> --extract-from <data_dict.json>  # 自动找 compute_results

返回 dict：{passed, hard_fails[], warnings[], target_price_claims[], verdict}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

# 目标价类检测（与 evidence_enforcer 同族，独立复刻避免循环依赖）
_TP_PATTERNS = [
    r"(?:目标价|12个月目标|合理价位|目标区间(?:上沿|下沿)?)\s*(?:为|约|在|：|:|至|~|～)?\s*(\d+(?:\.\d+)?)\s*(元|元/股|港币|港元)",
    r"(?:目标价|合理估值)\s*[：:]\s*(\d+(?:\.\d+)?)\s*元",
]
_TP_RE = [re.compile(p) for p in _TP_PATTERNS]

# 估值结论声明（元/股级别，需能对上引擎或带来源标注）
_ABS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*元(?:/股)?")

# 来源标注（E=一致预期/F=本报告预测/A=历史事实/B=行业基准/据=实体来源）
_SRC_RE = re.compile(r"[（(]([EFB])[）)]|据[^，。；\n]{1,12}")

_TOL = 0.03  # 目标价容差 ±3%


def _load_compute(compute_results: dict) -> tuple[float | None, list[float], dict]:
    """抽 engine_ib 目标价家族。返回 (primary, [family...], raw_ib)。"""
    ib = compute_results.get("engine_ib") or {}
    if ib.get("status") != "ok":
        return None, [], ib
    r = ib.get("result") or {}
    family = []
    for k in ("fair_value", "scenario_weighted_target", "mc_median"):
        v = r.get(k)
        if isinstance(v, (int, float)) and v == v and v > 0:
            family.append(float(v))
    primary = family[0] if family else None
    return primary, family, ib


def _find_compute_in(data_dict: dict) -> dict | None:
    """从 data_dict 递归找 compute_results。"""
    if isinstance(data_dict, dict):
        for k, v in data_dict.items():
            if k == "compute_results" and isinstance(v, dict):
                return v
            sub = _find_compute_in(v)
            if sub:
                return sub
    return None


def _in_family(value: float, family: list[float]) -> bool:
    for f in family:
        if f == 0:
            continue
        if abs(value - f) / max(abs(f), 1e-9) <= _TOL:
            return True
    return False


def lock_report(report_text: str, compute_results: dict) -> dict:
    """对报告执行数值锁定校验。"""
    hard_fails, warnings = [], []
    tp_claims = []

    primary, family, _ = _load_compute(compute_results)
    if primary is None:
        return {
            "passed": True,
            "skipped": "no_engine_ib",
            "verdict": "skip（无 engine_ib 结果，不做数值锁定）",
            "hard_fails": [],
            "warnings": ["无 engine_ib compute_results——本检查需要确定性估值作为锚"],
            "target_price_claims": [],
        }

    # 1. 目标价声明 vs 引擎家族
    for line_no, line in enumerate(report_text.splitlines(), start=1):
        if line.strip().startswith(("|", "---", "!", "```")):
            continue
        for rp in _TP_RE:
            for m in rp.finditer(line):
                try:
                    val = float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
                tp_claims.append({"line": line_no, "value": val, "text": m.group()[:50]})
                if not _in_family(val, family):
                    hard_fails.append(
                        f"L{line_no} 疑似自造目标价: {m.group()[:40]}（引擎家族={[round(f, 1) for f in family]}，"
                        f"偏差>{_TOL:.0%}）——目标价必须引用引擎值"
                    )

    # 2. 无源估值声明（绝对元/股且非目标价行、无 E/F/A/B/据 标注）
    for line_no, line in enumerate(report_text.splitlines(), start=1):
        if line.strip().startswith(("|", "---", "!", "```")):
            continue
        if not any(rp.search(line) for rp in _TP_RE):  # 排除已处理的目标价行
            for m in _ABS_RE.finditer(line):
                try:
                    val = float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
                # 只锁"像估值结论"的量级（>50 元/股，避免误伤单价/分红）
                if val < 50:
                    continue
                # 目标价语义（前 40 字含 目标/估值/对应）但无来源标注
                ctx = line[max(0, m.start() - 40) : m.start()]
                if not re.search(r"目标|估值|对应|股价|DCF", ctx):
                    continue
                src_ok = bool(_SRC_RE.search(line[m.start() : m.end() + 30]))
                if not src_ok and not _in_family(val, family):
                    warnings.append(f"L{line_no} 无源估值声明（未标注 E/F/A/据 且非引擎值）: {m.group()[:30]}")

    return {
        "passed": not hard_fails,
        "hard_fails": hard_fails,
        "warnings": warnings,
        "target_price_claims": tp_claims,
        "engine_family": [round(f, 1) for f in family],
        "verdict": "PASS" if not hard_fails else "BLOCK（存在疑似自造目标价，需改为引用引擎值）",
    }


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="报告 md 路径")
    parser.add_argument("compute", nargs="?", default=None, help="compute_results JSON 路径")
    parser.add_argument("--extract-from", default=None, help="从 data_dict JSON 自动找 compute_results")
    args = parser.parse_args()

    text = Path(args.report).read_text(encoding="utf-8")
    cr = {}
    if args.compute:
        cr = json.loads(Path(args.compute).read_text(encoding="utf-8"))
    elif args.extract_from:
        dd = json.loads(Path(args.extract_from).read_text(encoding="utf-8"))
        cr = _find_compute_in(dd) or {}
    else:
        print("需提供 compute JSON 或 --extract-from data_dict.json")
        sys.exit(2)

    result = lock_report(text, cr)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("passed") else 1)


if __name__ == "__main__":
    run_cli()
