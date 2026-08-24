# report_gate.py — 唯一输出入口 + 强制阻断
# 所有报告生成必须经过此函数，否则不产生输出文件
import logging, os, sys, json, re
from pathlib import Path
import datetime

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("2hao.report_gate")

class GateBlockedError(Exception):
    """报告被门禁阻断"""
    def __init__(self, gate, score, issues):
        self.gate = gate
        self.score = score
        self.issues = issues
        msg = "[%s BLOCKED] score=%.2f issues=%d" % (gate, score, len(issues))
        super().__init__(msg)

def _verify_pipeline_fingerprint(output_path, asset) -> None:
    """FP7d 校验：报告必须携带管线指纹（证明经由 E2EOrchestratorV2 产出）。

    agent 绕过管线直接生成的文件（用 python-docx/pandoc/手写 MD）无指纹 → 阻断。
    """
    out_dir = Path(output_path).parent
    # 查找本资产的指纹文件
    safe = re.sub(r"[^\w一-鿿]+", "_", str(asset)).strip("_") or "asset"
    candidates = [
        out_dir / f"{safe}_pipeline_fingerprint.json",
        out_dir / f"{Path(output_path).stem}_pipeline_fingerprint.json",
    ]
    # 也支持通配扫描（报告名可能带风格后缀）
    fp = next((c for c in candidates if c.exists()), None)
    if fp is None:
        try:
            matches = list(out_dir.glob("*_pipeline_fingerprint.json"))
            if matches:
                fp = matches[0]
        except Exception:
            fp = None
    if fp is None:
        logger.warning(
            "[FINGERPRINT] 未找到管线指纹 %s — 报告疑似绕过管线直接生成",
            [str(c) for c in candidates])
        raise GateBlockedError(
            "PipelineFingerprint", 0.0,
            ["未找到管线指纹。报告必须经由 E2EOrchestratorV2 完整管线生成，"
             "禁止绕过管线直接写报告。"])
    # 校验指纹内容
    try:
        import json as _json
        data = _json.loads(fp.read_text(encoding="utf-8"))
        if not data.get("via_pipeline"):
            raise GateBlockedError("PipelineFingerprint", 0.0,
                                   ["管线指纹无效（via_pipeline=false）"])
        logger.info("[FINGERPRINT] 管线指纹校验通过: %s (gate=%.2f)",
                    fp.name, data.get("gate_score", 0))
    except GateBlockedError:
        raise
    except Exception as e:
        logger.warning("[FINGERPRINT] 指纹解析失败(放行): %s", e)


class GatesConfig:
    """加载 gates_config.yaml 配置"""
    def __init__(self, path=None):
        if path is None:
            path = _ROOT / "export" / "gates_config.yaml"
        self.path = Path(path)
        self._config = self._load()
    
    def _load(self):
        if not self.path.exists():
            logger.warning("gates_config.yaml not found, using defaults")
            return self._defaults()
        try:
            import yaml
            with open(self.path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            return cfg
        except Exception as e:
            logger.warning("Failed to load config: %s, using defaults", e)
            return self._defaults()
    
    def _defaults(self):
        return {
            "iron_gate": {"enabled": True, "min_score": 0.85, "hard_fail": [], "require_all_hard": True},
            "visual_gate": {"enabled": True, "min_score": 0.80, "hard_fail": [], "require_all_hard": True},
            "export": {"delete_on_fail": True, "raise_on_fail": True, "log_all_failures": True, "max_retries": 3},
        }
    
    @property
    def iron_gate(self): return self._config.get("iron_gate", {})
    @property
    def visual_gate(self): return self._config.get("visual_gate", {})
    @property
    def export(self): return self._config.get("export", {})


def _log_failure(gate_name, score, issues, output_path):
    """记录阻断到日志文件"""
    log_dir = _ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "gate_failures.log"
    entry = {
        "gate": gate_name,
        "score": score,
        "issues": issues[:10],
        "output": str(output_path),
        "timestamp": datetime.datetime.now().isoformat(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _delete_output(path):
    """删除失败输出文件"""
    path = Path(path)
    if path.exists():
        try:
            os.remove(path)
            logger.info("Deleted blocked output: %s", path)
        except Exception as e:
            logger.warning("Could not delete %s: %s", path, e)


def export_report(md_text, output_path, report_type="industry_deep", style="cicc",
                  company_name="", title="", pipe_gate_result=None):
    """唯一输出入口：生成DOCX → VisualGate → IronGate → 通过才返回

    Args:
        md_text: Markdown 报告文本
        output_path: 输出路径 (.docx)
        report_type: 报告类型
        style: 机构风格
        company_name: 公司名
        title: 报告标题
        pipe_gate_result: 管线层已完成的 IronGate 结果（P1-2: 避免重复调用）

    Returns:
        str: DOCX 文件路径

    Raises:
        GateBlockedError: 门禁未通过 或 管线指纹缺失（agent 绕过管线）
    """
    output_path = str(output_path)
    config = GatesConfig()

    # Step 0.5: FP7d 管线指纹校验 — 报告必须经由 E2EOrchestratorV2 完整管线
    # agent 绕过管线直接生成的报告文件无指纹 → 阻断
    try:
        _verify_pipeline_fingerprint(output_path, company_name or title)
    except GateBlockedError:
        raise
    except Exception as e:
        logger.warning("[FINGERPRINT] 指纹校验异常(放行): %s", e)

    # Step 0: ContentEnforcer pre-export pipeline check (advisory)
    try:
        from pipeline.content_enforcer import ContentEnforcer
        ce = ContentEnforcer()
        ce.check_all()
    except Exception:
        pass  # ContentEnforcer is advisory; IronGate is the primary gate

    
    # Step 1: 导出 DOCX
    from export.exporter import ReportExporter
    exporter = ReportExporter(company_name=company_name, style_id=style, title=title)
    docx_path = exporter.to_docx(md_text, output_path)
    logger.info("DOCX exported: %s", docx_path)
    
    # Step 1.5: 检查图表文件是否存在
    import re
    chart_refs = re.findall(r'!\[.*?\]\((?!chart:)(.+?)\)', md_text)
    missing_charts = [c for c in chart_refs if not Path(c).exists() and not c.startswith('http')]
    if missing_charts:
        logger.warning("Missing chart images: %d of %d", len(missing_charts), len(chart_refs))
        if config.export.get("delete_on_fail", True) and config.export.get("raise_on_fail", True):
            _delete_output(output_path)
            # P2-3: ChartCheck 阶段只删除 DOCX，MD 还未生成
            raise GateBlockedError("ChartCheck", 0.0, 
                ["Missing charts: " + ", ".join(missing_charts[:5])])
    
    # Step 2: VisualGate 阻断检查
    vg_cfg = config.visual_gate
    vg_result = {"score": 1.0, "issues": []}  # P2-warn: 默认值避免 NameError
    if vg_cfg.get("enabled", True):
        from export.visual_gate import check as vg_check
        vg_result = vg_check(docx_path, report_type)
        
        vg_score = vg_result["score"]
        vg_passed = vg_score >= vg_cfg.get("min_score", 0.7)
        if not vg_passed:
            _log_failure("VisualGate", vg_score, vg_result.get("issues", []), docx_path)
            if config.export.get("delete_on_fail", True):
                _delete_output(docx_path)
                # P2-3 (audit 2026-08-01): Visual Gate 阻断时仅删除 DOCX，
                # 保留 MD 供人工审计追踪
            if config.export.get("raise_on_fail", True):
                raise GateBlockedError("VisualGate", vg_score, vg_result.get("issues", []))
        else:
            logger.info("VisualGate: score=%.2f (>=%.2f, passed)", vg_score, vg_cfg.get("min_score", 0.7))
    
    # Step 3: IronGate 阻断检查
    # P1-2 (audit 2026-08-01): 优先复用管线层已完成的 gate_result，
    # 避免 IronGate 在管线中被调用两次。仅当 pipe_gate_result 缺失时才兜底调用。
    ig_cfg = config.iron_gate
    ig_result = None
    if ig_cfg.get("enabled", True):
        if pipe_gate_result is not None:
            # 复用管线层已有结果，不再重复 IronGate
            # R78（2026-08-05）：兼容 dict（to_dict() 结果）与 GateReport 对象两种形态
            if isinstance(pipe_gate_result, dict):
                from pipeline.checks.base import GateReport, GateCheckResult
                _ig = GateReport()
                _ig.overall_score = float(pipe_gate_result.get("overall_score", 0) or 0)
                _ig.passed = bool(pipe_gate_result.get("passed", False))
                _ig.failures = list(pipe_gate_result.get("failures", []))
                _ig.checks = [GateCheckResult(name=c.get("name", ""),
                                              passed=bool(c.get("passed", False)),
                                              score=float(c.get("score", 0)),
                                              severity=c.get("severity", "warning"))
                              for c in pipe_gate_result.get("checks", [])]
                ig_result = _ig
            else:
                ig_result = pipe_gate_result
            logger.info("IronGate: 复用管线层结果 (score=%.2f, passed=%s)",
                        ig_result.overall_score, ig_result.passed)
        else:
            # 兜底：管线层未传入 gate_result，独立运行 IronGate
            from pipeline.iron_gate import IronGate
            gate = IronGate.from_text(md_text, report_type, style)
            ig_result = gate.run_all()
            logger.info("IronGate: 独立运行（管线层未传入 gate_result）")

        # R78（2026-08-05 全量审计 P0-1）：出口门禁语义修复——
        # 此前只判 overall_score，不判 ig_result.passed，也不消费 gates_config.yaml
        # 的 hard_fail / require_all_hard 配置。导致：核心检查失败（severity=error）
        # 但总分够高时，报告"高分绕过"出口。
        # 修复：passed=False → 阻断；hard_fail 命中 → 阻断（require_all_hard 时任一即阻断）。
        _blocked = False
        _block_reason = []
        if not ig_result.passed:
            _blocked = True
            _block_reason.append("Gate 未通过(passed=False)")
        # hard_fail 消费：gates_config.yaml 显式配置的硬性检查
        _hard_names = ig_cfg.get("hard_fail", [])
        _require_all = ig_cfg.get("require_all_hard", True)
        if _hard_names:
            _hf_failed = [c.name for c in ig_result.checks
                          if c.name in _hard_names and not c.passed]
            if _require_all and _hf_failed:
                _blocked = True
                _block_reason.append(f"hard_fail 未过: {_hf_failed}")
            elif not _require_all and len(_hf_failed) == len(_hard_names):
                _blocked = True
                _block_reason.append(f"全部 hard_fail 未过: {_hf_failed}")
        if ig_result.overall_score < ig_cfg.get("min_score", 0.65):
            _blocked = True
            _block_reason.append(f"score={ig_result.overall_score:.2f} < min={ig_cfg.get('min_score')}")

        if _blocked:
            _log_failure("IronGate", ig_result.overall_score, ig_result.failures, docx_path)

            if config.export.get("delete_on_fail", True):
                _delete_output(docx_path)
                # P2-3 (audit 2026-08-01): Iron Gate 阻断时仅删除 DOCX，
                # 保留 MD 供人工审计追踪

            if config.export.get("raise_on_fail", True):
                raise GateBlockedError("IronGate", ig_result.overall_score,
                                       ig_result.failures + _block_reason)

    vg_score = vg_result["score"] if vg_result else 1.0
    ig_score = ig_result.overall_score if ig_result is not None else 1.0
    # R82（2026-08-06）：终产物 AI 标注复核——导出后对最终 docx/md 扫描，
    # 防"扫描早于导出链路、标注在导出时注入"（v9 事故）。
    try:
        from pathlib import Path as _PA
        for _suffix in (".docx", ".md"):
            _f = _out.with_suffix(_suffix) if _out.suffix != _suffix else _out
            if _f.exists():
                _t = _f.read_text(encoding="utf-8", errors="ignore") if _suffix == ".md" else ""
                if _suffix == ".docx":
                    import zipfile
                    _z = zipfile.ZipFile(_f)
                    _t = _z.read("word/document.xml").decode("utf-8", errors="ignore")
                    _z.close()
                if "内容由AI生成" in _t or "AI辅助" in _t:
                    raise GateBlockedError(
                        "AICleanCheck", 0.0,
                        [f"终产物 {_suffix} 含 AI 标注——去AI化必须在导出后复核"])
    except GateBlockedError:
        raise
    except Exception as _ae:
        logger.warning("[AICLEAN] 终产物扫描异常(放行): %s", str(_ae)[:60])

    # R80 P0-0：产物验证——PDF 含图/大小、DOCX 空段率，不达标阻断交付
    # （防 LibreOffice 未装 → reportlab 降级出无图 PDF 仍"成功"）
    try:
        from pathlib import Path as _P
        _out = _P(docx_path)
        # DOCX 空段率检查
        if _out.exists() and _out.suffix == ".docx":
            import zipfile, re as _re
            z = zipfile.ZipFile(_out)
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
            z.close()
            paras = _re.findall(r"<w:p\b[^>]*>(.*?)</w:p>", xml, _re.S)
            if paras:
                empty = [p for p in paras if not _re.sub(r"<[^>]+>", "", p).strip()]
                empty_ratio = len(empty) / len(paras)
                if empty_ratio > 0.05:
                    raise GateBlockedError(
                        "ProductValidation", 0.0,
                        [f"DOCX 空段率 {empty_ratio:.0%}（>{5}%）——排版未清洗，阻断交付"])
        # PDF 验证（若同目录存在 PDF）
        _pdf = _out.with_suffix(".pdf")
        if _pdf.exists() and _pdf.stat().st_size < 100_000:
            # 小于 100KB 的 PDF 大概率无图（降级产物）
            logger.warning("[PRODUCT] PDF %dKB 可能无图（降级产物）", _pdf.stat().st_size // 1024)
            if config.export.get("raise_on_fail", True):
                raise GateBlockedError(
                    "ProductValidation", 0.0,
                    [f"PDF {_pdf.stat().st_size//1024}KB < 100KB，可能为无图降级产物"])
    except GateBlockedError:
        raise
    except Exception as _pe:
        logger.warning("[PRODUCT] 产物验证异常(放行): %s", str(_pe)[:80])

    logger.info("Report passed all gates: %s (VG=%.2f, IG=%.2f)",
                docx_path, vg_score, ig_score)
    
    return docx_path
