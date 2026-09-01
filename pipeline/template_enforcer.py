"""TemplateEnforcer - 模板执行强制器

确保报告模板被正确渲染，样式一致。
"""

import re as _re
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))


class TemplateEnforcer:
    """Template执行强制器 — 检查报告模板是否被正确渲染，样式一致。"""

    def __init__(self, sac_loader=None):
        self.sac = sac_loader
        self._rules = self._load_rules()
        self.violations = []
        self.fixes = []

    def _load_rules(self) -> dict:
        rules_path = _ANALYST_ROOT / "pipeline" / "reporting_rules.yaml"
        if not rules_path.exists():
            return {}
        try:
            import yaml

            with open(rules_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def enforce(self, report_text: str, report_type: str = "industry_deep", data: dict = None) -> dict:
        """对报告文本执行所有模板规则检查与自动修复。

        Returns:
            {"pass": bool, "violations": [str], "fixes": [str],
             "report_text": str (自动修复后的文本)}
        """
        self.violations = []
        self.fixes = []
        text = report_text

        # P0 - SAC 覆盖检查
        if self.sac:
            text = self._check_sac_coverage(text, report_type)

        # P0 - 表格完整性检查
        text = self._check_tables(text, report_type, data)

        # P0 - 章节内容检查（最小字数）
        text = self._check_sections(text, report_type)

        # P0 - 价格/估值倍数一致性检查
        text = self._check_price_consistency(text)

        # P1-F（2026-07-31 审计修复）：编号冲突检测——同层级出现两套编号即报错
        text = self._check_numbering_conflict(text)

        # P1 - 数据来源检查
        text = self._check_data_sources(text, data)

        # P1 - 图表数量检查
        text = self._check_charts(text, report_type)

        return {
            "pass": len([v for v in self.violations if v.startswith("[BLOCK]")]) == 0,
            "violations": self.violations,
            "fixes": self.fixes,
            "report_text": text,
        }

    def _check_sac_coverage(self, text: str, report_type: str) -> str:
        """检查SAC维度在报告中的覆盖情况——维度缺失超过阈值时告警但不阻断。"""
        required = self.sac.get_dimensions() if self.sac else []
        missing = []
        for dim in required:
            if isinstance(dim, dict):
                dname = dim.get("id", dim.get("question", ""))[:20]
                if dname and dname not in text:
                    missing.append(dname)
        if missing and len(missing) >= 10:
            self.violations.append(f"[WARN] SAC覆盖偏少: 覆盖{len(required) - len(missing)}/{len(required)}")
        return text

    def _check_tables(self, text: str, report_type: str, data: dict = None) -> str:
        """检查表格数量是否达标——不足时从财务数据自动生成摘要表。"""
        min_tables = 3
        if self.sac:
            cc = self.sac.get_chart_config()
            min_tables = cc.get("min_tables", 3)

        table_count = len(_re.findall(r"^\|.+\|.+\|$", text, _re.MULTILINE))
        if table_count >= min_tables:
            return text

        # 当 tables==0 时降级为 WARN（数据不足时表格自然缺失）
        _sev = "[WARN]" if table_count == 0 else "[BLOCK]"
        self.violations.append(f"{_sev} 表格不足: {table_count}/{min_tables}")

        # 数据足够时自动补充财务摘要表
        if data and isinstance(data, dict):
            financials = data.get("financials", data.get("financial_data", data.get("chart_data", {})))
            if financials:
                table_md = self._build_financial_table(financials)
                if table_md and len(table_md) > 50:
                    # 自动追加在报告末尾作为附录
                    text = text + "\n\n" + table_md
                    self.fixes.append(f"[AUTO] 自动补充财务数据表 ({len(table_md)} chars)")
                    return text

        return text

    def _build_financial_table(self, data: dict) -> str:
        """从财务数据构建markdown表格——用于自动补充缺失的表格。"""
        lines = []
        if not isinstance(data, dict):
            return ""
        # 提取财务年份
        years = sorted([k for k in data.keys() if isinstance(k, str) and k.isdigit() and len(k) == 4], reverse=True)[:5]
        if not years:
            return ""
        metrics = ["revenue", "net_profit", "gross_margin", "roe"]
        labels = {"revenue": "营收", "net_profit": "净利润", "gross_margin": "毛利率", "roe": "ROE"}
        header = "| 指标 | " + " | ".join(years) + " |"
        sep = "|" + "---|" * (len(years) + 1)
        lines.extend([header, sep])
        for m in metrics:
            row = [labels.get(m, m)]
            for y in years:
                yd = data.get(y, {})
                val = yd.get(m, "")
                row.append(str(val) if val else "-")
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def _check_sections(self, text: str, report_type: str) -> str:
        """检查各章节内容量——低于50字符的章节标记告警。"""
        sections = list(_re.finditer(r"^#{2,3}\s+(.+)$", text, _re.MULTILINE))
        for i, m in enumerate(sections):
            start = m.end()
            end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            content = text[start:end].strip()
            # 去除图表/表格引用后检查纯文本量
            pure_text = _re.sub(r"!\[.*?\]\(.*?\)", "", content)
            pure_text = _re.sub(r"\|.*\|", "", pure_text)
            if len(pure_text.strip()) < 50:
                self.violations.append(f'[WARN] 章节内容不足: "{m.group(1)[:30]}" ({len(pure_text.strip())} chars)')
        return text

    def _check_price_consistency(self, text: str) -> str:
        """检查价格/估值倍数一致性——同一倍数在全文只能有一个值。"""
        # 检查PS倍数不一致
        ps_matches = _re.findall(r"([0-9.]+)x\s*PS", text, _re.IGNORECASE)
        if len(ps_matches) >= 2:
            unique = set(ps_matches)
            if len(unique) > 1:
                # 统一为标准值
                standard = ps_matches[-1]
                self.violations.append(f"[WARN] PS倍数不一致: {ps_matches} (统一为{standard})")
                text = _re.sub(r"[0-9.]+x\s*PS", f"{standard}x PS", text)
                self.fixes.append(f"[AUTO] 统一PS倍数: {standard}x")
        return text

    def _check_numbering_conflict(self, text: str) -> str:
        """P1-F：检测章节编号冲突——同一层级出现两套"一、二、三…"编号。

        双模板拼接的典型症状：SAC 三段式 + 旧六段式各带一套"一、"编号。
        R3（2026-07-31 Marvis 审计）：从 WARN 升级为 BLOCK——编号冲突直接阻断导出，
        因为双编号意味着章节骨架错乱，报告不可交付。
        """
        # 收集所有"一、标题" 形式的一级编号
        first_level = _re.findall(r"^([一二三四五六七八九十]+)、", text, _re.MULTILINE)
        if len(first_level) >= 2:
            unique = list(dict.fromkeys(first_level))
            if len(unique) < len(first_level):
                # 有重复编号（如"一、"出现两次）——双模板症状
                dup = [n for n in unique if first_level.count(n) > 1]
                if dup:
                    self.violations.append(
                        f'[BLOCK] 章节编号冲突: "{dup[0]}、" 出现 {first_level.count(dup[0])} 次'
                        f"（疑似双模板拼接，章节骨架错乱不可交付）"
                    )
        return text

    def _check_data_sources(self, text: str, data: dict = None) -> str:
        """检查数据来源标注——确保主要数据点标明了来源。"""
        source_markers = [m.start() for m in _re.finditer(r"来源[：:]|数据来源|Source|source", text)]
        if len(source_markers) < 3:
            self.violations.append(f"[WARN] 数据来源标注不足: {len(source_markers)}/3")
        return text

    def _check_charts(self, text: str, report_type: str) -> str:
        """检查图表嵌入数量是否达标。"""
        # R74（2026-08-05）：Gate 评审时报告仍为 {{CHART:...}} 占位符格式，
        # 尚未到 assemble 节点（assemble 在 Gate 通过后才跑）。
        # 需同时识别占位符和最终 Markdown 图片引用，否则图表数恒为 0 死锁。
        charts = _re.findall(r"(\{\{CHART:[^}]+\}\})|(!\[.*?\]\(.*?\))", text)
        min_charts = 5
        if self.sac:
            cc = self.sac.get_chart_config()
            min_charts = cc.get("min_charts", 5)
        if len(charts) < min_charts:
            # 当 charts==0 时，降级为 WARN 而非 BLOCK：
            # chart_pipeline 已根据数据充分性决定是否生成图表，
            # 模板不应覆盖数据充分性判断。
            _sev = "[WARN]" if len(charts) == 0 else "[BLOCK]"
            self.violations.append(f"{_sev} 图表不足: {len(charts)}/{min_charts}")
        return text

    def report(self) -> dict:
        return {
            "violations": self.violations,
            "fixes": self.fixes,
            "total_violations": len(self.violations),
            "blocking": len([v for v in self.violations if v.startswith("[BLOCK]")]),
        }
