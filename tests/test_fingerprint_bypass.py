# -*- coding: utf-8 -*-
"""P0-1 (2026-09-01): 管线出口指纹绕过漏洞回归测试。

覆盖三个此前可绕过的路径：
1. 跨资产复用指纹（把 A 资产指纹改名给 B 资产）→ 必须阻断
2. 正文被篡改 / 指纹从别的报告复制 → report_sha256 不符 → 必须阻断
3. 指纹 JSON 损坏 → 必须阻断（此前 fail-open 放行）
4. 通配扫描被移除：无精确指纹文件时，即使目录里有其他资产指纹 → 必须阻断
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from export.report_gate import GateBlockedError, _verify_pipeline_fingerprint


def _sha256(content) -> str:
    import hashlib

    return hashlib.sha256(content.encode("utf-8") if isinstance(content, str) else content).hexdigest()


@pytest.fixture()
def fp_env(tmp_path):
    """构造报告输出目录 + 一份合法的指纹 + 一份报告正文。"""
    report_md = tmp_path / "测试资产.md"
    report_md.write_text("# 测试报告\n\n核心判断：买入。", encoding="utf-8")
    fingerprint = {
        "asset": "测试资产",
        "report_type": "listed_company",
        "style": "cicc",
        "gate_score": 0.9,
        "gate_passed": True,
        "via_pipeline": True,
        "pipeline": "E2EOrchestratorV2",
        "report_sha256": _sha256(report_md.read_bytes()),
    }
    fp_path = tmp_path / "测试资产_pipeline_fingerprint.json"
    fp_path.write_text(json.dumps(fingerprint, ensure_ascii=False), encoding="utf-8")
    return tmp_path, report_md


def _blocked_with(fn):
    """断言 fn 抛出 GateBlockedError，返回 issues 明细（错误详情在 .issues 而非 str）。"""
    with pytest.raises(GateBlockedError) as ei:
        fn()
    return "\n".join(ei.value.issues)


class TestFingerprintBypass:
    def test_valid_fingerprint_passes(self, fp_env):
        """合法指纹 + 未改正文 → 通过。"""
        tmp_path, report_md = fp_env
        _verify_pipeline_fingerprint(str(report_md), "测试资产")  # 不应抛异常

    def test_cross_asset_reuse_blocked(self, fp_env):
        """跨资产复用：B 资产引用 A 资产的指纹 → 阻断（资产名校验或找不到指纹均可）。"""
        tmp_path, report_md = fp_env
        msg = _blocked_with(lambda: _verify_pipeline_fingerprint(str(report_md), "另一个资产"))
        assert "未找到管线指纹" in msg or "资产不匹配" in msg

    def test_wildcard_scan_removed(self, fp_env):
        """通配扫描洞：B 资产无指纹，但目录里有 A 资产指纹 → 必须阻断（不再取 matches[0]）。"""
        tmp_path, report_md = fp_env
        other = tmp_path / "b_report.md"
        other.write_text("B 报告", encoding="utf-8")
        msg = _blocked_with(lambda: _verify_pipeline_fingerprint(str(other), "b_report"))
        assert "未找到管线指纹" in msg

    def test_tampered_report_blocked(self, fp_env):
        """正文被篡改：指纹哈希与报告不符 → 阻断。"""
        tmp_path, report_md = fp_env
        report_md.write_text("# 测试报告\n\n核心判断：卖出。（被篡改）", encoding="utf-8")
        msg = _blocked_with(lambda: _verify_pipeline_fingerprint(str(report_md), "测试资产"))
        assert "report_sha256" in msg or "不匹配" in msg

    def test_copied_fingerprint_blocked(self, fp_env):
        """复制改名伪造：把 A 的指纹复制给 B（asset 字段不符）→ 阻断。"""
        tmp_path, report_md = fp_env
        report_b = tmp_path / "b_report.md"
        report_b.write_text("B 报告正文", encoding="utf-8")
        # 复制 A 指纹但没改 asset 字段 → 校验时 asset 不匹配应阻断
        (tmp_path / "b_report_pipeline_fingerprint.json").write_text(
            (tmp_path / "测试资产_pipeline_fingerprint.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
        msg = _blocked_with(lambda: _verify_pipeline_fingerprint(str(report_b), "b_report"))
        assert "资产不匹配" in msg or "report_sha256" in msg or "不匹配" in msg

    def test_corrupted_fingerprint_blocked(self, fp_env):
        """指纹 JSON 损坏 → 阻断（fail-closed，不再放行）。"""
        tmp_path, report_md = fp_env
        (tmp_path / "测试资产_pipeline_fingerprint.json").write_text("{not valid json", encoding="utf-8")
        msg = _blocked_with(lambda: _verify_pipeline_fingerprint(str(report_md), "测试资产"))
        assert "损坏" in msg or "解析失败" in msg

    def test_no_via_pipeline_blocked(self, fp_env):
        """指纹缺 via_pipeline=true → 阻断。"""
        tmp_path, report_md = fp_env
        bad = {
            "asset": "测试资产",
            "gate_score": 0.9,
            "report_sha256": _sha256(report_md.read_bytes()),
        }
        (tmp_path / "测试资产_pipeline_fingerprint.json").write_text(
            json.dumps(bad, ensure_ascii=False), encoding="utf-8"
        )
        msg = _blocked_with(lambda: _verify_pipeline_fingerprint(str(report_md), "测试资产"))
        assert "via_pipeline" in msg
