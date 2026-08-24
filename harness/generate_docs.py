"""2hao-analyst SDD 文档生成器 — 从代码自动生成管线事实文档

核心思想（来自 Normal Computing SDD 论文）：
  - 规格（spec）是代码和文档的共同父级
  - 不是"写文档→写代码→更新文档"，而是"规格→代码+文档同时生成"

P3-audit 2026-08-24 重构定位：
  - generate_pipeline_facts() —— 唯一真实生成的产物：docs/PIPELINE_FACTS.md，
    数据全部来自运行时代码（IronGate 注册表 / SAC YAML / Provider 注册表 /
    校准阈值），由 pre-commit 的 sdd-facts-sync 钩子强制同步
  - generate_claude_md() 保留但已退役——CLAUDE.md 是手写宪法，不应被
    硬编码模板覆盖（旧钩子每次提交必败的根因）
"""

import re
import sys
from pathlib import Path

from harness.pipeline_contract import IRON_GATE_CONTRACT

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def generate_pipeline_facts() -> str:
    """从运行时代码提取管线事实 → docs/PIPELINE_FACTS.md（全自动同步）。"""
    lines = [
        "# PIPELINE FACTS",
        "",
        "> 本文件由 harness/generate_docs.py 从代码实时生成（pre-commit 强制同步）。",
        "> 手改无效——事实变更请改代码本身。生成时间见文件尾。",
        "",
    ]

    # ── IronGate 检查清单（AST 扫 checks/*.py + iron_gate 本体）──
    import ast

    defined = set()
    for f in (_ROOT / "pipeline" / "checks").glob("*.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_check_"):
                defined.add(node.name)
    ig_src = (_ROOT / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
    executed = set(re.findall(r"self\.(_check_[A-Za-z0-9_]+)", ig_src))
    lines += [
        "## IronGate",
        f"- 注册检查方法数（checks/）：{len(defined)}",
        f"- run_all 引用检查数：{len(executed)}",
        f"- 迁移完整性：{'OK' if defined == executed else 'DRIFT! defined-executed=' + str(sorted(defined - executed))}",
        f"- 合约 min_score：{IRON_GATE_CONTRACT.get('min_score')}",
        "",
    ]

    # ── SAC 报告类型与维度 ──
    try:
        from core.sacs import SACLoader

        sac_types = {}
        for rt in ("listed_company", "industry_deep", "unlisted_company", "earnings_notes", "decision_memo"):
            try:
                dims = SACLoader(rt).get_dimension_ids()
                sac_types[rt] = len(dims)
            except Exception:
                continue
        lines.append("## SAC")
        for rt, n in sorted(sac_types.items()):
            lines.append(f"- {rt}: {n} 维")
        lines.append("")
    except Exception as e:
        lines += ["## SAC", f"- 加载失败: {e}", ""]

    # ── LLM Provider 优先级 ──
    try:
        from core.deepseek_client import PROVIDER_PRIORITY

        lines.append("## LLM Providers（priority 越小越优先）")
        for name, pri in sorted(PROVIDER_PRIORITY.items(), key=lambda x: x[1]):
            lines.append(f"- {name}: {pri}")
        lines.append("")
    except Exception as e:
        lines += ["## LLM Providers", f"- 加载失败: {e}", ""]

    # ── 校准阈值 ──
    cal = _ROOT / "benchmark" / "calibrated_thresholds.json"
    lines.append("## 阈值来源")
    lines.append(f"- calibrated_thresholds.json: {'存在' if cal.exists() else '缺失（用内置默认）'}")
    # P3-audit: 不嵌入时间戳——确定性输出是 facts-sync 钩子可判等的前提
    return "\n".join(lines) + "\n"


def write_pipeline_facts() -> Path:
    out = _ROOT / "docs" / "PIPELINE_FACTS.md"
    out.write_text(generate_pipeline_facts(), encoding="utf-8")
    return out


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
