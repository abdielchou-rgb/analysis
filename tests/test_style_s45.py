# -*- coding: utf-8 -*-
"""S4/S5 单元测试。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.rhythm import directive_for
from core.voice_separation import separate_voices


class TestRhythm:
    @pytest.mark.unit
    def test_bold_call_short_sentence(self):
        d = directive_for("核心判断组", ["bold_call"])
        assert "短句" in d

    @pytest.mark.unit
    def test_financial_number_chain(self):
        d = directive_for("财务验证", ["financial_trends"])
        assert "数字" in d or "分子" in d

    @pytest.mark.unit
    def test_no_match_empty(self):
        assert directive_for("未知组", ["zzz"]) == ""


class TestVoiceSeparation:
    @pytest.mark.unit
    def test_moves_risk_block(self):
        t = "正文第一段判断。\n\n风险提示：若 X 则 Y。\n\n正文第二段结论。"
        out = separate_voices(t)
        assert "## 口径与风险说明" in out
        assert out.index("风险提示：") > out.index("第二段")
        assert "正文第一段判断。" in out.split("口径与风险说明")[0]

    @pytest.mark.unit
    def test_noop_when_absent(self):
        assert separate_voices("纯判断正文。") == "纯判断正文。"

    @pytest.mark.unit
    def test_never_rewrites_sentences(self):
        orig = "风险提示：碳酸锂若回升至15万元/吨则证伪逻辑。"
        out = separate_voices(f"判断段。\n\n{orig}\n\n结尾段。")
        assert "15万元/吨则证伪逻辑。" in out  # 原句原样保留
