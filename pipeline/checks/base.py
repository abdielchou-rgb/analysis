# -*- coding: utf-8 -*-
"""IronGate 共享基础模块 — 类型/日志/辅助函数。

R61（2026-08-03）：为拆分 iron_gate.py 提供公共依赖。
iron_gate.py 和 pipeline/checks/*_mixin.py 都从本模块导入共享类型，
避免循环导入（iron_gate 继承 mixin，mixin 需要 GateCheckResult）。
"""
from __future__ import annotations
import json
import logging
import re
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger("2hao.iron_gate")

_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class GateCheckResult:
    """单个检查的结果。"""
    name: str
    passed: bool
    score: float
    details: str = ""
    severity: str = "warning"  # error / warning / info


@dataclass
class GateReport:
    """Gate 校验报告。"""
    passed: bool = False
    overall_score: float = 0.0
    checks: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)

    @property
    def hard_fail_errors(self):
        """Return checks matching hard_fail names that did not pass"""
        hard_names = ["personal_narrative", "section_continuity", "table_quality_md",
                      "placeholder_charts", "forbidden_patterns", "bold_call", "so_what_chain",
                      "cross_section_consistency"]
        return [c for c in self.checks if c.name in hard_names and not c.passed]

    def to_dict(self):
        return {"passed": self.passed, "overall_score": self.overall_score,
                "checks": [asdict(c) for c in self.checks],
                "failures": self.failures, "suggestions": self.suggestions}

    def to_text(self):
        lines = ["=" * 60, "Iron Gate 校验报告", "=" * 60,
                 "状态: %s" % ("PASS" if self.passed else "FAIL"),
                 "综合评分: %.2f/1.00" % self.overall_score]
        for c in self.checks:
            icon = "+" if c.passed else "-"
            lines.append("  [%s] %s: %.2f - %s" % (icon, c.name, c.score, c.details[:80]))
        if self.failures:
            lines.extend(["", "失败项:", *["  - %s" % f[:80] for f in self.failures[:10]]])
        return "\n".join(lines)


def detect_value_conflicts(report_text: str, data_dict: dict) -> list:
    """财务数值冲突检测（模块级辅助，供 data_quality mixin 使用）。"""
    conflicts = []
    try:
        # 提取 data_dict 中带年份的数值键
        # R88c（2026-08-06）：仅收集语义明确的 % 类指标键（margin/net_profit/roe），
        # 排除 revenue_trend/market_size 等规模类键，也排除 profitability——
        # 该键语义不明（行业毛利率/净利率不确定），若纳入会拿"行业盈利数据14"
        # 与正文"2025年毛利率44.83%"（柯力公司层面毛利）错配报假冲突。
        # 正文模式只匹配"毛利率|净利率|ROE"，必须与 data_dict 键一一对应。
        known = {}
        for k, v in data_dict.items():
            if isinstance(k, str) and v is not None:
                # 形如 margin_2024 / net_profit_2024 / roe_2024
                m = re.match(r'^(?:margin|net_profit|roe)_(\d{4})$', k)
                if m:
                    try:
                        known.setdefault(m.group(1), {})[k.split('_')[0]] = float(v)
                    except (TypeError, ValueError):
                        pass
        if not known:
            return conflicts
        # 报告正文找"YYYY年XX Y%"模式，与 data_dict 对比
        generic = r'(?:毛利率|净利率|ROE)'
        for year, vals in known.items():
            expected_unit = "%"
            pat = re.compile(
                rf'(?:{year}年?(?:[^\n。]{{0,12}})?(?:{generic})|(?:{generic})[^\n。]{{0,12}}?{year}年?)'
                rf'[^\n。]{{0,20}}?(?<![\d.])(\d+(?:\.\d{{1,3}})?)\s*({expected_unit})'
            )
            for m in pat.finditer(report_text):
                try:
                    body_val = float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
                unit = m.group(2)
                for key, known_val in vals.items():
                    if abs(body_val - known_val) / max(abs(known_val), 1e-9) < 0.10:
                        break
                else:
                    conflicts.append(
                        f"{year}年 正文写{body_val:.0f}{unit} vs 数据层{list(vals.values())[0]:.0f}")
                    break  # 每年报一处
    except Exception:
        pass
    return conflicts[:5]
