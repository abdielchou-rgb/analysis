# -*- coding: utf-8 -*-
"""R67 (2026-08-04) 回归测试 — 柯力事故剩余 3 项 P2 修复

覆盖：
1. SELF_AUDIT BOM 容错（em_host_test.py U+FEFF）
2. COMPLIANCE 说服力架构失败项纳入修订目标
3. agent_provider 质量护栏（响应质量校验）
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_self_audit_bom_tolerant():
    """_self_audit.py 编译检查应剥离 BOM 容错。

    P1-audit 2026-08-24：_self_audit.py 源文件已从仓库移除（仅剩孤儿 pyc），
    被测对象消亡 → 条件跳过而非永久 FAIL。
    """
    import pytest
    target = _ROOT / "_self_audit.py"
    if not target.exists():
        pytest.skip("_self_audit.py 已移除，BOM 容错断言随之退役")
    src = _src("_self_audit.py")
    assert "lstrip" in src and "\\ufeff" in src, "self_audit 应剥离 BOM"
    # 实际跑 self_audit 应 PASS
    import subprocess, sys as _sys
    r = subprocess.run([_sys.executable, str(target)],
                       capture_output=True, text=True, timeout=30)
    assert "Result: PASS" in r.stdout, f"self_audit 应 PASS: {r.stdout[-200:]}"


def test_compliance_includes_persuasion():
    """COMPLIANCE 修订分支应含说服力架构/反方观点。"""
    src = _src("pipeline/e2e_orchestrator.py")
    assert "说服力架构" in src or "persuasion_architecture" in src, "应识别说服力架构失败"
    assert "反方观点" in src, "应识别反方观点"


def test_agent_quality_guard():
    """agent_provider 质量护栏应拦截坏响应。"""
    from core.agent_provider import _check_agent_response_quality
    good = ("柯力传感是称重传感器龙头，2022年营收10.6亿元，市占率行业第一，"
            "六维力传感器进入人形机器人供应链，未来看好人形机器人放量带来的成长空间，"
            "同时工业物联网业务打开第二增长曲线。") * 4
    assert _check_agent_response_quality(good) is None, "正常响应应通过"
    assert _check_agent_response_quality("") is not None, "空响应应拒"
    assert _check_agent_response_quality("太短") is not None, "过短应拒"
    long_placeholder = "请求超时，请稍后重试，系统暂时无法处理您的请求。" * 10
    assert _check_agent_response_quality(long_placeholder) is not None, "长占位应拒"
    long_refusal = "抱歉，我无法完成这个分析任务，因为超出我的能力范围。" * 10
    assert _check_agent_response_quality(long_refusal) is not None, "长拒绝应拒"


def test_em_host_bom_removed():
    """temp/em_host_test.py 不应再有 BOM。"""
    p = _ROOT / "temp" / "em_host_test.py"
    if p.exists():
        raw = p.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), "em_host_test.py 不应有 BOM"


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
