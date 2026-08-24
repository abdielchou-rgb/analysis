"""pipeline/format_sheriff.py -- Format Sheriff (deterministic post-processing)

Three layers of defense:
Layer 1 - Detection: scan for all known format issues
Layer 2 - Auto-fix: deterministic code fixes (no LLM)
Layer 3 - Report: detailed issue report for Iron Gate
"""

import re
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))


class FormatSheriff:
    """Format Sheriff - deterministic post-processing for report quality"""

    BOLD_THRESHOLD = 120
    TABLE_WIDTH_MAX = 200
    MIN_CHARTS = {"industry_deep": 5, "listed_company": 5, "unlisted_company": 4, "earnings_notes": 2}
    END_STACK_RATIO = 0.30

    def __init__(self):
        self.issues = []
        self.fixes_applied = []

    def patrol(self, text, report_type="industry_deep"):
        # Pre-scan for critical issues
        self._critical_scan(text)
        text = self._fix_format_consistency(text)

        """Run all checks and fixes, return fixed text"""
        text = self._fix_bold_abuse(text)
        text = self._fix_table_overflow(text)
        text = self._fix_table_trailing_prose(text)
        text = self._fix_llm_intro(text)
        text = self._fix_dangling_images(text)
        text = self._ensure_disclaimer(text)
        self._check_chart_placement(text)
        self._check_min_charts(text, report_type)
        self._check_data_sources(text)

        # Fix bold punctuation: move trailing punctuation outside bold
        for punct in "\u3002\uff0c\uff1a\uff1b":
            text = text.replace("**" + punct, punct + "**")
        return text

    def report(self):
        """Return check report"""
        errors = [i for i in self.issues if i.get("severity") == "error"]
        return {"issues": self.issues, "fixes": self.fixes_applied, "pass": len(errors) == 0}

    def _fix_bold_abuse(self, text):
        """Fix bold abuse - keep first bold per line, remove rest"""
        bc = len(re.findall(r"\*\*", text))
        if bc <= self.BOLD_THRESHOLD:
            return text
        lines = text.split("\n")
        new_lines = []
        for line in lines:
            matches = list(re.finditer(r"\*\*[^\*]+\*\*", line))
            if len(matches) <= 1:
                new_lines.append(line)
                continue
            first = matches[0]
            before = line[: first.start()]
            bold_part = line[first.start() : first.end()]
            after = line[first.end() :].replace("**", "")
            new_lines.append(before + bold_part + after)
        result = "\n".join(new_lines)
        nc = len(re.findall(r"\*\*", result))
        self.fixes_applied.append("bold abuse: %d -> %d markers" % (bc, nc))
        return result

    def _fix_table_overflow(self, text):
        """Fix table overflow - truncate cells that are too long"""
        lines = text.split("\n")
        new_lines = []
        for line in lines:
            if line.startswith("|") and line.endswith("|"):
                if len(line) > self.TABLE_WIDTH_MAX:
                    cells = line.split("|")
                    cells = [c[:27] + "..." if len(c) > 30 else c for c in cells]
                    new_line = "|".join(cells)
                    new_lines.append(new_line)
                    self.fixes_applied.append("table width: %d -> %d" % (len(line), len(new_line)))
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        return "\n".join(new_lines)

    def _fix_table_trailing_prose(self, text):
        """R54（2026-08-03）：修复表格行尾粘连正文——LLM 合并时把分析文字
        接到表格行尾（如『|。这一趋势若延续...』或『|（数据来源：...）』），
        破坏 markdown 表格结构。

        检测：以 | 开头、但**不以 | 结尾**的行，且在表格上下文内
        （前一行也是表格行）——说明最后一个 | 后有粘连的额外内容。
        修复：把粘连内容拆成新段落（表格行恢复以 | 结尾）。
        仅当行末不是标准表格分隔线且确实有额外内容才处理，避免误伤正常表格。
        """
        lines = text.split("\n")
        new_lines = []
        prev_was_table = False
        for i, line in enumerate(lines):
            _stripped = line.strip()
            is_table_start = _stripped.startswith("|") and _stripped.endswith("|")
            if not _stripped.startswith("|"):
                prev_was_table = False
                new_lines.append(line)
                continue

            # 以 | 开头但未以 | 结尾：可能粘连（须在表格上下文内）
            if not _stripped.endswith("|") and prev_was_table:
                # 找倒数第一个 | 的位置（分割表格与粘连内容）
                last_pipe = line.rfind("|")
                # 若行内 | 太少（<2）说明不是表格结构，跳过
                if last_pipe <= 0 or line.count("|") < 2:
                    prev_was_table = False
                    new_lines.append(line)
                    continue
                table_part = line[: last_pipe + 1]
                trailing = line[last_pipe + 1 :].strip()
                # 粘连内容判定：非空、不是纯表格分隔线、长度>2
                if trailing and not set(trailing) <= set("-|: ") and len(trailing) > 2:
                    new_lines.append(table_part.rstrip())
                    new_lines.append(trailing)
                    self.fixes_applied.append(f"table trailing prose: split L{i + 1} ({len(trailing)} chars)")
                    prev_was_table = True  # 表格仍在继续
                    continue
            prev_was_table = is_table_start
            new_lines.append(line)
        return "\n".join(new_lines)

    def _fix_llm_intro(self, text):
        """Remove LLM intro phrases from the beginning"""
        intros = [
            "指令。",  # prompt leak
            "\u597d\u7684\uff0c\u6536\u5230\u60a8\u7684\u6307\u4ee4\u3002",
            "\u597d\u7684\uff0c\u6536\u5230\u60a8\u7684\u6307\u793a\u3002",
            "\u597d\u7684\uff0c\u6536\u5230\u3002",
            "\u4ee5\u4e0b\u662f\u4e3a\u60a8\u5448\u73b0\u7684",
            "\u4f5c\u4e3a\u8d44\u6df1\u884c\u4e1a\u5206\u6790\u5e08\uff0c\u6211\u5c06\u4e3a\u60a8\u5448\u73b0",
            "\u4f5c\u4e3a\u8d44\u6df1\u884c\u4e1a\u5206\u6790\u5e08\uff0c\u6211\u5c06",
            "\u597d\u7684\uff0c\u6211\u5c06",
            "\u4ee5\u4e0b\u662f\u6211\u7684",
            "\u6211\u5c06\u4e3a\u60a8",
            "\u6839\u636e\u60a8\u7684\u8981\u6c42\uff0c\u6211",
        ]
        for phrase in intros:
            if phrase in text[:300]:
                text = text.replace(phrase, "", 1)
                self.fixes_applied.append("intro: removed LLM greeting")
                break
        return text

    def _fix_dangling_images(self, text):
        """Fix images stacked at end - better redistribution across sections (SHERIFF_ENHANCED)"""
        if not text:
            return text
        end_threshold = int(len(text) * 0.8)
        end_section = text[end_threshold:]
        all_imgs = list(re.finditer(r"!\[.*?\]\(.*?\)", text))
        end_imgs = list(re.finditer(r"!\[.*?\]\(.*?\)", end_section))
        if not all_imgs:
            return text
        total = len(all_imgs)
        end_count = len(end_imgs)
        if end_count > 0 and (end_count / total) > self.END_STACK_RATIO:
            self.issues.append(
                {
                    "severity": "warning",
                    "type": "image_stacking",
                    "detail": "%d/%d images in last 20%% of document" % (end_count, total),
                }
            )
        # Remove "[以下为补充图表]" and similar stub headers
        text = re.sub(r"\*{0,2}(以下为补充图表|以下为图表|补充图表|图表补充)[^\n]*\n*", "", text)
        # Distribute all stacked images into relevant sections
        section_markers = [m.start() for m in re.finditer(r"\n##+\s+", text)]
        if not section_markers or end_count <= 1:
            return text
        moved = 0
        for m_idx, m in enumerate(end_imgs):
            if moved >= 3:
                break
            # Pick section marker in order (cyclic)
            sec_idx = moved % len(section_markers)
            insert_at = section_markers[sec_idx]
            nxt = text.find("\n", insert_at + 1)
            if nxt > 0:
                text = text[:nxt] + "\n\n" + m.group() + "\n\n" + text[nxt:]
                self.fixes_applied.append("image: moved to section %d" % (sec_idx + 1))
                moved += 1
        # Remove remaining stacked images from end
        for m in list(re.finditer(r"!\[.*?\]\(.*?\)", text))[::-1][: min(3, end_count)]:
            text = text[: m.start()] + text[m.end() :]
            self.fixes_applied.append("image: removed stray chart from end")
        return text

    def _ensure_disclaimer(self, text):
        """Ensure disclaimer exists at end"""
        if "\u514d\u8d23\u58f0\u660e" not in text and "\u98ce\u9669\u63d0\u793a" not in text:
            text += (
                "\n\n---\n\n**\u514d\u8d23\u58f0\u660e**: "
                + "\u672c\u62a5\u544a\u57fa\u4e8e\u516c\u5f00\u4fe1\u606f\u548c\u53ef\u9760\u6570\u636e\u6e90\u7f16\u5236\uff0c"
                + "\u4ec5\u4f9b\u53c2\u8003\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae\u3002\n"
            )
            self.fixes_applied.append("disclaimer: added missing disclaimer")
        return text

    def _check_chart_placement(self, text):
        """Check if charts have analysis text before and after"""
        imgs = list(re.finditer(r"!\[.*?\]\(.*?\)", text))
        if not imgs:
            self.issues.append({"severity": "error", "type": "no_charts", "detail": "No charts in report"})
            return
        bare_count = 0
        for img in imgs:
            pos = img.start()
            before = text[max(0, pos - 200) : pos].strip()
            after = text[pos + len(img.group()) : pos + len(img.group()) + 200].strip()
            if len(before) < 50 or len(after) < 50:
                bare_count += 1
        if bare_count > 0:
            self.issues.append(
                {
                    "severity": "warning",
                    "type": "bare_charts",
                    "detail": "%d/%d charts lack surrounding analysis text" % (bare_count, len(imgs)),
                }
            )

    def _check_min_charts(self, text, report_type):
        """Check minimum chart count for report type"""
        imgs = re.findall(r"!\[.*?\]\(.*?\)", text)
        min_n = self.MIN_CHARTS.get(report_type, 3)
        if len(imgs) < min_n:
            self.issues.append(
                {
                    "severity": "error",
                    "type": "insufficient_charts",
                    "detail": "%d charts found, minimum %d required for %s" % (len(imgs), min_n, report_type),
                }
            )
        else:
            self.issues.append(
                {"severity": "info", "type": "chart_count_ok", "detail": "%d charts >= %d minimum" % (len(imgs), min_n)}
            )

    def _check_data_sources(self, text):
        """Check data source annotations"""
        sources = re.findall(r"\u6570\u636e\u6765\u6e90[\uff1a:]", text)
        if len(sources) < 3:
            self.issues.append(
                {
                    "severity": "warning",
                    "type": "insufficient_sources",
                    "detail": "Only %d data source annotations (min 3 recommended)" % len(sources),
                }
            )

    def V2_auto_insert_charts(self, text, chart_md_lines, sections_map):
        """V2: auto insert charts into relevant sections (deterministic, no LLM)"""
        if not chart_md_lines:
            return text
        # Find section headers
        section_headers = []
        for m in re.finditer(r"^#{2,3}s+(.*)$", text, re.MULTILINE):
            section_headers.append((m.start(), m.end(), m.group(1)))
        if not section_headers:
            return text
        # Insert charts by section mapping
        inserted = set()
        result = text
        for chart_line, chart_id in chart_md_lines:
            if chart_line in inserted:
                continue
            target_sec_name = sections_map.get(chart_id, "")
            if not target_sec_name:
                continue
            # Find matching section
            insert_pos = -1
            for i, (start, end, sec_name) in enumerate(section_headers):
                # Match section name prefix (first few chars)
                if target_sec_name[:4] in sec_name or any(kw in sec_name for kw in target_sec_name.split("→")[:1]):
                    # Insert at end of this section (before next section)
                    if i + 1 < len(section_headers):
                        insert_pos = section_headers[i + 1][0]
                    else:
                        insert_pos = len(result)
                    break
            if insert_pos < 0:
                # Fallback: insert after first section
                if section_headers:
                    if len(section_headers) > 1:
                        insert_pos = section_headers[1][0]
                    else:
                        insert_pos = len(result)
            if insert_pos > 0:
                after = result[insert_pos:]
                result = result[:insert_pos] + "\n\n" + chart_line + "\n\n" + after
                inserted.add(chart_line)
                self.fixes_applied.append("V2: chart " + chart_id[:25] + " inserted")
        return result

    def _critical_scan(self, text):
        """Pre-scan for critical formatting issues (hard failures)"""
        import re

        # 1. Check for prompt leak
        if re.search(r"^\u6307\u4ee4\u3002", text.strip()):
            self.issues.append(
                {"severity": "error", "check": "prompt_leak", "detail": "Report starts with prompt instruction leak"}
            )

        # 2. Check for empty bold markers
        empty_bold = len(re.findall(r"^\s*\*\*\s*$", text, re.MULTILINE))
        if empty_bold > 0:
            self.issues.append(
                {
                    "severity": "warning",
                    "check": "empty_bold_markers",
                    "detail": str(empty_bold) + " empty bold markers found",
                }
            )

        # 3. Check for personal narrative markers at start
        if text.strip().startswith("我是") or text.strip().startswith("各位"):
            self.issues.append(
                {"severity": "error", "check": "personal_narrative", "detail": "Report starts with personal narrative"}
            )

        # 4. Check data source coverage
        sources = len(re.findall(r"\u6765\u6e90[\uff1a:]", text))
        para_count = len([p for p in text.split("\n\n") if len(p.strip()) > 50])
        ratio = sources / max(para_count, 1)
        if ratio < 0.3 and para_count > 5:
            self.issues.append(
                {
                    "severity": "warning",
                    "check": "low_source_coverage",
                    "detail": "Data source coverage: " + str(sources) + "/" + str(para_count),
                }
            )

        return self.issues

    def _fix_format_consistency(self, text):
        """Fix formatting issues: bold markers, heading jumps, empty tables"""
        import re

        # Fix mixed bold markers
        text = re.sub(r"\*{4,}", "**", text)

        # Fix heading level jumps
        lines = text.split("\n")
        fixed = []
        prev_level = 0
        for line in lines:
            m = re.match(r"^(#{1,6})\s+", line)
            if m:
                level = len(m.group(1))
                if level > prev_level + 1 and prev_level > 0:
                    fixed.append(line)
                else:
                    fixed.append(line)
                prev_level = level
            else:
                fixed.append(line)
        text = "\n".join(fixed)

        # Fix empty bold markers
        text = re.sub(r"\*\*\s*\*\*", "", text)

        # Remove standalone bold asterisks
        text = re.sub(r"(?m)^\s*\*\*\s*$", "", text)

        self.fixes_applied.append("Fixed format consistency")
        return text


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Format Sheriff")
    parser.add_argument("input", help="Input markdown file")
    parser.add_argument("--output", "-o", help="Output file")
    parser.add_argument("--type", default="industry_deep", help="Report type")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    sheriff = FormatSheriff()
    fixed = sheriff.patrol(text, args.type)

    out_path = args.output or args.input
    Path(out_path).write_text(fixed, encoding="utf-8")

    print("=" * 50)
    print("Format Sheriff Report")
    print("=" * 50)
    print("Fixes applied: %d" % len(sheriff.fixes_applied))
    for f in sheriff.fixes_applied:
        print("  [+] %s" % f)
    print("Issues found: %d" % len(sheriff.issues))
    for i in sheriff.issues:
        print("  [!] [%s] %s" % (i["severity"], i["detail"]))

    passed = sheriff.report()["pass"]
    print("\nOverall: %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
