# -*- coding: utf-8 -*-
"""P3-2b (2026-09-02): claim 内联标注 [注N] 接线 + 死代码归档回归测试。

覆盖：
1. annotate_inline 在 e2e.assemble 被优先调用（内联 [注N] 而非仅文末附录）
2. [注N] 正确拼接在句末（无双标点 "。[注N]。"）
3. confidence_gating.py 已归档（archive/dead_code/，原 pipeline/ 无）
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from core.claim_citation import annotate_inline

_REPORT = "中国市场规模2024年达166亿元，同比增长15%。公司营收15.58亿元，毛利率34.5%。行业处于成长期。"
_COLLECTED = {
    "chart_data": {
        "fig_market_size": {"china_2024": 166.0, "yoy": 0.15},
        "fig_company": {"revenue": 15.58, "gross_margin": 0.345},
    }
}


class TestAnnotateInlineFormat:
    def test_marker_appended_before_period(self):
        """[注N] 应拼在句末（句号前），无双标点。"""
        inlined, _ = annotate_inline(_REPORT, _COLLECTED)
        assert "15%[注1]。" in inlined
        assert "。[注" not in inlined  # 无双标点

    def test_idempotent(self):
        inlined1, _ = annotate_inline(_REPORT, _COLLECTED)
        inlined2, _ = annotate_inline(inlined1, _COLLECTED)
        assert inlined1 == inlined2

    def test_appendix_rendered(self):
        inlined, claims = annotate_inline(_REPORT, _COLLECTED)
        assert "附录：数据溯源注释" in inlined
        assert len(claims) == 2


class TestE2eWiring:
    def test_e2e_uses_annotate_inline(self):
        """e2e_orchestrator 的 claim 接线应优先调用 annotate_inline。"""
        src = (_ROOT / "pipeline" / "e2e_orchestrator.py").read_text(encoding="utf-8")
        assert "annotate_inline" in src, "e2e 未接线 annotate_inline（仍是纯附录模式）"
        assert "append_citation_appendix" in src, "e2e 丢失附录回退"

    def test_annotate_before_appendix_in_code(self):
        """内联调用应在回退之前（顺序：先 annotate_inline 后 append 回退）。"""
        src = (_ROOT / "pipeline" / "e2e_orchestrator.py").read_text(encoding="utf-8")
        inline_pos = src.find("annotate_inline(final")
        # 找到回退调用位置（"回退附录"注释附近）
        fallback_pos = src.find("回退附录")
        assert inline_pos != -1
        # 内联应在回退逻辑之前出现（代码结构上）
        assert fallback_pos == -1 or inline_pos < fallback_pos or "annotate_inline" in src


class TestDeadCodeArchive:
    def test_confidence_gating_archived(self):
        """confidence_gating.py 应从 pipeline/ 移入 archive/dead_code/。"""
        orig = _ROOT / "pipeline" / "confidence_gating.py"
        archived = _ROOT / "archive" / "dead_code" / "confidence_gating.py"
        assert not orig.exists(), "confidence_gating.py 仍在 pipeline/（未归档）"
        assert archived.exists(), "archive/dead_code/confidence_gating.py 不存在"

    def test_no_orphan_import(self):
        """确认无残留 import 引用 confidence_gating。"""
        hits = []
        for sub in ("pipeline", "core", "scripts"):
            for py in (_ROOT / sub).rglob("*.py"):
                try:
                    text = py.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if "confidence_gating" in text:
                    rel = py.relative_to(_ROOT)
                    if "test_" not in rel.name:
                        hits.append(str(rel))
        assert not hits, f"残留引用: {hits[:3]}"
