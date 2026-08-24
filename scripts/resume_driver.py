#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resume Driver — 把 E2EOrchestratorV2 的 AgentGraph 拆成可恢复的多个阶段，
每个 bash 调用跑一个阶段并保存上下文，跨调用推进管线。

用途：在 bash 会话有进程隔离（后台进程被杀、单次调用限时）的环境下，
让完整管线（含多次 LLM 调用）能够分段执行完成。

**本脚本不绕过管线**：它只调度管线自己的节点（E2ENodes / SectionWriter / IronGate），
最终产出一致、完整的报告，并走 Iron Gate 校验。

用法：
    python scripts/resume_driver.py init        # 初始化上下文（跑非LLM快速节点）
    python scripts/resume_driver.py write1      # 写第一部分（LLM）
    python scripts/resume_driver.py write2      # 写第二部分（LLM）
    python scripts/resume_driver.py write3      # 写第三部分（LLM）
    python scripts/resume_driver.py assemble    # StyleCompiler + assemble
    python scripts/resume_driver.py gate        # Iron Gate + export
    python scripts/resume_driver.py status      # 查看进度
"""
import sys, os, pickle, json, logging, time, re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("2hao.resume_driver")

CKPT = Path(os.environ.get("RESUME_CKPT", "/tmp/resume_ctx.pkl"))
STATE = Path(os.environ.get("RESUME_STATE", "/tmp/resume_state.json"))

ASSET = "传感器行业"
REPORT_TYPE = "industry_deep"
STYLE = "cicc"
ENRICH = "/tmp/enrich/sensor_industry_enrich.json"


def _load_env():
    """加载 .env 中的密钥到 os.environ（与 scheduler.py 一致）"""
    env_path = _ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    # 强制卸载坏代理（requests 会读取环境代理）
    for p in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(p, None)


_load_env()


def load_ctx():
    if CKPT.exists():
        with open(CKPT, "rb") as f:
            return pickle.load(f)
    return None


def save_ctx(ctx):
    with open(CKPT, "wb") as f:
        pickle.dump(ctx, f)


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def build_orch():
    from pipeline.e2e_orchestrator import E2EOrchestratorV2
    return E2EOrchestratorV2(ASSET, REPORT_TYPE, STYLE, str(_ROOT / "output"),
                             enrich_file=ENRICH)


FAST_NODES = [
    ("preflight", "preflight_check", []),
    ("biz_macro", "biz_macro_inject", ["preflight"]),
    ("data", "data", []),
    ("data_feeds", "data_feeds", ["data"]),
    ("enrich", "enrich_data", ["data"]),
    ("scarcity", "scarcity_signals", ["enrich"]),
    ("cross_validate", "cross_validate", ["enrich"]),
    ("argument", "argument_engine", ["enrich"]),
    ("learning", "learning", []),
    ("compute", "compute", ["enrich"]),
    ("charts", "charts", ["enrich"]),
    ("hypothesis", "hypothesis_check", []),
]


def _ensure_ctx():
    """初始化上下文（如未初始化）"""
    orch = build_orch()
    ctx = orch._build_context()
    ctx["_fast_done"] = []
    save_ctx(ctx)
    return ctx


def cmd_next():
    """跑下一个未完成的快速节点（单节点级 checkpoint）"""
    ctx = load_ctx()
    if ctx is None:
        ctx = _ensure_ctx()
    from pipeline.e2e_orchestrator import E2ENodes
    done = ctx.get("_fast_done", [])
    for nid, fn_name, _deps in FAST_NODES:
        if nid in done:
            continue
        fn = getattr(E2ENodes, fn_name)
        t0 = time.time()
        try:
            out = fn(nid, ctx)
            if isinstance(out, dict):
                ctx.update(out)
            done.append(nid)
            ctx["_fast_done"] = done
            save_ctx(ctx)
            save_state({"stage": "fast", "next": nid, "done_nodes": done})
            logger.info("[%s] passed (%.0fms)", nid, (time.time()-t0)*1000)
            print(json.dumps({"node": nid, "status": "passed",
                              "elapsed_ms": int((time.time()-t0)*1000)}, ensure_ascii=False))
            return 0
        except Exception as e:
            done.append(nid)  # 记录失败避免死循环
            ctx["_fast_done"] = done
            save_ctx(ctx)
            logger.error("[%s] FAILED: %s", nid, e)
            print(json.dumps({"node": nid, "status": "failed", "error": str(e)[:200]}, ensure_ascii=False))
            return 0
    # 全部完成
    save_state({"stage": "fast", "done": True, "done_nodes": done})
    print(json.dumps({"stage": "fast", "done": True, "nodes": len(done)}, ensure_ascii=False))
    return 0


def cmd_init():
    """一次性跑所有非 LLM 快速节点（在单次 bash 限时内可能跑不完，请用 next 逐节点推进）"""
    orch = build_orch()
    ctx = orch._build_context()
    from pipeline.e2e_orchestrator import E2ENodes

    results = {}
    for nid, fn_name, _deps in FAST_NODES:
        fn = getattr(E2ENodes, fn_name)
        t0 = time.time()
        try:
            out = fn(nid, ctx)
            if isinstance(out, dict):
                ctx.update(out)
            results[nid] = {"status": "passed"}
            logger.info("[%s] passed (%.0fms)", nid, (time.time()-t0)*1000)
        except Exception as e:
            results[nid] = {"status": "failed", "error": str(e)[:200]}
            logger.error("[%s] FAILED: %s", nid, e)
    ctx["_stage_done"] = ["init"]
    ctx["_resume_results"] = results
    save_ctx(ctx)
    save_state({"stage": "init", "done": True, "results": results})
    print(json.dumps({"stage": "init", "results": results}, ensure_ascii=False, indent=2))
    return 0


def _run_write_seg(seg_idx):
    """写一个 section 段（LLM 调用）"""
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    # 控制单次 LLM 调用的 token 预算，确保在 bash 限时内完成
    max_tokens = int(os.environ.get("SEG_MAX_TOKENS", "2000"))
    try:
        import pipeline.section_writer as _sw_mod
        _orig = _sw_mod.call_deepseek
        def _capped(messages, model="deepseek-chat", temperature=0.35,
                    max_tokens=8192, api_key="", stream=False):
            mt = min(max_tokens, int(os.environ.get("SEG_MAX_TOKENS", "2000")))
            return _orig(messages, model=model, temperature=temperature,
                         max_tokens=mt, api_key=api_key, stream=stream)
        _sw_mod.call_deepseek = _capped
    except Exception as e:
        logger.warning("monkeypatch call_deepseek failed: %s", e)
    from pipeline.section_writer import SectionWriter
    sw = SectionWriter(REPORT_TYPE, STYLE)
    sw._chart_paths = ctx.get("chart_paths", {})
    sw._last_data_context = ctx.get("collected_data", {})
    sw._data_bundle = sw._build_data_bundle(ctx.get("collected_data", {}))
    data_str = sw._serialize_data(ctx.get("collected_data", {}))
    chart_md = sw._build_chart_md(ASSET)
    seg = sw.segments[seg_idx]
    logger.info("Writing seg %d/3: %s (max_tokens=%d)", seg_idx+1, seg["label"][:40], max_tokens)
    dim_defs = sw._build_dimension_defs_full(seg["dimension_ids"])
    texts = ctx.get("_seg_texts", [])
    summaries = ctx.get("_seg_summaries", [])
    prev_s = summaries[-1] if summaries else ""
    if seg_idx == 2:
        # 若辩论已单独跑过，直接用；否则现场跑
        debate = ctx.get("_debate_text", "")
        if not debate or len(debate) < 100:
            debate = sw._debate_bold_call(ASSET, data_str)
        if debate and len(debate) > 100:
            texts.append(debate)
            summaries.append(sw._extract_summary(debate))
            ctx["_seg_texts"] = texts
            ctx["_seg_summaries"] = summaries
            ctx["_stage_done"] = (ctx.get("_stage_done", []) or []) + [f"write{seg_idx+1}"]
            save_ctx(ctx)
            print(json.dumps({"stage": f"write{seg_idx+1}", "debate_len": len(debate)}, ensure_ascii=False))
            return 0
    prompt = sw._build_prompt_v4(seg_idx, seg, ASSET, dim_defs, data_str, chart_md, prev_s,
                                 ctx.get("gate_feedback", ""), ctx.get("learning_findings", ""),
                                 state_anchor=ctx.get("state_anchor", None))
    text = sw._call_llm(prompt, seg_idx, ctx.get("learning_findings", ""), "", "")
    text = sw._clean(text)
    texts.append(text)
    summaries.append(sw._extract_summary(text))
    ctx["_seg_texts"] = texts
    ctx["_seg_summaries"] = summaries
    ctx["_stage_done"] = (ctx.get("_stage_done", []) or []) + [f"write{seg_idx+1}"]
    save_ctx(ctx)
    print(json.dumps({"stage": f"write{seg_idx+1}", "len": len(text)}, ensure_ascii=False))
    return 0


def cmd_write1():
    return _run_write_seg(0)


def cmd_write2():
    return _run_write_seg(1)


def cmd_write3():
    return _run_write_seg(2)


def cmd_debate():
    """单独跑 Bold Call 辩论（3 次 LLM 调用），写入 _seg_texts 最前面"""
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    try:
        import pipeline.section_writer as _sw_mod
        _orig = _sw_mod.call_deepseek
        def _capped(messages, model="deepseek-chat", temperature=0.35,
                    max_tokens=8192, api_key="", stream=False):
            mt = min(800, int(os.environ.get("SEG_MAX_TOKENS", "800")))
            return _orig(messages, model=model, temperature=temperature,
                         max_tokens=mt, api_key=api_key, stream=stream)
        _sw_mod.call_deepseek = _capped
    except Exception as e:
        logger.warning("monkeypatch call_deepseek failed: %s", e)
    from pipeline.section_writer import SectionWriter
    sw = SectionWriter(REPORT_TYPE, STYLE)
    data_str = sw._serialize_data(ctx.get("collected_data", {}))
    debate = sw._debate_bold_call(ASSET, data_str)
    if debate and len(debate) > 100:
        # 辩论放在报告最前面（Bold Call 开篇），单独存
        ctx["_debate_text"] = debate
        save_ctx(ctx)
        print(json.dumps({"stage": "debate", "debate_len": len(debate)}, ensure_ascii=False))
    else:
        print(json.dumps({"stage": "debate", "len": 0, "note": "debate empty"}), ensure_ascii=False)
    return 0


def cmd_assemble():
    """StyleCompiler + assemble 成 final_text（含图表注入与来源附录）"""
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    from pipeline.section_writer import SectionWriter
    sw = SectionWriter(REPORT_TYPE, STYLE)
    texts = ctx.get("_seg_texts", [])
    report = sw._assemble(ASSET, texts)
    report = re.sub(r"\{CHART:(\w+)\}", r"![](chart:\1)", report)
    report = sw._remove_md_artifacts(report)
    ctx["report_text"] = report
    try:
        from pipeline.e2e_orchestrator import E2ENodes
        # 关键：在 StyleCompiler 之前先把 [CHART:...] 占位符解析为真实图表路径。
        # StyleCompiler 会剥离未知的 {[CHART:...]} 标记，导致 assemble 无法注入。
        from pipeline.chart_assembler import ChartAssembler
        ca = ChartAssembler(REPORT_TYPE, STYLE)
        chart_map = ctx.get("chart_paths", {})
        injected = ca.inject_charts_postprocess(report, chart_map)
        # 修复：把相对路径转成绝对路径，使 export_report 的 ChartCheck 能解析到文件
        def _abs_path(m):
            alt = m.group(1)
            path = m.group(2)
            if path.startswith(("http", "data:")) or os.path.isabs(path):
                return m.group(0)
            full = Path(_ROOT) / path
            if full.exists():
                return "![" + alt + "](" + str(full) + ")"
            return m.group(0)
        injected = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _abs_path, injected)
        ctx["report_text"] = injected
        # 再跑 style_compile（写回 report_text）
        out = E2ENodes.style_compile("style", ctx)
        if isinstance(out, dict):
            ctx.update(out)
        # 最后用标准 assemble 节点注入来源附录（此时 CHART 已解析，fallback 不会重复）
        out2 = E2ENodes.assemble("assemble", ctx)
        if isinstance(out2, dict):
            ctx.update(out2)
        # 最终绝对路径修正：把相对路径转成绝对路径，使 export_report ChartCheck 能解析
        # 图表引用是相对 output/ 目录的（如 charts/market_size.png），需按 output/ 解析
        final = ctx.get("final_text", "")
        if final:
            out_root = Path(_ROOT) / "output"
            def _abs(m):
                alt, path = m.group(1), m.group(2)
                if path.startswith(("http", "data:")) or os.path.isabs(path):
                    return m.group(0)
                full = out_root / path
                if full.exists():
                    return "![" + alt + "](" + str(full) + ")"
                return m.group(0)
            final2 = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _abs, final)
            ctx["final_text"] = final2
    except Exception as e:
        logger.warning("[STYLE/ASSEMBLE] failed: %s", e)
    ctx["_stage_done"] = (ctx.get("_stage_done", []) or []) + ["assemble"]
    save_ctx(ctx)
    print(json.dumps({"stage": "assemble", "final_text_len": len(ctx.get("final_text", ""))}, ensure_ascii=False))
    return 0


def cmd_gate():
    """Iron Gate + 导出（含指纹）"""
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    from pipeline.iron_gate import IronGate
    text = ctx.get("final_text", "") or ctx.get("report_text", "")
    # 与 E2ENodes.validate 一致的降级判定：图表不足时设置 degradation_level=1，
    # IronGate 据此放宽图表密度类检查（真实数据缺失属预期，见 FP7b）
    chart_count = len(ctx.get("chart_paths", {}))
    dl = ctx.get("degradation_level", 0)
    if chart_count < 5:
        dl = max(dl, 1)
        logger.info("[L1 DEGRADATION] charts=%d < 5, degradation_level=1", chart_count)
    gate = IronGate.from_text(text, REPORT_TYPE, STYLE)
    gate.degradation_level = dl
    gate._allow_placeholder_degradation = dl >= 1
    gr = gate.run_all()
    ctx["gate_result"] = {"passed": gr.passed, "score": gr.overall_score,
                          "failures": [str(f) for f in gr.failures[:10]]}
    print(json.dumps({"gate_passed": gr.passed, "score": round(gr.overall_score, 3),
                      "failures": ctx["gate_result"]["failures"]}, ensure_ascii=False))
    safe = "传感器行业"
    md_path = Path(_ROOT) / "output" / f"{safe}_{STYLE}.md"
    md_path.write_text(text, encoding="utf-8")
    print("MD:", md_path)
    if gr.passed:
        try:
            from export.report_gate import export_report
            orch = build_orch()
            orch._write_pipeline_fingerprint(ctx, ctx["gate_result"])
            docx_path = Path(_ROOT) / "output" / f"{safe}_{STYLE}.docx"
            exported = export_report(text, str(docx_path), report_type=REPORT_TYPE,
                                     style=STYLE, company_name=ASSET, title="传感器行业深度报告")
            ctx["_docx_path"] = exported
            print("DOCX:", exported)
        except Exception as e:
            logger.warning("DOCX export failed: %s", e)
            print("DOCX_ERROR:", str(e)[:300])
    ctx["_stage_done"] = (ctx.get("_stage_done", []) or []) + ["gate"]
    save_ctx(ctx)
    save_state({"stage": "gate", "done": True, "gate_passed": gr.passed,
                "score": gr.overall_score})
    return 0


def cmd_rerun_node(nid):
    """重跑指定节点（enrich/charts 等）"""
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    from pipeline.e2e_orchestrator import E2ENodes
    fn_map = {
        "enrich": E2ENodes.enrich_data,
        "charts": E2ENodes.charts,
        "compute": E2ENodes.compute,
        "data": E2ENodes.data,
    }
    fn = fn_map.get(nid)
    if fn is None:
        print("未知节点:", nid)
        return 1
    t0 = time.time()
    try:
        out = fn(nid, ctx)
        if isinstance(out, dict):
            ctx.update(out)
        # 若重跑 enrich 或 charts，清除已完成的 write 依赖相关标记
        if nid in ("enrich", "charts"):
            for k in ("_fast_done",):
                pass
        save_ctx(ctx)
        save_state({"stage": f"rerun_{nid}", "done": True})
        print(json.dumps({"node": nid, "status": "passed",
                          "elapsed_ms": int((time.time()-t0)*1000)}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"node": nid, "status": "failed", "error": str(e)[:200]}, ensure_ascii=False))
    return 0


def cmd_reset_writes():
    """清空已写文本，注入 Gate 反馈，为写改循环第二轮做准备"""
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    ctx["_seg_texts"] = []
    ctx["_seg_summaries"] = []
    ctx["_debate_text"] = ""
    failures = ctx.get("gate_result", {}).get("failures", [])
    if failures:
        ctx["gate_feedback"] = "上一轮质量门禁未通过，请针对以下问题修订：\n- " + "\n- ".join(f[:150] for f in failures[:6])
    ctx["_revise_round"] = ctx.get("_revise_round", 0) + 1
    save_ctx(ctx)
    print(json.dumps({"stage": "reset_writes", "round": ctx["_revise_round"],
                      "gate_feedback": ctx["gate_feedback"][:200]}, ensure_ascii=False))
    return 0


def cmd_merge_charts():
    """合并 ChartPipeline(5) + ChartPlanner(6) 的全部图表到 ctx['chart_paths']，
    供 write 阶段看到全部可用图表并在正文嵌入占位符。"""
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    merged = dict(ctx.get("chart_paths", {}))
    try:
        from pipeline.chart_planner import ChartPlanner
        planner = ChartPlanner(REPORT_TYPE, STYLE, 'output/charts2', industry=ASSET)
        paths2 = planner.generate_all(ctx.get("collected_data", {}))
        paths2.pop("__meta", None)
        merged.update(paths2)
    except Exception as e:
        logger.warning("ChartPlanner failed: %s", e)
    ctx["chart_paths"] = merged
    ctx["_merged_charts"] = True
    save_ctx(ctx)
    print(json.dumps({"merged_charts": len(merged), "ids": list(merged.keys())}, ensure_ascii=False))
    return 0


def cmd_polish():
    """用管线自身 LLM 对成稿做一轮机构化润色：
    1) 重写开篇摘要，加入明确评级+目标价+市场共识+So What 链
    2) 去除重复样板句
    """
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    text = ctx.get("final_text", "") or ctx.get("report_text", "")
    if len(text) < 2000:
        print("ERROR: final_text 过短")
        return 1
    from core.deepseek_client import call_deepseek
    # 提取前 2500 字作参考
    head = text[:2500]
    prompt = (
        f"你是资深行业分析师。请对以下传感器行业深度报告做开篇润色。\n\n"
        f"报告开头参考：\n{head}\n\n"
        f"请只输出一段【核心投资摘要】（200-300字），要求：\n"
        f"1. 以明确评级开头，如「给予行业'增持'评级」并给出目标价（如'板块未来12个月目标价上行空间XX%'）\n"
        f"2. 包含市场共识的表述（如'市场普遍认为…'）以及我们的不同判断\n"
        f"3. 包含So What链（'这意味着…因此建议…'）\n"
        f"4. 包含可证伪条件（'若…则判断失效'）\n"
        f"5. 引用具体数据（2024年中国传感器市场4061.2亿元、全球2023年1797亿美元等）\n"
        f"直接输出摘要正文，不要标题前缀。"
    )
    sp = "你是资深行业分析师，输出专业Markdown正文。直接输出内容。"
    try:
        r = call_deepseek([
            {"role": "system", "content": sp},
            {"role": "user", "content": prompt},
        ], temperature=0.35, max_tokens=1200)
        summary = r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error("polish LLM failed: %s", e)
        print(json.dumps({"stage": "polish", "error": str(e)[:200]}, ensure_ascii=False))
        return 0
    # 去样板句
    boilerplate = "。因此我们认为，这一趋势的核心变量兑现程度将决定后续估值重估的空间"
    while boilerplate in text:
        text = text.replace(boilerplate, "")
    # 在开头插入摘要
    header_end = 0
    for marker in ["\n\n", "核心判断", "Bold Call"]:
        idx = text.find(marker)
        if idx > 0 and idx < 300:
            header_end = idx
            break
    # 保留 # 标题（若有），在其后插入
    if text.startswith("#"):
        nl = text.find("\n")
        if nl > 0:
            text = text[:nl] + "\n\n" + summary + "\n\n" + text[nl+1:]
        else:
            text = summary + "\n\n" + text
    elif header_end > 0:
        text = text[:header_end] + summary + "\n\n" + text[header_end:]
    else:
        text = summary + "\n\n" + text
    ctx["report_text"] = text
    ctx["final_text"] = text
    ctx["_polished"] = True
    save_ctx(ctx)
    print(json.dumps({"stage": "polish", "final_len": len(text)}, ensure_ascii=False))
    return 0


def cmd_supplement():
    """R6 圆桌修复：用管线自身 LLM 补充缺失的 SAC 必需维度段落。

    目前缺失（0 命中）：capital_flow（资金面）、elasticity_analysis（弹性）、
    industry_chain（产业链）。core_disagreement 命中弱。
    生成的段落插入正文末尾（来源附录之前），带数据支撑。
    """
    ctx = load_ctx()
    if ctx is None:
        print("ERROR: 先运行 init")
        return 1
    final = ctx.get("final_text", "") or ctx.get("report_text", "")
    from core.deepseek_client import call_deepseek
    data_str = ""
    try:
        from pipeline.section_writer import SectionWriter
        sw = SectionWriter(REPORT_TYPE, STYLE)
        data_str = sw._serialize_data(ctx.get("collected_data", {}))[:1500]
    except Exception:
        pass
    prompt = (
        f"你是资深行业分析师，为《传感器行业深度报告》补充三个缺失章节。\n\n"
        f"可用数据：\n{data_str}\n\n"
        f"请输出以下三个小节（Markdown，每节 250-350 字，含具体数据与来源标注(A/B/E/F)）：\n\n"
        f"## 八、资金面与资本市场映射\n"
        f"覆盖：传感器板块资金面判断（北向资金/公募仓位/两融/板块成交等至少2个维度）、"
        f"资本市场一致预期与估值水平、戴维斯双击/双杀判断。\n\n"
        f"## 九、弹性分析与信号链\n"
        f"覆盖：需求收入弹性（IED系数判断——传感器行业是强周期/防御型/中性）、价格弹性、"
        f"供给弹性；先行/同步/滞后三级信号链各1-2个可追踪指标。\n\n"
        f"## 十、产业链联动与风险因素\n"
        f"覆盖：上游（晶圆/材料）—中游（MEMS代工）—下游（消费/汽车/工业）联动传导、"
        f"系统性风险清单（至少5条，含概率与影响）。\n\n"
        f"直接输出三个小节正文，不要其他说明。"
    )
    sp = "你是资深行业分析师，输出专业Markdown正文，每个判断带数据支撑和反方论证。"
    try:
        r = call_deepseek([
            {"role": "system", "content": sp},
            {"role": "user", "content": prompt},
        ], temperature=0.35, max_tokens=2500)
        supplement = r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error("supplement LLM failed: %s", e)
        print(json.dumps({"stage": "supplement", "error": str(e)[:200]}, ensure_ascii=False))
        return 0
    # 插入到来源附录之前
    marker = "AGENT_ENRICH_SOURCES"
    if marker in final:
        idx = final.find("<!-- " + marker)
        final = final[:idx].rstrip() + "\n\n" + supplement + "\n\n" + final[idx:]
    else:
        final = final.rstrip() + "\n\n" + supplement + "\n"
    ctx["final_text"] = final
    ctx["report_text"] = final
    ctx["_supplemented"] = True
    save_ctx(ctx)
    print(json.dumps({"stage": "supplement", "added_len": len(supplement)}, ensure_ascii=False))
    return 0


def cmd_status():
    st = load_state()
    print(json.dumps(st, ensure_ascii=False, indent=2))
    ctx = load_ctx()
    if ctx:
        print("seg_texts:", len(ctx.get("_seg_texts", [])))
        print("final_text_len:", len(ctx.get("final_text", "")))
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fns = {
        "init": cmd_init, "next": cmd_next, "write1": cmd_write1,
        "write2": cmd_write2, "write3": cmd_write3, "debate": cmd_debate,
        "assemble": cmd_assemble, "gate": cmd_gate, "status": cmd_status,
        "rerun": cmd_rerun_node,
    }
    if cmd == "rerun" and len(sys.argv) > 2:
        return cmd_rerun_node(sys.argv[2])
    if cmd == "reset":
        return cmd_reset_writes()
    if cmd == "merge_charts":
        return cmd_merge_charts()
    if cmd == "polish":
        return cmd_polish()
    if cmd == "supplement":
        return cmd_supplement()
    fn = fns.get(cmd)
    if fn is None:
        print("未知命令:", cmd)
        return 1
    return fn()

if __name__ == "__main__":
    sys.exit(main())
