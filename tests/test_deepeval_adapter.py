"""DeepEval 适配器 — LLM-as-judge 评估（显式门控）。

P3-audit 2026-08-24 落地项：业界共识形态的 judge 评估接入。
默认 SKIP（零 token）；设 EVAL_LLM_JUDGE=1 时以 DeepSeek 为 judge 跑
G-Eval 正确性评估，分数低于阈值则 FAIL——夜间套件/手动触发用。

与 eval_gate.py 的分工：
  - eval_gate.py  : 确定性指标，每次 PR 必跑，免费
  - 本模块        : judge 指标，按需跑，付费（5-15x 成本）
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        os.environ.get("EVAL_LLM_JUDGE", "0") != "1",
        reason="judge 评估需 EVAL_LLM_JUDGE=1 显式开启（付费 LLM 调用）",
    ),
]

SAMPLE_REPORT_EXCERPT = """# 商业航天深度研究（节选）

我们判断2026年商业航天发射次数将同比增长40%以上。核心依据：其一，
海南文昌二期工位2025Q4投产，产能瓶颈解除；其二，可回收复飞周期已压缩至
30天以内。风险提示：若发动机量产良率低于80%，上述判断不成立。
数据来源：行业统计口径[1]；公司公告[2]。
"""

REQUIREMENT = "评估该研报节选的判断是否有具体依据、是否包含风险证伪条件"


class _DeepSeekJudge:
    """把 2hao 的 deepseek_client 包装成 DeepEvalBaseLLM（deepeval 校验模型类型）。"""

    def load_model(self):
        return self

    def generate(self, prompt: str) -> str:
        from core.deepseek_client import call_deepseek

        r = call_deepseek(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        return r["choices"][0]["message"]["content"]

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return "deepseek-chat"


def _make_geval():
    try:
        from deepeval.models import DeepEvalBaseLLM
    except ImportError:
        pytest.skip("deepeval 不可用")
    globals()["_DeepSeekJudge"] = type("_DeepSeekJudgeBase", (_DeepSeekJudge, DeepEvalBaseLLM), {})
    judge = _DeepSeekJudge()
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams

    return GEval(
        name="研报论断正确性",
        criteria=(
            "判断论断是否附带可核查的具体依据（产能/时间窗等），"
            "并明确给出风险或证伪条件。依据越具体、证伪越可操作，分数越高。"
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=judge,
        threshold=0.6,
    )


@pytest.fixture(scope="module")
def geval():
    try:
        return _make_geval()
    except Exception as e:  # deepeval 版本差异/初始化失败 → 跳过而非误报
        pytest.skip(f"GEval 初始化失败: {e}")


def test_golden_excerpt_correctness_above_threshold(geval):
    """黄金节选必须过 judge 阈值——若不过，说明 judge 口径或样本退化。"""
    from deepeval import assert_test
    from deepeval.test_case import LLMTestCase

    tc = LLMTestCase(input=REQUIREMENT, actual_output=SAMPLE_REPORT_EXCERPT)
    assert_test(tc, [geval])
