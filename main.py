"""2hao-analyst — 统一入口

⚠️ 这是管线唯一入口。所有 Agent 必须通过此入口调度。

用法：
    python main.py "芯联集成" --type listed_company --style cicc

流程：
    1. Harness 验证（import链/语法/P0扫描）
    2. E2EOrchestratorV2（完整管线）
    3. Iron Gate（质量门禁）
    4. Report Gate（导出 + 可视化门禁）
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("2hao.main")

# R69（2026-08-05）：main.py 入口加载 .env（此前仅 scheduler.py 加载，
# 导致 DEEPSEEK_API_KEY 缺失 → deepseek 判不可用 → 回退 agent_provider 兜底质量崩坏）
try:
    _env_path = _ROOT / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
        logger.info(
            "[ENV-R69] 已从 .env 加载环境变量（deepseek=%s）", "OK" if os.environ.get("DEEPSEEK_API_KEY") else "MISSING"
        )
except Exception as _e:
    logger.warning("[ENV-R69] .env 加载失败: %s", _e)

# ── GateBlockedError import (safe, runtime import with fallback) ──
try:
    from export.report_gate import GateBlockedError
except ImportError:

    class GateBlockedError(Exception):
        pass


def run_pipeline(
    asset: str,
    report_type: str = "industry_deep",
    style: str = "cicc",
    output_dir: str = "output",
    time_anchor: dict = None,
    enrich_file: str = None,
) -> dict:
    """运行完整分析管线

    Args:
        asset: 分析标的
        report_type: 报告类型
        style: 机构风格
        output_dir: 输出路径
        time_anchor: 时间锚点
        enrich_file: agent 补充数据 JSON 路径

    Returns:
        dict: 包含 status / md / docx / gate_passed / gate_score
    """
    print(f"\n{'=' * 60}")
    print("  2hao-analyst Pipeline")
    print(f"{'=' * 60}")
    print(f"  标的: {asset}")
    print(f"  类型: {report_type}")
    print(f"  风格: {style}")
    print(f"  输出: {output_dir}")
    print(f"{'=' * 60}\n")

    result = {
        "status": "ok",
        "asset": asset,
        "report_type": report_type,
        "style": style,
        "timestamp": datetime.now().isoformat(),
    }

    # Step 0: Harness 快速验证
    print("[0/5] Harness 环境验证...")
    try:
        from harness.validator import run_all as harness_check

        h = harness_check()
        if not h.passed:
            h.print_report()
            p0_failed = [c.name for c in h.checks if not c.passed and c.severity == "P0"]
            if p0_failed:
                # P0-audit 2026-08-24: P0 失败（语法/密钥泄漏/合约）必须阻断，
                # 此前降级为 warning 继续——安全带从不锁死。
                result["status"] = "error"
                result["error"] = f"Harness P0 检查失败: {', '.join(p0_failed)}"
                print(f"  ✗ 阻断: {result['error']}")
                return result
            logger.warning("Harness 验证未完全通过（仅 P1 警告），继续执行")
        else:
            print(f"  ✓ Harness: {len(h.checks)} 项检查通过 ({h.duration_ms:.0f}ms)")
    except Exception as e:
        logger.warning(f"Harness 验证跳过: {e}")

    # Step 1: 运行管线
    print("[1/5] 初始化 E2EOrchestratorV2...")
    from pipeline.e2e_orchestrator import E2EOrchestratorV2

    t0 = datetime.now()
    orchestrator = E2EOrchestratorV2(
        asset=asset,
        report_type=report_type,
        style=style,
        output_dir=output_dir,
        enrich_file=enrich_file,
    )
    pipe_result = orchestrator.run()
    elapsed = (datetime.now() - t0).total_seconds()
    result["pipeline_time_s"] = round(elapsed, 1)
    print(f"  ⏱ Pipeline: {elapsed:.1f}s")

    if pipe_result.get("error") or pipe_result.get("status") == "error":
        result["status"] = "error"
        result["error"] = pipe_result.get("error", "管线执行错误")
        print(f"  ✗ 管线失败: {result['error']}")
        return result

    report_text = pipe_result.get("report_text", "") or pipe_result.get("final_text", "")
    if not report_text:
        result["status"] = "error"
        result["error"] = "管线未生成报告文本"
        return result

    # Step 2: Iron Gate
    print("[2/5] Iron Gate 质量检查...")
    from pipeline.iron_gate import IronGate

    gate = IronGate.from_text(report_text, report_type, style, asset=asset)
    gate_result = gate.run_all()
    # P1-2 (audit 2026-08-01): 将 gate_result 存入 pipe_result，供 export 层复用
    # 避免 report_gate.py 重复完整 IronGate 检查（双重调用 → 单次调用）
    pipe_result["gate_result"] = gate_result
    result["gate_passed"] = gate_result.passed
    result["gate_score"] = round(gate_result.overall_score, 3)
    result["gate_checks"] = gate_result.to_dict()
    print(
        f"  IronGate: {'✓ 通过' if gate_result.passed else '✗ 阻断'} "
        f"(score={result['gate_score']:.2f}, "
        f"{len(gate_result.failures)} issues)"
    )

    # Step 3: 导出
    print("[3/5] 导出报告...")
    # Determine output path
    safe_name = asset.split()[0] if asset else "report"
    md_path = Path(output_dir) / f"{safe_name}_{style}.md"
    docx_path = Path(output_dir) / f"{safe_name}_{style}.docx"

    md_path.parent.mkdir(parents=True, exist_ok=True)
    # P0-C（2026-07-31 审计修复）：MD 与 DOCX 共用统一清洗出口。
    # 写盘前强制 strip AIGC 元数据，否则人工审计首要阅读的 MD 裸露 AIGC 块。
    try:
        from core.style import strip_aigc_metadata

        cleaned_md, _was_mod = strip_aigc_metadata(report_text)
    except ImportError:
        cleaned_md = report_text
    # 额外的排版整理：去除裸露的 HTML 注释块
    import re as _re

    cleaned_md = _re.sub(r"<!--.*?-->", "", cleaned_md, flags=_re.DOTALL)
    cleaned_md = _re.sub(r"\n{3,}", "\n\n", cleaned_md).strip()
    # P3-audit 2026-08-24：claim 级溯源附录（STORM 式数字→数据键→来源）。
    # 纯确定性匹配，env REPORT_CITATION_APPENDIX=0 可关；
    # REPORT_CITATION_INLINE=1 切换为内联脚注形态（[注N] 标记+编号附录）。
    if os.environ.get("REPORT_CITATION_APPENDIX", "1") != "0":
        try:
            if os.environ.get("REPORT_CITATION_INLINE", "0") == "1":
                from core.claim_citation import annotate_inline

                cleaned_md, _claims = annotate_inline(cleaned_md, pipe_result.get("collected_data", {}) or {})
            else:
                from core.claim_citation import append_citation_appendix

                cleaned_md = append_citation_appendix(cleaned_md, pipe_result.get("collected_data", {}) or {})
        except Exception as _cc_err:
            logger.warning("[CITATION] 溯源附录生成失败: %s", str(_cc_err)[:80])
    # P3-B：双声部分离——编辑声部段落归位到文末统一块
    if os.environ.get("REPORT_VOICE_SEPARATION", "1") != "0":
        try:
            from core.voice_separation import separate_voices

            cleaned_md = separate_voices(cleaned_md)
        except Exception as _vs_err:
            logger.warning("[VOICE] 双声部分离失败: %s", str(_vs_err)[:60])
    md_path.write_text(cleaned_md, encoding="utf-8")
    result["md"] = str(md_path)
    print(f"  MD: {md_path}")

    if gate_result.passed:
        try:
            from export.report_gate import export_report as gate_export

            exported = gate_export(
                report_text,
                str(docx_path),
                report_type=report_type,
                style=style,
                company_name=asset,
                title=asset,
            )
            result["docx"] = exported
            print(f"  DOCX: {exported}")
        except GateBlockedError as e:
            logger.warning(f"导出门禁阻断: {e}")
            result["gate_passed"] = False
            result["gate_error"] = str(e)
        except Exception as e:
            logger.warning(f"导出失败: {e}")

    # Step 4: 汇总
    # R78（2026-08-05 全量审计 P0-1.4）：Gate 未通过时不得返回 status=ok（FP7d 合规）。
    # MD 仍写盘供人工审计，但 status=error 让调用方/调度器感知失败。
    print("[4/5] 汇总结果...")
    result["status"] = "ok" if result.get("gate_passed", False) else "error"
    if result["status"] != "ok":
        result["error"] = result.get("gate_error", "Iron Gate 未通过，报告未交付")
    print(f"\n{'=' * 60}")
    print(f"  完成: {result['status']}")
    print(f"  Gate: {'✓' if result.get('gate_passed') else '✗'} score={result.get('gate_score', 'N/A')}")
    for k in ["md", "docx"]:
        if result.get(k):
            print(f"  {k.upper()}: {result[k]}")
    print(f"{'=' * 60}\n")

    return result


def main():
    import argparse

    p = argparse.ArgumentParser(description="2hao-analyst — 深度研究报告生成")
    p.add_argument("asset", nargs="?", default="", help="分析标的")
    p.add_argument(
        "--type",
        "-t",
        default="industry_deep",
        choices=["industry_deep", "listed_company", "unlisted_company", "earnings_notes"],
    )
    p.add_argument("--style", "-s", default="cicc", help="机构风格（cicc/gs/ms/mck/bcg/jpm）")
    p.add_argument("--output", "-o", default="output")
    p.add_argument("--time-anchor", "-ta", default=None, help="时间锚点 JSON")
    p.add_argument(
        "--enrich-file", "-e", default=None, help="agent 补充数据 JSON 路径（见 pipeline/data_enrichment.py schema）"
    )

    args = p.parse_args()
    if not args.asset:
        print("用法: python main.py <标的> [--type <类型>] [--style <风格>]")
        return 1

    ta = json.loads(args.time_anchor) if args.time_anchor else None
    result = run_pipeline(args.asset, args.type, args.style, args.output, ta, enrich_file=args.enrich_file)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
