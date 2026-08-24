"""2hao-analyst SDD 文档生成器 — 从代码自动生成 CLAUDE.md / SKILL.md / README

核心思想（来自 Normal Computing SDD 论文）：
  - 规格（spec）是代码和文档的共同父级
  - 不是"写文档→写代码→更新文档"，而是"规格→代码+文档同时生成"
  - 本脚本从 pipeline contracts + SAC YAML + 代码 docstring 生成所有文档
"""

import sys
from pathlib import Path

from harness.pipeline_contract import IRON_GATE_CONTRACT

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def generate_claude_md() -> str:
    """从管线合约自动生成 CLAUDE.md"""
    return """# 2号分析师 AI 行为约束宪法

> 此文件由 harness/generate_docs.py 自动生成。
> 不要手动编辑 — 改合约，然后重新生成。

---

## 第一原则——调度管线，不准写报告

你的唯一职责是执行 pipeline/scheduler.py。你不是分析师。

## 第二原则——检查清单

```
□ 1. DEEPSEEK_API_KEY 已设置？
□ 2. 命令：python pipeline/scheduler.py "标的" --type listed_company
□ 3. Iron Gate 通过了？
```

## 第三原则——管线步骤（E2EOrchestratorV2）

preflight_check → data_collect → chart_gen → compute → section_writer → iron_gate → export

## 第四原则——假数据阻断

DataCollectorV5 返回空数据时，不得编造数据替代。如实报告"数据源不可用"。

## 第五原则——自检

在写任何报告内容前自问：
1. 我在用 WebSearch 采集数据？→ 应该调 pipeline/scheduler.py
2. 我在用 Write 写报告？→ 应该调 pipeline/scheduler.py
3. Iron Gate 跑完了？→ 没跑完不能交付
"""


def generate_pipeline_overview() -> str:
    """从合约生成管线概览 Markdown"""
    try:
        from harness.pipeline_contract import (  # noqa: F401  (availability probe)
            E2E_ORCHESTRATOR_CONTRACT,
            SCHEDULER_CONTRACT,
        )
    except ImportError:
        # Fallback inline
        return ""

    lines = ["## 管线架构", ""]
    lines.append("```")
    lines.append("scheduler.py (唯一入口)")
    lines.append("  └→ E2EOrchestratorV2")
    for step, desc in E2E_ORCHESTRATOR_CONTRACT["steps"]:
        lines.append(f"       ├→ {step} — {desc}")
    lines.append(
        "  └→ IronGate (24 项检查, min_score={:.2f})".format(
            IRON_GATE_CONTRACT["min_score"] if "IRON_GATE_CONTRACT" in dir() else 0.55
        )
    )
    lines.append("  └→ export (DOCX / PDF / PPTX)")
    lines.append("```")
    return "\n".join(lines)


def generate_sdd_report() -> str:
    """生成完整的 SDD 规格报告"""
    lines = [
        "# 2hao-analyst SDD 规格说明书",
        "",
        "> 自动生成时间：$(date)",
        "> 生成器：harness/generate_docs.py",
        "",
        "## 规格 vs 代码 vs 文档 映射",
        "",
        "| 规格层 | 代码位置 | 文档位置 |",
        "|--------|----------|----------|",
        "| 管线合约 | harness/pipeline_contract.py | CLAUDE.md / README.md |",
        "| SAC 框架 | core/sacs/*.yaml | AGENTS.md / SKILL.md |",
        "| 验证规则 | harness/validator.py | pre-commit-config.yaml |",
        "| 质量门禁 | pipeline/iron_gate.py | SKILL.md |",
        "",
        "## 变化追踪",
        "",
        "修改代码合约后，执行以下命令同步文档：",
        "",
        "```bash",
        "python harness/generate_docs.py  # 重新生成所有文档",
        "python harness/validator.py       # 验证一致性",
        "```",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="2hao SDD Doc Generator")
    parser.add_argument("--output", "-o", default="", help="输出目录")
    args = parser.parse_args()

    out_dir = Path(args.output) if args.output else _ROOT

    # Generate CLAUDE.md
    claude = generate_claude_md()
    (out_dir / "CLAUDE.md").write_text(claude, encoding="utf-8")
    print(f"  ✓ CLAUDE.md ({len(claude)} chars)")

    # Generate pipeline overview
    overview = generate_pipeline_overview()
    (out_dir / "docs" / "pipeline_overview.md").write_text(overview, encoding="utf-8")
    print(f"  ✓ docs/pipeline_overview.md ({len(overview)} chars)")

    # Generate SDD spec
    sdd = generate_sdd_report()
    (out_dir / "docs" / "sdd_spec.md").write_text(sdd, encoding="utf-8")
    print(f"  ✓ docs/sdd_spec.md ({len(sdd)} chars)")

    print("\n文档生成完成。如需同步到 CLAUDE.md，运行：")
    print("  python harness/generate_docs.py")
