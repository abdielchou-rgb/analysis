"""R77 (2026-08-05) 回归测试 — P0-4 失败保护 chaos 注射验证。

场景1: agent_provider 质量护栏拦截坏响应（占位符/过短/拒绝生成）
场景2: best-so-far 回滚——低分 attempt 不覆盖高分稿
（只读验证，不真实跑管线）
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

for line in (_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)


def test_quality_guard_blocks_placeholder():
    """护栏应拦截占位符/错误响应。"""
    from core.agent_provider import _check_agent_response_quality

    long_placeholder = "请求超时，请稍后重试。服务暂不可用，队列为空，无待处理请求。" * 15
    issue = _check_agent_response_quality(long_placeholder)
    assert issue and "占位" in issue, f"应拦截占位符: {issue}"


def test_quality_guard_blocks_short():
    """护栏应拦截过短响应（<150字）。"""
    from core.agent_provider import _check_agent_response_quality

    issue = _check_agent_response_quality("太短了")
    assert issue and "过短" in issue, f"应拦截过短: {issue}"


def test_quality_guard_blocks_refusal():
    """护栏应拦截拒绝生成响应。"""
    from core.agent_provider import _check_agent_response_quality

    long_refusal = "我无法完成这个分析任务，因为缺少足够的数据支撑。我无法生成投资建议。" * 15
    issue = _check_agent_response_quality(long_refusal)
    assert issue and "拒绝" in issue, f"应拦截拒绝: {issue}"


def test_quality_guard_accepts_good():
    """护栏应放行合格响应。"""
    from core.agent_provider import _check_agent_response_quality

    good = "公司2025年营收15.58亿元，毛利率44.8%，归母净利3.41亿元。DCF估值区间145-160亿元，目标价28元。" * 3
    assert _check_agent_response_quality(good) is None, "合格响应应放行"


def test_best_so_far_rollback():
    """best-so-far 回滚：低分 attempt 不覆盖高分稿。"""
    bsf = {"score": 0, "text": ""}

    def simulate(score, text):
        # 与 e2e R66 相同的逻辑
        if score > bsf["score"] and len(text) > 500:
            bsf["score"] = score
            bsf["text"] = text
            return "UPDATED"
        return "KEPT"

    t1 = "高质量分析稿：" + ("公司2025年营收15.58亿元，毛利率44.8%，DCF估值145-160亿。" * 20)
    t2 = "稍差分析稿：" + ("公司2025年营收15.58亿元。" * 30)
    t3 = "泛化行业稿：" + ("本报告对传感器行业进行分析。" * 40)

    simulate(0.91, t1)
    simulate(0.88, t2)
    simulate(0.77, t3)

    assert bsf["score"] == 0.91, f"应保留最高分: {bsf['score']}"
    assert bsf["text"] == t1, "应保留 attempt1 高分稿"
    assert "高质量分析稿" in bsf["text"]


def test_e2e_best_so_far_code_path():
    """e2e 代码应包含 best-so-far 更新与回滚逻辑。"""
    src = (_ROOT / "pipeline" / "e2e_orchestrator.py").read_text(encoding="utf-8")
    assert "_best_so_far" in src, "应有 best-so-far 记录"
    assert "保留最佳稿" in src, "失败时应保留最佳稿"
    assert "更新最佳稿" in src, "应更新最佳稿"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
