"""eval_gate.py — 确定性评估门禁（业界共识形态）。

P3-audit 2026-08-24 落地项：把"eval 只有失败能阻断才算 quality gate"
工程化——纯确定性指标（零 judge token），双层阈值：

  1. absolute    绝对下限（篇幅/判断密度/数据密度/反方论证）
  2. relative    相对基线容差（指标 ≥ 基线中位数 × min_ratio，
                 容忍 LLM 方差不放过真回归——kube-dojo 模式）

硬失败（no_ai_disclaimer）不受容差保护，一票否决。

用法：
    python tests/golden/eval_gate.py                       # 校验全部 golden 样本
    python tests/golden/eval_gate.py --report output/x.md  # 校验单份产出
    python tests/golden/eval_gate.py --update-baseline     # 重算基线中位数
退出码：0=通过，1=存在失败（CI 直接阻断）。
"""

import json
import re as _re
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.golden.golden_check import check_one  # noqa: E402

THRESHOLDS_PATH = _ROOT / "benchmark" / "eval_thresholds.json"
BASELINE_PATH = _ROOT / "benchmark" / "eval_baseline.json"

DEFAULT_THRESHOLDS = {
    "absolute": {"chars": 5000, "jp_count": 5, "data_points": 20, "cp_count": 3},
    "relative": {"enabled": True, "min_ratio": 0.40, "metric_keys": ["chars", "jp_count", "data_points", "cp_count"]},
    # P3-B：分型阈值——快评类与深度报告天然不同长尾，按正文标记自动切换
    "type_profiles": {
        "earnings_notes": {
            "detect_regex": "(业绩点评|财报点评|季报点评|年报点评|earnings\\s*note)",
            "absolute_overrides": {"chars": 2500, "data_points": 12, "cp_count": 2},
            "relative_disabled": True,
        },
        "decision_memo": {
            "detect_regex": "(决策备忘录)",
            "absolute_overrides": {"chars": 3500},
            "relative_disabled": False,
        },
    },
}


def load_thresholds() -> dict:
    th = {}
    if THRESHOLDS_PATH.exists():
        try:
            th = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
        except Exception:
            th = {}
    # P3-B：旧版阈值文件缺新键时以默认补齐（分型/相对容差等）
    merged = dict(DEFAULT_THRESHOLDS)
    for k, v in th.items():
        if k == "relative" and isinstance(v, dict) and isinstance(merged.get("relative"), dict):
            m = dict(merged["relative"])
            m.update(v)
            merged["relative"] = m
        else:
            merged[k] = v
    return merged


def load_baseline() -> dict:
    """基线 = golden 集各指标中位数（首次自动生成）。"""
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return update_baseline()


def update_baseline() -> dict:
    samples = [check_one(f)["metrics"] for f in sorted(_HERE.glob("*.md")) if f.stat().st_size > 1000]
    if not samples:
        return {}
    base = {}
    for key in samples[0]:
        vals = [m[key] for m in samples if isinstance(m.get(key), (int, float))]
        if vals:
            base[key] = round(statistics.median(vals), 1)
    BASELINE_PATH.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
    return base


def evaluate_report(md_path) -> dict:
    """单份报告评估：返 metrics / verdicts / failures / passed。

    P3-B：分型阈值——正文头部命中 type_profiles.detect_regex 时，
    absolute 用 overrides、relative 可按型关闭（快评类 vs 深度报告）。
    """
    th = load_thresholds()
    r = check_one(Path(md_path))
    metrics = r["metrics"]
    failures = []

    # 分型检测与覆盖合并
    raw_head = Path(md_path).read_text(encoding="utf-8", errors="ignore")[:800]
    detected = None
    for tname, prof in (th.get("type_profiles") or {}).items():
        try:
            if _re.search(prof.get("detect_regex", ""), raw_head):
                detected = tname
                break
        except Exception:
            continue
    abs_floor = dict(th["absolute"])
    rel_cfg = dict(th.get("relative") or {})
    if detected:
        prof = th["type_profiles"][detected]
        abs_floor.update(prof.get("absolute_overrides") or {})
        if prof.get("relative_disabled"):
            rel_cfg["enabled"] = False

    for key, floor in abs_floor.items():
        val = metrics.get(key)
        if isinstance(val, bool):
            ok = val is floor or bool(val)
        elif isinstance(val, (int, float)):
            ok = val >= floor
        else:
            ok = bool(val)
        if not ok:
            tag = f"[{detected}]" if detected else "[absolute]"
            failures.append(f"{tag} {key}={val} < 下限{floor}")

    if rel_cfg.get("enabled"):
        # P3-audit: 文件级豁免——异质历史样本（旧版个股点评等）不参与相对比对
        if Path(md_path).name not in set(rel_cfg.get("exempt_files", [])):
            baseline = load_baseline()
            ratio = float(rel_cfg.get("min_ratio", 0.40))
            for key in rel_cfg.get("metric_keys", []):
                val = metrics.get(key)
                base = baseline.get(key)
                if isinstance(val, (int, float)) and base:
                    if val < base * ratio:
                        failures.append(f"[relative] {key}={val} < 基线中位{base}×{ratio}")

    if not metrics.get("no_ai_disclaimer", False):
        failures.append("[hard] AI 免责声明出现（一票否决，不容差）")

    return {
        "file": Path(md_path).name,
        "metrics": metrics,
        "failures": failures,
        "passed": not failures,
    }


def main() -> int:
    args = sys.argv[1:]
    if "--update-baseline" in args:
        base = update_baseline()
        print(f"baseline updated -> {BASELINE_PATH}")
        print(json.dumps(base, ensure_ascii=False, indent=1))
        return 0
    targets = [Path(a) for a in args if a.endswith(".md")]
    if not targets:
        targets = sorted(_HERE.glob("*.md"))
    all_ok = True
    for f in targets:
        if f.stat().st_size < 1000:
            continue
        r = evaluate_report(f)
        icon = "PASS" if r["passed"] else "FAIL"
        all_ok &= r["passed"]
        print(
            f"  [{icon}] {r['file']} chars={r['metrics']['chars']} "
            f"jp={r['metrics']['jp_count']} data={r['metrics']['data_points']} "
            f"cp={r['metrics']['cp_count']}"
        )
        for msg in r["failures"]:
            print(f"        - {msg}")
    print(f"\n=== eval gate: {'PASS' if all_ok else 'FAIL'} ({len(targets)} files) ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
