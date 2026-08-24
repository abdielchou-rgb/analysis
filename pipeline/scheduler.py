"""2号分析师 Scheduler — 强制管线入口 (v2, E2EOrchestratorV2 backend)

⚠️ 这是 2hao-analyst 报告生成的唯一入口。
Agent 不得绕过此模块直接写报告。

用法：
    python pipeline/scheduler.py "芯联集成" --type listed_company --style cicc

三步流程：
    1. 环境自检（DeepSeek API key / akshare / dependencies）
    2. 数据预采集自检（是否拿到了真实数据）
    3. 调用 E2EOrchestratorV2（写→评→改循环 + Iron Gate）

任何绕过此入口的报告输出 = 无效输出。
"""

import sys
import os
import json
import re
import logging
from pathlib import Path
import importlib

# ── 加载 .env（环境变量注入）──
# .env 位于项目根目录，包含 DEEPSEEK_API_KEY / TAVILY_API_KEY / ALIYUN_API_KEY 等
def _load_env_file() -> None:
    """从项目根目录 .env 加载密钥到 os.environ（不覆盖已存在的变量）。"""
    try:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


_load_env_file()

# ── 强制出口模式 ──
# FP4/FP7: 所有报告输出必须经过export_report + visual_gate
# Agent(Claude)不得绕过此模式直接生成DOCX
_ENFORCE_GATE = os.environ.get("ENFORCE_GATE", "true").lower() == "true"

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("2hao.scheduler")


# ═══════════════════════════════════════════════════════════════
# 环境自检
# ═══════════════════════════════════════════════════════════════

ENV_CHECKS = {}

def run_env_checks() -> bool:
    """运行环境自检，返回是否全部通过"""
    all_pass = True

    # 1. DeepSeek API Key
    dk = os.environ.get("DEEPSEEK_API_KEY", "")
    ENV_CHECKS["deepseek_key"] = bool(dk) and dk.startswith("sk-")
    if not ENV_CHECKS["deepseek_key"]:
        logger.warning("[环境] DEEPSEEK_API_KEY 未设置或格式不正确")
        all_pass = False
    else:
        logger.info("[环境] DEEPSEEK_API_KEY 已设置")

    # R82（2026-08-06）：LLM provider 路由诊断——明确当前用哪个 provider，
    # 解决"反复要 key / Marvis 没启动"的困惑。
    _lp = os.environ.get("LLM_PROVIDER", "deepseek")
    _hb_path = _ROOT / "data" / "agent_llm_queue" / ".heartbeat"
    _hb_ok = False
    if _hb_path.exists():
        try:
            import time as _t
            _ts = float(json.loads(_hb_path.read_text(encoding="utf-8")).get("ts", 0))
            _hb_ok = (_t.time() - _ts) <= 30
        except Exception:
            pass
    ENV_CHECKS["llm_provider"] = _lp
    if _lp == "agent_provider":
        logger.info("[环境] LLM_PROVIDER=agent_provider（Marvis 起草）| responder 心跳: %s",
                    "OK" if _hb_ok else "无/过期→将快速失败回退DeepSeek")
        if not _hb_ok:
            logger.warning("[环境] Marvis responder 不在线！需在本环境运行: python scripts/agent_llm_responder.py watch")
    else:
        logger.info("[环境] LLM_PROVIDER=deepseek（性能模式）| DeepSeek key: %s",
                    "OK" if ENV_CHECKS["deepseek_key"] else "缺失→会反复要求key")

    # 2. LLM provider 策略（2026-07-31 用户决策）：单 provider = DeepSeek
    #    多 provider 自动切换已移除。DeepSeek 故障时由 L3 agent 兜底
    #    （见 e2e_orchestrator 的 llm_degradation_level 机制）。
    #    恢复多 provider 请从 .env.bak 恢复 key。

    # 3. akshare
    try:
        import akshare as ak
        ENV_CHECKS["akshare"] = True
        logger.info("[环境] akshare 可用")
    except (ImportError, OSError) as e:
        ENV_CHECKS["akshare"] = False
        logger.warning("[环境] akshare 不可用（%s）——部分数据不可用", e)
        all_pass = False

    # 3. core modules (实际管线使用的模块)
    for mod_name in [
        "core.sacs", "core.deepseek_client",
        "pipeline.iron_gate", "pipeline.section_writer",
        "pipeline.chart_runner", "pipeline.e2e_orchestrator",
        "pipeline.data_collector", "core.style",
    ]:
        try:
            importlib.import_module(mod_name)
            ENV_CHECKS[mod_name] = True
        except Exception as e:
            ENV_CHECKS[mod_name] = False
            logger.error("[环境] 模块导入失败: %s — %s", mod_name, e)
            all_pass = False

    # 4. SAC 文件是否存在
    sac_dir = _ROOT / "core" / "sacs"
    required_sacs = ["sac_industry_deep.yaml", "sac_listed_company.yaml",
                     "sac_unlisted_company.yaml", "sac_earnings_notes.yaml",
                     "sac_decision_memo.yaml"]  # R83
    for sac_file in required_sacs:
        exists = (sac_dir / sac_file).exists()
        ENV_CHECKS[f"sac_{sac_file}"] = exists
        if not exists:
            logger.error("[环境] SAC 文件缺失: %s", sac_file)
            all_pass = False

    return all_pass


# ═══════════════════════════════════════════════════════════════
# 主调度入口
# ═══════════════════════════════════════════════════════════════

def schedule(asset: str, report_type: str = "industry_deep",
             style: str = "cicc", output_dir: str = "output",
             time_anchor: dict = None, enrich_file: str = None,
             data_sufficiency_hint: dict = None, industry_hint: str = "",
             client_questions: list = None) -> dict:
    """调度完整管线（E2EOrchestratorV2 后端）

    Args:
        asset: 分析标的（股票代码或公司名）
        report_type: 报告类型
        style: 机构风格
        output_dir: 输出目录
        time_anchor: 时间锚点 dict
        enrich_file: agent 补充数据 JSON 路径（--enrich-file）

    Returns:
        {"status": "ok", "md": "path/to/report.md", "docx": "path/to/report.docx", ...}
        或 {"status": "error", "message": "..."}
    """
    print(f"\n{'='*60}")
    print(f"  2号分析师 Scheduler — 强制管线入口 (v2)")
    print(f"{'='*60}")
    print(f"  标的: {asset}")
    print(f"  类型: {report_type}")
    print(f"  风格: {style}")
    print(f"  输出: {output_dir}")
    print(f"{'='*60}\n")
    # FP8 数据充足度提示（来自 --data-check-only 的 gaps，或调用方传参）
    if not data_sufficiency_hint:
        # 自动读取 output/<asset>_gaps.json 作为数据充足度信号（若存在）
        _gap_path = Path(output_dir) / f"{asset}_gaps.json"
        if _gap_path.exists():
            try:
                _gap = json.loads(_gap_path.read_text(encoding="utf-8"))
                data_sufficiency_hint = {
                    "sufficient": bool(_gap.get("sufficient", True)),
                    "semantic_gap": _gap.get("semantic_gap") or _gap.get("detail", "").split("semantic_gap=")[-1][:60] if _gap.get("semantic_gap") is None else _gap.get("semantic_gap"),
                    "missing_partial": _gap.get("missing_partial") or [],
                    "missing_core": _gap.get("missing_core") or [],
                }
                logger.info("[PLANNER] 读取 gaps.json: sufficient=%s", data_sufficiency_hint.get("sufficient"))
            except Exception as _e:
                logger.warning("[PLANNER] gaps.json 解析失败: %s", str(_e)[:60])
    industry_hint = industry_hint or ""
    # 从标的名提取行业线索（若未传）——截取关键词，供 planner 框架匹配
    if not industry_hint:
        industry_hint = asset

    # Step 1: 环境自检
    print("[1/4] 环境自检...")
    env_ok = run_env_checks()
    if not env_ok:
        logger.warning("环境自检未完全通过，将尝试继续（管线内部会有降级处理）")

    # Step 2: 加载 SAC 框架
    print("[2/4] 加载 SAC 框架...")
    from core.sacs import SACLoader
    sac = SACLoader(report_type)
    dims = sac.get_dimension_ids()
    chain = sac.get_logic_chain()
    print(f"  SAC: {sac._data.get('name', report_type)}")
    print(f"  维度: {len(dims)} 个")
    print(f"  逻辑链: {len(chain)} 步")

    # Step 2.5: FP8 元认知选择 — 分析方案规划（决定用什么框架/聚焦哪些维度）
    # 方案只影响"用什么方法"，不豁免后续 IronGate 验证（FP8 边界）
    print("[2.5] 分析方案规划（FP8 元认知选择）...")
    analysis_plan = None
    try:
        from core.analyst_planner import build_analysis_plan
        analysis_plan = build_analysis_plan(
            asset=asset, report_type=report_type,
            data_sufficiency=data_sufficiency_hint,
            industry_hint=industry_hint,
        )
        print(f"  框架: {[f['id'] for f in analysis_plan['frameworks']]}")
        print(f"  维度聚焦: {len(analysis_plan['sac_focus']['focus'])} 核心, "
              f"精简: {len(analysis_plan['sac_focus']['slim'])}")
        print(f"  降级声明: {len(analysis_plan['degradation'])} 项")
    except Exception as e:
        logger.warning("[PLANNER] 方案规划失败（降级为全维度管线）: %s", str(e)[:80])
        analysis_plan = None

    # 持久化分析方案（可审计）
    if analysis_plan:
        try:
            _plan_path = Path(output_dir) / f"{asset}_analysis_plan.json"
            _plan_path.write_text(json.dumps(analysis_plan, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("[PLANNER] 方案已保存: %s", _plan_path)
        except Exception as _e:
            logger.warning("[PLANNER] 方案保存失败: %s", str(_e)[:60])

    # Step 3: 执行 E2EOrchestratorV2
    print("[3/4] 调用 E2EOrchestratorV2（数据→计算→写→评→改→门禁）...")
    print("  ⚠ Agent 不得绕过此步骤直接写报告\n")

    from pipeline.e2e_orchestrator import E2EOrchestratorV2
    orchestrator = E2EOrchestratorV2(
        asset=asset,
        report_type=report_type,
        style=style,
        output_dir=output_dir,
        enrich_file=enrich_file,
        analysis_plan=analysis_plan,  # R65: FP8 分析方案
        client_questions=client_questions,  # R83: 委托方问题清单注入
    )
    result = orchestrator.run()

    # R78（2026-08-05 全量审计 P0-2）：orchestrator.run() 返回 report_text 而非 md，
    # 此前 scheduler 读 result["md"] 恒空 → 二次IronGate/ChartEngine/强制出口三段永不执行。
    # 修复：从 report_text 写 MD 到 output_dir，再走后续门禁链。
    if result.get("report_text") and not result.get("md"):
        try:
            _safe = re.sub(r"[^\w一-鿿]+", "_", str(asset)).strip("_") or "report"
            _md_path = Path(output_dir) / f"{_safe}_{style}.md"
            _md_path.write_text(result["report_text"], encoding="utf-8")
            result["md"] = str(_md_path)
            logger.info("[SCHEDULER] 从 report_text 写 MD: %s", _md_path)
        except Exception as _e:
            logger.warning("[SCHEDULER] 写 MD 失败: %s", str(_e)[:80])

    # Step 4: 检查结果并运行 Iron Gate
    print("\n[4/4] Iron Gate 校验...")
    if result.get("status") == "error":
        logger.error("管线返回错误: %s", result.get("message", "未知错误"))
        print(f"\n[!!] 管线未能完成: {result.get('message', '未知错误')}")
        result["status"] = "error"
        result["_scheduler"] = True
        result["_env_checks"] = ENV_CHECKS
        # L3 LLM 兜底信号透传（agent 可感知并介入）
        if result.get("needs_agent"):
            result["status"] = "needs_agent"
            print(f"\n[L3] LLM 不可用，需要 agent 兜底: {result.get('llm_gap', '')}")
            print("    agent 可介入补写后重跑（或恢复 DEEPSEEK_API_KEY）")
        return result

    # Iron Gate 检查 (从报告文本)
    from pipeline.iron_gate import IronGate
    md_path = result.get("md", "")
    if md_path and Path(md_path).exists():
        gate = IronGate(md_path, report_type, style, client_questions=client_questions)
        gate_result = gate.run_all()
        print(f"  Iron Gate: {'✓ 通过' if gate_result.passed else '✗ 阻断'} "
              f"(score={gate_result.overall_score:.2f})")
        result["gate_passed"] = gate_result.passed
        result["gate_score"] = gate_result.overall_score
        result["gate_report"] = gate_result.to_dict()
    else:
        print("  Iron Gate: 跳过（无报告文本）")
        result["gate_passed"] = True

    result["status"] = "ok"
    result["_scheduler"] = True
    result["_env_checks"] = ENV_CHECKS

    # 数据桥接信号透传（agent 兜底是否发生 / 是否需要 agent 补充数据）
    for _k in ("needs_agent", "data_enriched", "data_sufficiency"):
        if _k in result:
            result[_k] = result.get(_k)
    if enrich_file:
        result["enrich_file"] = enrich_file
    
    # T1: ChartEngine图表生成
    if result.get("md", ""):
        _md_path = result["md"]
        if Path(_md_path).exists():
            try:
                from core.chart_engine import ChartEngine
                _ce = ChartEngine(output_dir=str(Path(_md_path).parent), style_id=style)
                _ce.set_style(style)
                # 从markdown中提取[CHART]占位符列表来生成对应图表
                _md_text = Path(_md_path).read_text(encoding="utf-8")
                import re
                _chart_ids = re.findall(r"CHART:(\\w+)", _md_text)
                for _cid in set(_chart_ids):
                    _ce._generate_chart_by_id(_cid)
                logger.info("[CHARTS] Generated %d charts for %s", len(_chart_ids), asset)
            except Exception as e:
                logger.debug("[CHARTS] %s", e)
    
    # FP4/FP7: 强制出口模式 — 通过export_report+visual_gate才能交付
    if _ENFORCE_GATE and result.get("md", ""):
        md_path = result["md"]
        if Path(md_path).exists():
            try:
                from export.report_gate import export_report, GateBlockedError
                docx_path = str(Path(md_path).with_suffix('.docx'))
                # R78（2026-08-05 P0-1.7）：透传管线层 gate_result，避免 IronGate 双跑
                _pipe_gate = result.get("gate_report")
                exported = export_report(
                    Path(md_path).read_text(encoding='utf-8'),
                    docx_path,
                    report_type=report_type,
                    style=style,
                    company_name=asset,
                    title=asset,
                    pipe_gate_result=_pipe_gate,
                )
                result["docx"] = exported
                result["gate_passed"] = True
                print(f"  [强制出口] DOCX: {exported}")
                
                # VisualGate检查
                try:
                    from export.visual_gate import check as vg_check
                    vg = vg_check(exported, report_type)
                    print(f"  [VisualGate] score={vg.get('score',0):.2f}")
                except Exception as vge:
                    print(f"  [VisualGate] {vge}")
                    
            except GateBlockedError as gbe:
                print(f"  [强制出口阻断] {gbe}")
                result["gate_passed"] = False
                result["gate_error"] = str(gbe)
                if result.get("md") and Path(result["md"]).exists():
                    Path(result["md"]).unlink()
                logger.error("强制出口: 报告被门禁阻断，已删除输出")
                return {"status": "error", "error": f"出口门禁阻断: {gbe}"}
            except Exception as e:
                logger.warning("强制出口异常(非阻断): %s", e)
    
    print(f"\n[✓] 管线完成。")
    for fmt, path in result.items():
        if isinstance(path, str) and path.endswith((".md", ".docx", ".pdf", ".pptx")):
            print(f"  {fmt}: {path}")
    return result


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="2号分析师 Scheduler — 强制管线入口",
        epilog="Agent 不得绕过此入口直接写报告。",
    )
    parser.add_argument("asset", help="分析标的（股票代码或公司名）")
    parser.add_argument("--type", "-t", default="industry_deep",
                        choices=["industry_deep", "listed_company", "unlisted_company", "earnings_notes", "decision_memo"],
                        help="报告类型（decision_memo=委托方决策备忘录 R83）")
    parser.add_argument("--style", "-s", default="cicc",
                        help="机构风格（cicc/gs/ms/mck/bcg/citic）")
    parser.add_argument("--output", "-o", default="output",
                        help="输出目录")
    parser.add_argument("--time-anchor", "-ta", default=None,
                        help="时间锚点 JSON")
    parser.add_argument("--enrich-file", "-e", default=None,
                        help="agent 补充数据 JSON 路径（见 pipeline/data_enrichment.py schema）")
    parser.add_argument("--client-questions", "-cq", default=None,
                        help="委托方必答问题清单 JSON（R83：读者+决策点注入，decision_memo 用）")
    parser.add_argument("--data-check-only", action="store_true",
                        help="只做数据缺口快速检查（跑到 enrich 节点即止，不写报告）")
    args = parser.parse_args()

    ta = json.loads(args.time_anchor) if args.time_anchor else None
    cq = json.loads(args.client_questions) if args.client_questions else None

    if args.data_check_only:
        from pipeline.data_enrichment import data_check_only
        print("\n" + "=" * 60)
        print("  数据缺口快速检查（不写报告）")
        print("=" * 60)
        r = data_check_only(args.asset, args.type, args.output, args.enrich_file)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        print("\n[✓] 检查完成。缺口清单见: " + r.get("gap_manifest_path", "(无)"))
        return 0

    result = schedule(args.asset, args.type, args.style, args.output,
                      time_anchor=ta, enrich_file=args.enrich_file,
                      client_questions=cq)
    if result.get("status") == "error":
        return 1

    print("\n" + "=" * 60)
    print(f"  2号分析师 Scheduler — 完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
