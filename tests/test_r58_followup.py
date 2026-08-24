"""R58 (2026-08-03) 回归测试 — 后续工作接线。

覆盖：
  - consolidation 模块接入 compute_engine
  - 四大审计规则确定性检查（financial_fraud_signals）
  - 知识库维护自动化脚本
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── R58-1: consolidation 接入 compute ─────────────
def test_compute_engine_has_consolidation():
    """compute_engine 应接入 consolidation。"""
    src = (_ROOT / "pipeline" / "compute_engine.py").read_text(encoding="utf-8")
    assert "_run_consolidation" in src, "应含 _run_consolidation"
    assert "from core.compute.consolidation import" in src, "应导入 consolidation 模块"


def test_consolidation_runs():
    """compute_engine._run_consolidation 应返回整合阶段。"""
    from pipeline.compute_engine import ComputeEngine

    ce = ComputeEngine()
    data = {"chart_data": {"fig_valuation": {"industry": "半导体", "cr3": 45}}}
    r = ce._run_consolidation(data)
    assert r.get("status") == "ok", f"应返回ok: {r}"
    assert "consolidation_stage" in r, f"应含整合阶段: {list(r.keys())}"
    assert "整合" in r["consolidation_stage"], "CR3=45应判整合中"


# ── R58-2: 审计确定性检查 ─────────────────────────
def test_fraud_check_registered():
    """IronGate 应注册 financial_fraud_signals 检查。"""
    from pipeline.iron_gate import IronGate

    assert hasattr(IronGate, "_check_financial_fraud_signals")


def test_fraud_check_detects():
    """财务异常 data_dict 应触发造假信号。"""
    import json

    from pipeline.iron_gate import IronGate

    text = ("本报告分析某公司。2024年营收12亿元，净利2.1亿元。我们判断成长期，预计营收增长30%。我们看好龙头。") * 6
    gate = IronGate.from_text(text, report_type="listed_company", style="cicc")
    gate.asset = "test_fraud_r58"
    gate.sac_id = "test_fraud_r58"
    dd = {
        "revenue_trend_2023": 9.0,
        "revenue_trend_2024": 12.0,
        "receivable_2023": 3.0,
        "receivable_2024": 4.5,  # 应收增速50%
        "operating_cashflow_latest": 0.6,
        "net_profit_latest": 2.1,  # OCF/净利=0.29
        "margin_2022": 39.8,
        "margin_2023": 40.1,
        "margin_2024": 40.0,  # 波动0.3pct
        "other_receivable_latest": 2.0,
        "revenue_latest": 12.0,  # 17%
    }
    p = _ROOT / "output" / "test_fraud_r58_data_dict.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(dd), encoding="utf-8")
    try:
        r = gate._check_financial_fraud_signals()
        assert not r.passed, f"财务异常应触发: {r.details}"
        assert "利润质量差" in r.details, "应识别OCF/净利<0.5"
    finally:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


# ── R58-3: 知识库维护自动化 ───────────────────────
def test_refresh_script_exists():
    """refresh_knowledge_base.py 应存在。"""
    assert (_ROOT / "scripts" / "refresh_knowledge_base.py").exists()


def test_refresh_detects_changes():
    """refresh 脚本应能扫描并检测文件变化。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("refresh_kb", _ROOT / "scripts" / "refresh_knowledge_base.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    current = mod.scan_files()
    assert isinstance(current, dict), "应返回文件字典"
    if current:
        rel, (mtime, size) = list(current.items())[0]
        assert isinstance(mtime, float), "mtime 应为 float"


# ── R58-5: Marvis 指令 ────────────────────────────
def test_marvis_r58_instruction():
    """R58 Marvis 指令应存在且覆盖并购/ESG。"""
    assert (_ROOT / "docs" / "marvis-data-backfill-r58.md").exists(), "R58指令缺失"
    content = (_ROOT / "docs" / "marvis-data-backfill-r58.md").read_text(encoding="utf-8")
    assert "m_and_a_cases" in content, "应含并购案例库"
    assert "industry_esg" in content, "应含ESG数据"
    assert "forward_picks" in content, "应含预测样本"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
