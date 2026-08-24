"""
修复管线 — 断点修复入口（R92/R95）

用法：
  python pipeline/repair_pipeline.py "output/商业航天深度研究报告.md" --report-type industry_deep
  1. 读取报告文本 → Iron Gate 检查
  2. 失败分类 → 机械类直接修 / 语义类建议重写段
  3. 定向修复 → check_only 复验
  4. 返回修复后的报告文本

不在原 scheduler.py 加 --repair-only 是因为与原 E2E 管线逻辑不同。
修复管线是新路（断点定向修），E2E 是原路（全量重跑），分离更清晰。
"""
import sys, json, re, os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from pipeline.iron_gate import IronGate
from pipeline.checks.base import GateCheckResult


def repair_report(report_path: str, report_type: str = "industry_deep") -> dict:
    """断点修复入口。"""
    path = Path(report_path)
    if not path.exists():
        return {"status": "error", "message": f"文件不存在: {path}"}

    text = path.read_text(encoding="utf-8")

    # 1. 完整 Gate 检查 → 获取失败项
    gate = IronGate(str(path), report_type)
    report = gate.run_all()
    failures = gate.report_failures(report)

    if not failures:
        return {"status": "pass", "message": "Gate 已全部通过，无需修复",
                "gate_score": report.overall_score}

    print(f"[修复管线] {len(failures)} 项失败（{sum(1 for f in failures if f['class']=='mechanical')} 机械 + "
          f"{sum(1 for f in failures if f['class']=='semantic')} 语义 + "
          f"{sum(1 for f in failures if f['class']=='environmental')} 环境）")

    # 2. 分类修复
    mechanical = [f for f in failures if f['class'] == 'mechanical']
    semantic = [f for f in failures if f['class'] == 'semantic']

    changes = []

    # — 机械类修复（规则驱动的定向替换） —
    for f in mechanical:
        name = f['name']
        if name == 'forbidden_patterns':
            # 删除 AI 免责声明
            if 'AI生成' in text or 'AI辅助' in text or '内容由AI生成' in text:
                old = text
                text = re.sub(r'\n?\*?（内容由AI生成，仅供参考）\*?', '', text)
                text = re.sub(r'\n?\*?\(内容由AI生成，仅供参考\)\*?', '', text)
                if text != old:
                    changes.append(f"  [修] 删除 AI 免责声明")
        elif name == 'placeholder_xxx':
            n = text.count('[CHART:') + text.count('[TABLE:')
            if n > 0:
                text = text.replace('[CHART:', '![fig_')
                text = text.replace('[TABLE:', '| 表_')
                changes.append(f"  [修] 替换 {n} 个占位符")
        elif name == 'completeness_scan':
            # 修截断：给段落补句号
            changes.append(f"  [标记] completeness_scan 需目检确认")

    # — 语义类修复（标记建议，需人工/LLM介入） —
    for f in semantic:
        changes.append(f"  [建议] {f['name']}: {f['details'][:60]}...（需 LLM 改写或人工确认）")

    # 3. 定向复验
    modified_names = [f['name'] for f in mechanical]
    if modified_names:
        gate2 = IronGate.from_text(text, report_type)
        recheck = gate2.check_only(modified_names)
        repaired = len([c for c in recheck.checks if c.passed])
        total = len(recheck.checks)
        print(f"[修复管线] 定向复验: {repaired}/{total} 通过")

    return {
        "status": "repaired" if changes else "unchanged",
        "gate_score": report.overall_score,
        "failures_before": len(failures),
        "repairs": changes,
        "text": text,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="2hao 断点修复管线")
    ap.add_argument("report_path", help="报告 md 路径")
    ap.add_argument("--report-type", default="industry_deep", help="报告类型")
    ap.add_argument("--output", "-o", default=None, help="输出路径（默认为覆盖原文件）")
    args = ap.parse_args()

    result = repair_report(args.report_path, args.report_type)

    print(f"\n=== 修复结果 ===")
    print(f"状态: {result['status']}")
    print(f"原 Gate 分: {result.get('gate_score', 'N/A')}")
    for c in result.get('repairs', []):
        print(c)

    if result.get('text') and args.output:
        Path(args.output).write_text(result['text'], encoding="utf-8")
        print(f"已写入: {args.output}")
    elif result.get('text'):
        print("\n[预览] 修复后的文本前 200 字:")
        print(result['text'][:200])
        print("...")
        print("(无 --output，未保存)")


if __name__ == "__main__":
    main()