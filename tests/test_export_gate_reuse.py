# -*- coding: utf-8 -*-
"""P1-2 修复回归测试（2026-09-06）：export_report 复用管线 gate_result。

背景：validate 节点已运行 IronGate 并通过（gate_result in context），但 e2e_orchestrator
export_docx 调用 export_report 时漏传 pipe_gate_result → export 永远落入"独立重跑
IronGate"分支 → enriched_text（含 provenance 注释）与管线校验文本不一致 → 两套 gate
分数不一致 → 高分报告被误阻断。

本测试验证：传入 passed 的 pipe_gate_result 时，export_report 走复用分支，
不再独立实例化 IronGate。
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _minimal_docx(path: Path):
    """构造可通过 DOCX 空段率/无 AI 标注检查的最小 docx。"""
    import zipfile

    document_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        "<w:body><w:p><w:r><w:t>报告正文内容</w:t></w:r></w:p></w:body></w:document>"
    )
    content_types = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
        "<Default Extension='xml' ContentType='application/xml'/>"
        "<Override PartName='/word/document.xml' "
        "ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
        "</Types>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("word/document.xml", document_xml)


class _FakeExporter:
    def __init__(self, out_path: Path):
        self.out_path = out_path

    def to_docx(self, markdown_text, output_path, chart_paths=None):
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        _minimal_docx(self.out_path)
        return str(self.out_path)


@pytest.fixture
def _patch_export_heavy(monkeypatch, tmp_path):
    """打桩 export_report 的重依赖：指纹、exporter、visual gate。"""
    import export.report_gate as rg

    docx_path = tmp_path / "report.docx"

    def _noop_fp(*args, **kwargs):
        return None

    monkeypatch.setattr(rg, "_verify_pipeline_fingerprint", _noop_fp)

    def _fake_exporter_factory(company_name=None, style_id=None, title=None):
        return _FakeExporter(docx_path)

    import export.exporter as ex

    monkeypatch.setattr(ex, "ReportExporter", _fake_exporter_factory)

    def _fake_vg_check(docx, report_type):
        return {"score": 1.0, "issues": []}

    monkeypatch.setattr(rg, "vg_check", _fake_vg_check, raising=False)
    # visual_gate 从模块 import check as vg_check —— 也直接改模块函数兜底
    import export.visual_gate as vg

    monkeypatch.setattr(vg, "check", _fake_vg_check, raising=False)
    return docx_path


class TestExportGateReuse:
    def test_reuses_pipe_result_when_passed(self, _patch_export_heavy, monkeypatch):
        """传入 passed pipe_gate_result → 不实例化独立 IronGate。"""
        import export.report_gate as rg

        # 哨兵：若 export 独立重跑 IronGate，from_text 会被调用 → 触发 AssertionError
        class _SentinelGate:
            @staticmethod
            def from_text(*a, **k):
                raise AssertionError("IronGate 独立重跑被触发——pipe_gate_result 未被复用")

        monkeypatch.setattr("pipeline.iron_gate.IronGate", _SentinelGate)

        from pipeline.checks.base import GateCheckResult, GateReport

        gr = GateReport()
        gr.overall_score = 0.87
        gr.passed = True
        gr.failures = []
        gr.checks = [GateCheckResult(name="content_volume", passed=True, score=1.0, severity="warning")]

        docx = rg.export_report(
            "# 测试报告\n\n目标价 100 元。",
            str(_patch_export_heavy),
            report_type="listed_company",
            style="cicc",
            title="测试",
            pipe_gate_result=gr,
        )
        assert docx == str(_patch_export_heavy)
        assert Path(docx).exists()

    def test_runs_standalone_when_missing(self, _patch_export_heavy, monkeypatch):
        """pipe_gate_result 缺失 → export 兜底独立重跑 IronGate（原行为保留）。"""
        import export.report_gate as rg

        calls = {"n": 0}

        class _FakeGate:
            def __init__(self, *a, **k):
                pass

            def run_all(self):
                calls["n"] += 1
                from pipeline.checks.base import GateReport

                gr = GateReport()
                gr.overall_score = 1.0
                gr.passed = True
                return gr

            @staticmethod
            def from_text(*a, **k):
                return _FakeGate()

        monkeypatch.setattr("pipeline.iron_gate.IronGate", _FakeGate)
        docx = rg.export_report(
            "# 测试报告\n\n目标价 100 元。",
            str(_patch_export_heavy),
            report_type="listed_company",
            style="cicc",
            title="测试",
            pipe_gate_result=None,
        )
        assert calls["n"] == 1, "缺 pipe_gate_result 时应独立运行一次 IronGate"
        assert Path(docx).exists()
