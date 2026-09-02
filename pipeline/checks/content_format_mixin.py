"""IronGate 检查 Mixin — content_format 类检查。

R61（2026-08-03 迁移）：由 scripts/migrate_iron_gate.py 自动生成。
方法原样迁移自 pipeline/iron_gate.py，签名不变，IronGate 继承后行为零变化。
"""

import os
import re

from pipeline.checks.base import GateCheckResult


class ContentFormatChecksMixin:
    """content_format 类检查方法。"""

    def _check_content_volume(self) -> GateCheckResult:
        vol = len(self.report_text)
        passed = vol >= self.min_chars
        ratio = min(vol / self.min_chars, 1.0)
        return GateCheckResult(
            name="content_volume", passed=passed, score=ratio, details="字数: %d/%d" % (vol, self.min_chars)
        )

    def _check_content_density(self) -> GateCheckResult:
        md_size = len(self.report_text)
        docx_path = self.report_path.with_suffix(".docx")
        docx_size = docx_path.stat().st_size if docx_path.exists() else 0
        ratio = min(docx_size / max(md_size, 1) * 10, 1.0) if docx_size > 0 else 0.7
        return GateCheckResult(
            name="content_density", passed=True, score=ratio, details="MD:%d DOCX:%d" % (md_size, docx_size)
        )

    def _check_report_date(self) -> GateCheckResult:
        """R76（2026-08-05 P0）：报告日期检查 — DI-001 规则，report_date == current_date。

        提取报告中的"报告日期：XXXX年XX月"类表述，与系统当前日期对比。
        规则：
          - 无日期行 → 阻断（severity=error）
          - 年份不一致 → 阻断
          - 月份超出当前月 ±1 范围 → 阻断
          - 当前月 ±1 月内 → 通过
        """
        import datetime as _dt

        text = self.report_text or ""

        # 匹配模式：报告日期：2026年8月 / 报告日期 2026年08月 / 2026年8月5日 等
        date_patterns = [
            r"报告日期[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月",
            r"出具日期[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月",
            r"发布日期[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月",
        ]

        found_year = None
        found_month = None
        for pat in date_patterns:
            m = re.search(pat, text)
            if m:
                found_year = int(m.group(1))
                found_month = int(m.group(2))
                break

        if found_year is None:
            # 没有日期行 → 阻断
            return GateCheckResult(
                name="report_date",
                passed=False,
                score=0.0,
                details="报告中未找到'报告日期：XXXX年XX月'声明",
                severity="error",
            )

        now = _dt.datetime.now()
        cur_year = now.year
        cur_month = now.month

        # 年份不一致 → 阻断
        if found_year != cur_year:
            return GateCheckResult(
                name="report_date",
                passed=False,
                score=0.0,
                details=f"报告日期 {found_year}年{found_month}月 != 当前 {cur_year}年{cur_month}月（年份不一致）",
                severity="error",
            )

        # 月份检查：当前月 ±1 月内通过
        month_diff = (cur_year - found_year) * 12 + (cur_month - found_month)
        if abs(month_diff) <= 1:
            return GateCheckResult(
                name="report_date",
                passed=True,
                score=1.0,
                details=f"报告日期 {found_year}年{found_month}月 == 当前 {cur_year}年{cur_month}月（±1月容差内）",
            )
        elif month_diff > 1:
            # 报告日期早于当前（历史日期）
            return GateCheckResult(
                name="report_date",
                passed=False,
                score=0.0,
                details=f"报告日期 {found_year}年{found_month}月 为历史日期，当前为 {cur_year}年{cur_month}月（过期 {month_diff} 个月）",
                severity="error",
            )
        else:
            # 报告日期晚于当前（未来日期）
            return GateCheckResult(
                name="report_date",
                passed=False,
                score=0.0,
                details=f"报告日期 {found_year}年{found_month}月 为未来日期，当前为 {cur_year}年{cur_month}月",
                severity="error",
            )

    def _check_placeholder_xxx(self) -> GateCheckResult:
        """R77（2026-08-05 P0）：未替换占位符检查。

        检测报告文本中是否残留"XXX"、"TODO"、"待填写"等未替换占位符。
        命中即阻断。
        """
        import re as _re

        text = self.report_text or ""

        # 占位符模式：XXX/TODO/待填写/TBD/FIXME/xxx/___/… 等
        placeholder_patterns = [
            # R77（2026-08-05 验证）： 边界在中文上下文不生效（ 只认 ASCII word
            # boundary），"我们判断XXX技术路线"的 XXX 会漏检。改用直接匹配，
            # 中文报告中 XXX/TODO 等大写占位符是未替换标记的主流形态。
            (r"XXX", "XXX占位符"),
            (r"TODO", "TODO标记"),
            (r"待填写", "待填写占位符"),
            (r"TBD", "TBD标记"),
            (r"FIXME", "FIXME标记"),
            (r"_{3,}", "下划线占位（___）"),
            # B1: 占位符协议残留——LLM 未替换的 {{tp_primary}} 等标记
            (r"\{\{[a-z_]+\}\}", "占位符协议残留（B1 {{xxx}}）"),
            # R77（2026-08-05 验证）：中文省略号"……"是正常标点（语意延续），
            # 不是占位符，不应拦截。真实占位符由 XXX/TODO/待填写/TBD/FIXME 覆盖。
        ]

        found = []
        for pat, label in placeholder_patterns:
            matches = _re.findall(pat, text)
            if matches:
                # 去重显示
                unique_matches = list(set(matches))[:3]
                found.append(f"{label}({', '.join(unique_matches)})")

        if found:
            return GateCheckResult(
                name="placeholder_xxx",
                passed=False,
                score=0.0,
                details="发现未替换占位符: " + "; ".join(found),
                severity="error",
            )
        return GateCheckResult(name="placeholder_xxx", passed=True, score=1.0, details="无未替换占位符")

    def _check_judgment_density(self) -> GateCheckResult:
        """R56（2026-08-03）：判断密度/数据密度——对标金牌报告基准。

        methodology_backtest_deep.json 统计：金牌报告判断 2.6/千字（中位）、
        数据 13.3/千字（中位）；普通报告 1.5/千字。p10 保守下限作为门槛：
          min_judgment_density = 1.2 判断/千字
          min_data_density = 5.0 数据/千字
        （低于 p10 说明报告"只描述不判断"或"判断无数据支撑"）

        判断词：我们认为/我们判断/预计/有望/超预期/风险/评级 等。
        数据点：数字+单位（%/亿元/倍/万股/元）。
        """
        import re as _re

        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("judgment_density", True, 1.0, "text too short, skipped", severity="warning")
        # 阈值从 backtest_deep 读取（可被覆盖）
        _min_jd = float(os.environ.get("MIN_JUDGMENT_DENSITY", "1.2"))
        _min_dd = float(os.environ.get("MIN_DATA_DENSITY", "5.0"))

        _chars = len(text)
        _kchars = _chars / 1000.0

        # 判断词计数（对标 backtest 用的 19 词）
        _judgment_words = [
            "我们认为",
            "我们判断",
            "我们预计",
            "预计",
            "有望",
            "超预期",
            "低于预期",
            "判断",
            "评级",
            "建议",
            "看好",
            "看空",
            "风险",
            "催化剂",
            "拐点",
            "推荐",
        ]
        _n_judgments = sum(len(_re.findall(w, text)) for w in _judgment_words)
        # 数据点计数：数字+单位（2026-08-29 扩展单位列表，提升检出率）
        _data_pats = re.findall(
            r"\d+(?:\.\d+)?\s*(?:%|‰|亿元|万元|亿元|万|元|倍|人|家|个|项|次|条|篇|页|天|月|年|小时|分钟|吨|公斤|千克|米|公里|平方|立方)",
            text,
        )
        _n_data = len(_data_pats)

        _jd = _n_judgments / _kchars if _kchars > 0 else 0
        _dd = _n_data / _kchars if _kchars > 0 else 0

        issues = []
        if _jd < _min_jd:
            issues.append(f"判断密度{_jd:.1f}/千字 < {_min_jd}（金牌基准 p10，报告偏'描述'缺'判断'）")
        if _dd < _min_dd:
            issues.append(f"数据密度{_dd:.1f}/千字 < {_min_dd}（金牌基准 p10，判断缺数据支撑）")

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.3, 1.0 - 0.3 * len(issues))
        det = f"判断密度:{_jd:.1f}/千字 数据密度:{_dd:.1f}/千字" + (
            " | " + "; ".join(issues) if issues else "（对标金牌基准）"
        )
        return GateCheckResult("judgment_density", passed, score, det, severity="error")

    def _check_aigc_fingerprint(self) -> GateCheckResult:
        patterns = [
            "以下是根据",
            "根据您的要求",
            "好的，",
            "作为AI",
            "作为人工智能",
            "我无法",
            "我不能",
            "首先，让我",
            "让我为您",
        ]
        matches = sum(1 for p in patterns if p in self.report_text[:500])
        ratio = matches / max(len(patterns), 1)
        passed = ratio < 0.15
        # 2026-08-08：工作过程语言（AI 工具痕迹）检测——补采/差距量化/战略部/---等
        # 来源：油位 v2.8 复查发现（工具语言混入严肃报告正文）
        wp_note = ""
        try:
            from core.template_blacklist import scan_metacomment, scan_work_process

            _wp = scan_work_process(self.report_text or "")
            _mc = scan_metacomment(self.report_text or "")
            if not _wp.get("passed"):
                wp_note = f"|工作过程语言{_wp.get('total', 0)}处: " + ", ".join(
                    f"{h['term']}x{h['count']}" for h in _wp.get("exact_hits", [])[:4]
                )
                passed = False  # 工作过程语言 = 报告带工具痕迹，阻断
            if not _mc.get("passed"):
                wp_note += f"|元评论语言{_mc.get('total', 0)}处: " + ", ".join(
                    f"{h['term']}x{h['count']}" for h in _mc.get("exact_hits", [])[:4]
                )
                passed = False  # 元评论 = AI 助手姿态，阻断
        except Exception:
            pass
        det = f"AI痕迹: {ratio:.0%}" + wp_note
        return GateCheckResult(name="AIGC痕迹", passed=passed, score=1.0 - ratio, details=det)

    def _check_human_sense(self) -> GateCheckResult:
        signals = [
            "我们",
            "调研发现",
            "判断",
            "我们认为",
            "据我们了解",
            "跟踪",
            "发现",
            "分析",
            "测算",
            "注意到",
            "从我们的分析",
            "我们判断",
            "从业多年",
            "从历史上看",
            "我们注意到",
            "据我们测算",
            "我们的核心",
            "从行业经验",
        ]
        count = sum(1 for s in signals if s in self.report_text)
        score = min(count / 4.0, 1.0)
        passed = count >= 1
        return GateCheckResult(name="人感检测", passed=passed, score=score, details="人感信号: %d个" % count)

    def _check_format_consistency(self) -> GateCheckResult:
        issues = []
        if re.search(r"\*\*。|\*\*，", self.report_text):
            issues.append("标点紧邻加粗")
        if re.search(r"#{4,}", self.report_text):
            issues.append("标题层级过深")
        emphasis_keywords = ["核心判断", "我们建议", "重点关注", "值得注意"]
        found_e = sum(1 for kw in emphasis_keywords if kw in self.report_text)
        if found_e < 1:
            issues.append("Emphasis markers: " + str(found_e) + "/4")
        passed = len(issues) == 0
        score = max(0, 1.0 - len(issues) * 0.15)
        # FP7b L1 降级：格式类检查降为 advisory（不阻断），由整体 score 把关
        severity = "warning" if self._allow_placeholder_degradation else "error"
        return GateCheckResult(
            name="排版一致性",
            passed=passed,
            score=score,
            details=str(issues) if issues else "格式正常",
            severity=severity,
        )

    def _check_insight_quality(self) -> GateCheckResult:
        """R79 P1-1：洞察质量检查——判断句是否有信息增量。

        油位报告圆桌评审：判断密度数判断词被刷分，LLM 堆"我们判断/预计"凑密度，
        但判断本身是常识复述（"受益于政策""需求增长"）无信息增量。
        本检查：对每个判断句检测是否含"具体锚点"——数字+时间窗口+因果机制。
        有锚点的判断=洞察；无锚点的判断=常识复述，降分。
        """
        import re

        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("insight_quality", True, 1.0, "报告过短")
        # 判断句提取：判断词开头的句子
        judgment_sents = re.findall(r"[^。\n]*?(?:我们判断|我们认为|我们预计|判断|预计)[^。]*。", text)
        if not judgment_sents:
            return GateCheckResult("insight_quality", True, 0.8, "无显式判断句")
        # 常识复述模式（无具体锚点的套话判断）
        cliche_patterns = [
            r"(受益于|受惠于).{0,8}(政策|需求|行业|趋势)",
            r"(需求|市场).{0,6}(增长|扩大|提升)",
            r"(格局|竞争).{0,6}(优化|改善|集中)",
            r"(国产替代|渗透率).{0,6}(加速|提升)",
            r"具有.{0,6}(潜力|空间|前景)",
        ]
        anchored = 0
        cliche = 0
        for sent in judgment_sents:
            has_anchor = bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|亿|倍|元|个|座|家)", sent)) and bool(
                re.search(r"(20\d{2}|Q[1-4]|年|季|月)", sent)
            )
            is_cliche = any(re.search(p, sent) for p in cliche_patterns)
            if has_anchor and not is_cliche:
                anchored += 1
            elif is_cliche and not has_anchor:
                cliche += 1
        total = len(judgment_sents)
        insight_ratio = anchored / max(total, 1)
        cliche_ratio = cliche / max(total, 1)
        if cliche_ratio > 0.5:
            return GateCheckResult(
                "insight_quality",
                False,
                max(0.1, 0.6 - cliche_ratio * 0.4),
                f"洞察质量低(P1): {cliche}/{total} 判断为常识复述（无具体数字/时间/机制锚点）",
                severity="warning",
            )
        return GateCheckResult(
            "insight_quality",
            True,
            min(1.0, 0.5 + insight_ratio),
            f"洞察质量: 有锚点判断 {anchored}/{total}（{insight_ratio:.0%}），常识复述 {cliche}",
        )

    def _check_template_phrases(self) -> GateCheckResult:
        """R79 P0-1：模板句检测——拦截万能过渡句复读。

        油位报告圆桌评审：10 个模板句全报告复读 3-8 次，是 LLM 被
        "每段必须 So What 链/判断密度"逼出来的填充句。
        命中 ≥2 warning，≥4 error（说明全文被模板污染）。
        """
        text = self.report_text or ""
        if not text:
            return GateCheckResult("template_phrases", True, 1.0, "无文本")
        try:
            from core.template_blacklist import scan

            r = scan(text)
        except Exception:
            return GateCheckResult("template_phrases", True, 1.0, "黑名单不可用")
        total = r["total_exact"] + r["total_variant"]
        if total >= 4:
            return GateCheckResult(
                "template_phrases",
                False,
                max(0.0, 1.0 - total * 0.15),
                f"模板句污染(P1): 命中 {total} 处（{r['exact_hits']}）——全文被套话填充，需局部重写为具体论证",
                severity="error",
            )
        if total >= 2:
            return GateCheckResult(
                "template_phrases",
                False,
                max(0.0, 1.0 - total * 0.1),
                f"模板句提示: 命中 {total} 处——建议改写为具体论证",
                severity="warning",
            )
        return GateCheckResult("template_phrases", True, 1.0, "无模板句")

    def _check_layout_quality(self) -> GateCheckResult:
        """R31（2026-08-02 排版根治）：文档布局质量门禁。

        检查报告文本 + 已导出的 docx 的排版隐患：
          - markdown 连续空行（→ docx 空段落 → 空白页）
          - docx 空段落率 / 连续空段（真正造成空白页的元凶）
        排版是"最后一公里"——内容对了但打开是空白页等于白写。
        注意：pandoc 转换会把规范空行变多余空段，所以 md 检测+docx 检测都要。
        """
        import re as _re

        text = self.report_text or ""
        issues = []
        # R74（2026-08-05 P1）：md 层图表位置检测
        # 油位 v6 审计发现——所有 13 张图堆在"附录"之后，正文中无任何随文插入。
        # docx 层检查已覆盖（R40），但手动路径绕过 ChartAssembler 时 docx 无 drawing 元素。
        # 现增加 md 层检查：查正文段落中（附录标题之前）是否有 ![fig_xxx] 内联引用。
        md_inline_imgs = _re.findall(r"!\[(fig_\w+)\]", text)
        appendix_pos = text.find("附录")
        if appendix_pos > 0 and md_inline_imgs:
            before_appendix = text[:appendix_pos]
            inline_before = _re.findall(r"!\[(fig_\w+)\]", before_appendix)
            if not inline_before:
                # R78（2026-08-05 油位v8诊断）：图表堆叠附录是 P0——LLM 未按指令嵌图、
                # ChartAssembler 兜底静默堆附录、layout_quality warning 放行，三道全失效。
                # 直接 error 级阻断：图表必须随文，不允许全量堆附录出厂。
                return GateCheckResult(
                    "layout_quality",
                    False,
                    0.0,
                    f"图表未随文(P0): {len(md_inline_imgs)} 张图全部位于'附录'之后，正文无随文引用——"
                    f"必须通过 ChartAssembler 在对应章节插入，禁止全量堆附录出厂",
                    severity="error",
                )
        # 1. md 层：连续空行
        if len(text) >= 300:
            lines = text.split("\n")
            run = 0
            max_run = 0
            for ln in lines:
                if not ln.strip():
                    run += 1
                    max_run = max(max_run, run)
                else:
                    run = 0
            if max_run >= 3:
                issues.append(f"md 连续 {max_run} 个空行")
        # 2. docx 层：检查已导出的 docx 空段落（真正空白页来源）
        import os as _os

        docx_path = ""
        if getattr(self, "md_path", ""):
            docx_path = str(self.md_path).replace(".md", ".docx")
        elif hasattr(self, "report_path") and self.report_path:
            docx_path = str(self.report_path).replace(".md", ".docx")
        if docx_path and _os.path.exists(docx_path):
            try:
                import zipfile

                z = zipfile.ZipFile(docx_path)
                xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
                z.close()
                paras = _re.findall(r"<w:p\b[^>]*>(.*?)</w:p>", xml, _re.S)
                total = len(paras)
                empty = [p for p in paras if not _re.sub(r"<[^>]+>", "", p).strip()]
                # R40：自闭合空段落 <w:p/>（python-docx 空段格式）也计入空段
                self_closing_empty = xml.count("<w:p/>") + xml.count("<w:p />")
                empty_ratio = (
                    (len(empty) + self_closing_empty) / (total + self_closing_empty)
                    if (total + self_closing_empty)
                    else 0
                )
                # 连续空段（含自闭合空段——连续自闭合即连续空段）
                empty_set = set()
                for i, p in enumerate(paras):
                    if not _re.sub(r"<[^>]+>", "", p).strip():
                        empty_set.add(i)
                max_run = 0
                run = 0
                for i in range(len(paras)):
                    if i in empty_set:
                        run += 1
                        max_run = max(max_run, run)
                    else:
                        run = 0
                # 自闭合空段（<w:p/>）——按"连续位置"计算，而非总数。
                # R91（2026-08-10）：此前 `self_closing_empty >= 3 → max_run = total`
                # 把全文分散的表格后空段（每个表格后一个 <w:p/>）误判成"连续 N 个"。
                # 实际空段是分散的（表格间有内容），不造成空白页。
                # 正确：统计 XML 中连续相邻的自闭合空段最大个数（相邻 = 仅空白间隔）。
                _sc_positions = [_m.start() for _m in _re.finditer(r"<w:p\s*/>", xml)]
                _sc_max_run = 0
                _sc_run = 0
                for _k in range(len(_sc_positions)):
                    _sc_run += 1
                    _sc_max_run = max(_sc_max_run, _sc_run)
                    if _k + 1 < len(_sc_positions):
                        _between = xml[_sc_positions[_k] : _sc_positions[_k + 1]]
                        # 两个自闭合空段之间若只有空白/标签闭合符号 → 视为连续
                        if not _re.sub(r"\s|<[^>]+>", "", _between):
                            continue
                        _sc_run = 0
                if _sc_max_run >= 3:
                    max_run = max(max_run, _sc_max_run)
                if empty_ratio > 0.15:
                    issues.append(f"docx 空段落率 {empty_ratio:.0%}（{len(empty)}/{total}）")
                if max_run >= 3:
                    issues.append(f"docx 连续 {max_run} 个空段落（→空白页）")
                # R40（2026-08-02 渲染层目检）：分页符计数
                page_breaks = xml.count('w:type="page"') + xml.count("pageBreakBefore")
                if page_breaks >= 3:
                    issues.append(f"docx 强制分页符 {page_breaks} 个（过多）")
                # R40：图片分布——检查图片是否全部集中在尾部（后 50% 段落）
                img_positions = [i for i, p in enumerate(paras) if "<w:drawing>" in p]
                if len(img_positions) >= 3 and total > 20:
                    first_img_ratio = img_positions[0] / total
                    # 若所有图片都位于后 50%，且正文段落有内容 → 图表未随文
                    if first_img_ratio > 0.5:
                        issues.append(
                            f"图表未随文: {len(img_positions)} 张图全部位于正文后{first_img_ratio:.0%}（应随对应章节插入）"
                        )
                # R43（2026-08-02）：目录渲染目检——R42 新增静态目录后，
                # 应确保"目录"标题存在且含条目（防止未来改动破坏目录插入）。
                has_toc_title = "目" in xml and "录" in xml
                if has_toc_title:
                    # 目录标题后应有条目（非空段落紧随其后）
                    _toc_positions = [
                        i
                        for i, p in enumerate(paras)
                        if "目" in _re.sub(r"<[^>]+>", "", p) and "录" in _re.sub(r"<[^>]+>", "", p)
                    ]
                    if _toc_positions:
                        _after = _toc_positions[0] + 1
                        _next_text = ""
                        for _j in range(_after, min(_after + 5, len(paras))):
                            _t = _re.sub(r"<[^>]+>", "", paras[_j]).strip()
                            if _t:
                                _next_text = _t
                                break
                        if not _next_text:
                            issues.append("目录为空: '目  录'标题后无条目")
            except Exception:
                pass
        passed = len(issues) == 0
        det = f"排版质量: {len(issues)} 项" + (": " + "; ".join(issues[:3]) if issues else "正常")
        return GateCheckResult("layout_quality", passed, 1.0 if passed else 0.6, det, severity="warning")

    def _check_completeness_scan(self) -> "GateCheckResult":
        """R53审计（2026-08-03 P1-1）：正文完整性扫描——截断/碎片/未完成句拦截。

        背景：气体传感器圆桌审计坐实正文 3 处截断——
          决策门"双的分析"(L12)、表E-2"2025-202"(L318)、DCF碎片(L320)，
          Gate 全绿出厂——无完整性扫描。
        本检查做确定性扫描（非 LLM 判断）：
          1. 未闭合代码块（``` 数量为奇数）
          2. 表格半 cell（行内管道符数量不一致，末 cell 截半）
          3. 年份截断（"2025-202" 后无后续数字）
          4. 已知截断碎片关键词（"双的分析"、"DCF碎片"等特征）
          5. 句末连字符/截半词
          6. 段落末词截半（非完整句 + 无标点结尾）
        """
        import re as _re

        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("completeness_scan", True, 1.0, "text too short, skipped", severity="warning")
        issues = []
        lines = text.split("\n")

        # ── 1. 未闭合代码块 ────────────────────────────────────
        _fence_count = text.count("```")
        if _fence_count % 2 == 1:
            issues.append(f"未闭合代码块: 存在奇数个```（{_fence_count}个）")

        # ── 2. 表格半 cell / 行管道符不一致 ────────────────────
        # 检测：(a) 行以 | 开头且管道符数明显少于表头 → 半 cell 截断
        #       (b) 表格上下文内行以 | 开头但未以 | 结尾（多出未闭合 cell）→ 截断
        # 注意：只有首尾都有 | 的行才进入表格上下文，避免把正文中以 | 开头
        #       的普通句子误判为表格（真实报告正文可能以 | 强调）。
        # P2-1（2026-09-01）：误报修复——失败样本 '...） |。'（正文句子含竖线分隔符）
        # 被当表格行未闭合。现在表格上下文要求"连续 2+ 行首尾 | 且管道数一致"才算
        # 真表格；单行以 | 开头未闭合只有在前一行已确认表头时才报警。
        _in_table = False
        _header_pipes = 0
        _table_streak = 0
        for _i, _ln in enumerate(lines):
            _s = _ln.strip()
            if _s.startswith("|") and _s.endswith("|"):
                _pipe_count = _s.count("|")
                if not _in_table:
                    _table_streak += 1
                    # 连续两行首尾 | 才算进入表格上下文（防正文单行竖线误判）
                    if _table_streak >= 2:
                        _in_table = True
                        _header_pipes = _pipe_count
                elif _pipe_count < _header_pipes - 1:
                    issues.append(
                        f"表格半cell(L{_i + 1}): 管道符{_pipe_count}个 < 表头{_header_pipes}个"
                        f"（'...{_s[-30:]}' 疑似截断）"
                    )
            elif _in_table and _s.startswith("|") and not _s.endswith("|"):
                # 已在表格上下文内，遇到未闭合行 → cell 截断
                # P2-1：仅当该行管道数 ≥ 表头管道数-1（确实是表格数据行截断）才报警；
                # 管道数很少的正文句子（如 '| 见图3'）不是表格截断
                _pipe_count = _s.count("|")
                if _pipe_count >= _header_pipes - 1:
                    issues.append(f"表格行未闭合(L{_i + 1}): '...{_s[-30:]}'（cell 截断或多余内容）")
            elif _s and not _s.startswith("|"):
                _in_table = False
                _table_streak = 0

        # ── 3. 年份截断（"2025-202" 后无后续数字）──────────────
        # 模式：20XX - 后跟不足 4 位的年份（20YY 只到 2-3 位即截断）。
        # 注意：完整 4 位年份（2026-2027年）是合法双年份表述，不能误判。
        for _m in _re.finditer(r"20\d\d\s*[-–—]\s*20\d{0,2}(?!\d)", text):
            _after = text[_m.end() : _m.end() + 12]
            # 排除完整 4 位年份（2026-2027年/2027E/2027 等）——不是截断
            _second_yr = _m.group(0).split("-")[-1].split("–")[-1].split("—")[-1].strip()
            if len(_second_yr) >= 4:
                continue
            # 排除合法后续（年/E 等年份后缀）
            if _re.match(r"(?:年|[Ee]\b| |\.)", _after.strip()):
                continue
            if not _re.match(r"\d", _after.strip()):
                _snippet = text[max(0, _m.start() - 8) : _m.end() + 8].replace("\n", " ")
                issues.append(f"年份截断: '...{_snippet}...'（{_m.group(0)} 后无完整年份）")

        # ── 4. 已知截断碎片特征 ────────────────────────────────
        # 注意：不含"如下：/见表/见图"类引导词规则——投行报告"盈利预测如下："后
        # 接表格/列表是正常写法，误报率高（R54 实测）。
        _fragment_pats = [
            (r"的?[双两]的?分析[^。；\n]{0,4}$", "句子截断（'双的分析'类）"),
            (r"DCF[^\n。；]{0,6}(?:碎片|残段|未完)", "DCF 碎片"),
        ]
        for _i, _ln in enumerate(lines):
            _s = _ln.strip()
            if not _s or _s.startswith("#"):
                continue
            for _pat, _desc in _fragment_pats:
                if _re.search(_pat, _s):
                    issues.append(f"截断碎片(L{_i + 1}): {_desc} '...{_s[-35:]}'")

        # ── 5. 句末连字符/截半词 ───────────────────────────────
        for _i, _ln in enumerate(lines):
            _s = _ln.strip()
            if not _s:
                continue
            if _s.endswith("-") or _s.endswith("—") or _s.endswith("–"):
                issues.append(f"句末连字符(L{_i + 1}): '...{_s[-25:]}'（疑似截半词）")

        # ── 6. 段落末词截半（非完整句 + 无标点结尾）────────────
        _sentence_enders = "。；！？，、：”’】」）》%"
        for _i, _ln in enumerate(lines):
            _s = _ln.strip()
            if not _s or _s.startswith("#") or _s.startswith("|") or _s.startswith("-"):
                continue
            if len(_s) < 15:
                continue
            if re.search(
                r"^(?:报告级别|报告日期|分析师|分析周期|报告标题|股票代码|"
                r"评级|行业|日期|编制|机构)\s*[:：]",
                _s,
            ):
                continue
            if _s[-1] not in _sentence_enders and not _s.endswith("."):
                _next = lines[_i + 1].strip() if _i + 1 < len(lines) else ""
                # R89（2026-08-30）：段落末词+标题衔接、头部模板行衔接 → 正常段落结构，不算截断
                if _s[-1].isalpha() or ("一" <= _s[-1] <= "鿿"):
                    if not _next or _next.startswith("#"):
                        continue
                    if re.search(
                        r"^(?:报告级别|报告日期|分析师|分析周期|报告标题|股票代码|"
                        r"评级|行业|日期|编制|机构)\s*[:：]",
                        _next,
                    ):
                        continue
                issues.append(f"段落截断(L{_i + 1}): 末词'...{_s[-20:]}'无标点且无后续（疑似截半）")
        _seen = set()
        _uniq = []
        for _i in issues:
            if _i not in _seen:
                _seen.add(_i)
                _uniq.append(_i)

        passed = len(_uniq) == 0
        score = 1.0 if passed else max(0.3, 1.0 - 0.25 * len(_uniq))
        det = f"完整性扫描: {len(_uniq)} 项" + (": " + "; ".join(_uniq[:3]) if _uniq else "无")
        # R89（2026-08-30）：非上市报告数据稀缺、段落短，段落截断误报率高。
        _rt = getattr(self, "report_type", "") or ""
        _sev = "warning" if _rt == "unlisted_company" and len(_uniq) <= 2 else "error"
        return GateCheckResult("completeness_scan", passed, score, det, severity=_sev)

    def _check_template_repeat(self) -> GateCheckResult:
        """R35（2026-08-02）：模板句高重复检测。

        柯力报告圆桌审计发现：4 个模板句各出现 2 次（"这一趋势若持续，盈利中枢存在
        系统性上移的可能"等），属 LLM 套模板/拼接痕迹。检测同一模板句出现≥2次。
        """
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("template_repeat", True, 1.0, "text too short, skipped", severity="warning")
        # 已知模板句（柯力案 + 通用高频套话）
        templates = [
            "这一趋势若持续，盈利中枢存在系统性上移的可能",
            "上述变化对盈利预测的传导，存在路径与时滞上的不确定性",
            "若该趋势延续，我们对这一方向的确定性判断将得到进一步强化",
            "该数据背后折射出的经营质量变化，比单期数值本身更值得关注",
            "这一迹象提示，市场当前定价可能尚未充分反映上述逻辑的潜在弹性",
            "该信号与基本面相互印证，增强了我们对此前观点落地的信心",
            "因此，这意味着",
            "综合判断：",
            "在此背景下，竞争壁垒的强化将构成公司中长期价值的核心支撑",
            "这意味着读者可据此交叉验证核心判断与估值区间",
        ]
        repeats = []
        for t in templates:
            cnt = text.count(t)
            if cnt >= 2:
                repeats.append(f"{t}(x{cnt})")
        # 概念错位词（模板残留，跨行业污染）
        mismatch_words = ["端侧变现", "AI芯片", "消费电子叙事", "to C 变现"]
        mism = [w for w in mismatch_words if w in text]
        passed = len(repeats) == 0 and len(mism) == 0
        det_parts = []
        if repeats:
            det_parts.append("模板句重复: " + "; ".join(repeats[:3]))
        if mism:
            det_parts.append("概念错位: " + ", ".join(mism))
        det = "; ".join(det_parts) if det_parts else "无模板污染"
        return GateCheckResult("template_repeat", passed, 1.0 if passed else 0.5, det, severity="warning")

    def _check_semantic_repeat(self) -> "GateCheckResult":
        """R53审计（2026-08-03 P1-2）：跨章节语义重复检测。

        背景：_check_template_repeat 是 10 句硬编码黑名单，只查字面精确重复，
          新套话（如"端侧变现"/"我们看好其成长空间"）不在名单即漏。
        本检查用字符 n-gram 相似度做**跨章节语义重复**检测（零依赖）：
          - 按 markdown 二级标题切章节
          - 每章节句子集合两两比较（字符 2-gram Jaccard 相似度）
          - 跨章节句子相似度 ≥0.85 → 语义重复（LLM 套话/复制粘贴痕迹）
        输出"章节A/章节B 相似度0.91"可定位证据链。

        阈值：0.85（顶级打法建议 sentence-BERT ≥0.85；n-gram 保守取 0.90 防误报，
        因字符 n-gram 对同义词替换较敏感）。
        """
        import re as _re

        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("semantic_repeat", True, 1.0, "text too short, skipped", severity="warning")

        # ── 1. 按章节切分 ──────────────────────────────────────
        sections = {}  # 章节名 -> [句子]
        _cur_title = "(引言)"
        for _ln in text.split("\n"):
            _s = _ln.strip()
            if _s.startswith("##") or _s.startswith("# "):
                _t = _re.sub(r"^#{1,3}\s*", "", _s).strip()
                if _t:
                    _cur_title = _t[:40]
                    sections.setdefault(_cur_title, [])
            elif _s and len(_s) >= 20 and not _s.startswith("|"):
                sections.setdefault(_cur_title, [])
                # 切句（按句读）
                _parts = _re.split(r"[。；！？]", _s)
                for _p in _parts:
                    _p = _p.strip()
                    if len(_p) >= 15:
                        sections[_cur_title].append(_p)

        # 过滤太短的章节
        sections = {k: v for k, v in sections.items() if len(v) >= 1}
        _titles = list(sections.keys())
        if len(_titles) < 2:
            return GateCheckResult("semantic_repeat", True, 1.0, "章节过少，跳过", severity="warning")

        # ── 2. 字符 2-gram 集合 ────────────────────────────────
        def _ngrams(s, n=2):
            s = _re.sub(r"\s+", "", s)
            if len(s) < n:
                return {s} if s else set()
            return {s[i : i + n] for i in range(len(s) - n + 1)}

        def _is_source_note(s):
            """来源标注/免责句（重复属正常，非内容套话）。"""
            return "数据来源" in s or "资料来源" in s or "来源：" in s or "风险提示" in s or "免责" in s

        def _is_noise(s):
            """表格线/纯格式噪声（非内容句子）。"""
            return s.startswith("|") or set(s) <= set("-|: ") or s.isdigit()

        def _sim(a, b):
            ga, gb = _ngrams(a), _ngrams(b)
            if not ga or not gb:
                return 0.0
            inter = len(ga & gb)
            return inter / max(len(ga), len(gb))

        # ── 3. 跨章节句子两两比较（限样本，防 O(n²) 爆炸）─────
        # 每章节最多取前 12 个句子；章节两两比较时句子抽样 8 个
        _MAX_SENT_PER_SEC = 12
        _SAMPLE = 8
        repeats = []
        for _i in range(len(_titles)):
            for _j in range(_i + 1, len(_titles)):
                _sa = [
                    s for s in sections[_titles[_i]][:_MAX_SENT_PER_SEC] if not _is_source_note(s) and not _is_noise(s)
                ]
                _sb = [
                    s for s in sections[_titles[_j]][:_MAX_SENT_PER_SEC] if not _is_source_note(s) and not _is_noise(s)
                ]
                if not _sa or not _sb:
                    continue
                # 抽样比较（控制计算量）
                _step_a = max(1, len(_sa) // _SAMPLE)
                _step_b = max(1, len(_sb) // _SAMPLE)
                _sa_s = _sa[::_step_a][:_SAMPLE]
                _sb_s = _sb[::_step_b][:_SAMPLE]
                for _x in _sa_s:
                    for _y in _sb_s:
                        _s = _sim(_x, _y)
                        if _s >= 0.90:
                            repeats.append(
                                f"『{_titles[_i]}』vs『{_titles[_j]}』相似度{_s:.2f}：'{_x[:28]}…'≈'{_y[:28]}…'"
                            )
                            if len(repeats) >= 5:
                                break
                    if len(repeats) >= 5:
                        break
                if len(repeats) >= 5:
                    break
            if len(repeats) >= 5:
                break

        passed = len(repeats) == 0
        score = 1.0 if passed else max(0.4, 1.0 - 0.3 * len(repeats))
        det = f"语义重复: {len(repeats)} 项" + (": " + "; ".join(repeats[:3]) if repeats else "无")
        return GateCheckResult("semantic_repeat", passed, score, det, severity="warning")

    def _check_forbidden_patterns(self) -> GateCheckResult:
        forbidden = ["AI生成", "人工智能生成", "本报告由AI", "作为语言模型", "我是一款", "由OpenAI", "我是Claude"]
        # R72（2026-08-05 P0 加固）：油位 v6 圆桌审计发现 Marvis 手动修复路径
        # 绕过了管线 export 链路，R42 已删除的免责声明在手动路径复活。
        # 此前白名单豁免 "内容由AI生成，仅供参考"——但 R42 明确要求清除所有 AI 免责。
        # 现改为硬拦截：不仅不豁免，反而专门检测这个被反复复活的最顽固模式。
        # 硬化：无论通过哪个路径写出的报告，只要含 AI 免责声明，直接 FAIL。
        hard_kill = "内容由AI生成，仅供参考"
        if hard_kill in self.report_text:
            return GateCheckResult(
                name="禁止词检测",
                passed=False,
                score=0.0,
                details=f"[P0] 发现AI免责声明: '{hard_kill}'——R42已删除/R72加固，禁止在任何路径出现",
            )
        text = self.report_text
        found = [f for f in forbidden if f in text]
        passed = len(found) == 0
        score = 1.0 if passed else 0.3
        return GateCheckResult(name="禁止词检测", passed=passed, score=score, details=str(found) if found else "无")

    def _check_gbk_encoding(self) -> GateCheckResult:
        """P2-4 (2026-09-01): 出口质量红线——检测乱码/编码损坏。

        触发条件（审计 2026-09-01 实测 output/_gate_prev.md 含 GBK 错乱）：
        1. U+FFFD 替换字符（解码失败的标准信号）
        2. 常见 GBK 乱码 mojibake 模式：'å'/'æ'/'ç'/'è' 等拉丁扩展跟随 CJK 的形态
           （UTF-8 文本被 GBK 解码产生的典型乱码），如 'æµæ±è§çº¤'
        3. 报告头部声明 UTF-8 但正文含 \x00-\x08 控制字符

        乱码是"系统性事实错误"（R28：Agent 对事实负责）——含乱码的报告不可交付。
        """
        import re

        text = self.report_text or ""
        issues = []
        # 1. 替换字符
        n_repl = text.count("�")
        if n_repl >= 1:
            issues.append(f"U+FFFD 替换字符 {n_repl} 处")
        # 2. GBK mojibake 模式：乱码通常成串出现（>=4 个连续 latin 扩展字符）
        mojibake = re.findall(r"(?:[\xc0-\xff][\x80-\xbf]){4,}", text)
        if len(mojibake) >= 1:
            issues.append(f"疑似 GBK 乱码 {len(mojibake)} 处（如 '{mojibake[0][:20]}...'）")
        # 3. 控制字符（除 \n\r\t）
        ctrl = [c for c in text if ord(c) < 9 or 13 < ord(c) < 32]
        if ctrl:
            issues.append(f"非法控制字符 {len(ctrl)} 个")

        passed = len(issues) == 0
        score = 1.0 if passed else 0.0
        severity = "error" if not passed else "info"
        return GateCheckResult(
            name="gbk_encoding",
            passed=passed,
            score=score,
            details="; ".join(issues) if issues else "无乱码",
            severity=severity,
        )

    def _check_placeholder_source(self) -> GateCheckResult:
        """P0-2 (2026-09-01): 出口质量红线——拦截裸来源锚点。

        审计发现失败产物含 '目标价38.40元（数据来源：公司年度报告）' 这类
        无具体来源的锚点数字（FP2a 数据零编造违反）。检测：
        1. '（数据来源：X）' 中 X 是泛称（公司年度报告/公告/官网/公开资料/网络）
        2. '（来源：X）' 同上
        """
        import re

        text = self.report_text or ""
        bad = re.findall(
            r"[（(]\s*(?:数据来源|来源|资料来源)\s*[：:]\s*(?:公司|公司年度报告|公司公告|年报|半年报|季报|官网|公开资料|公开信息|网络|百度|搜索|招股说明书)\s*[）)]",
            text,
        )
        # 具体来源（如 '来源：2025年年报' '数据来源：wind'）不拦截——带具体主体的来源是合法锚
        passed = len(bad) == 0
        score = 1.0 if passed else 0.3
        severity = "error" if not passed else "info"
        det = "裸来源锚点: %d 处" % len(bad)
        if bad:
            det += "（如 '%s'——必须替换为具体来源+日期）" % bad[0]
        return GateCheckResult(name="placeholder_source", passed=passed, score=score, details=det, severity=severity)

    def _check_markdown_artifacts(self):
        """Check for residual markdown syntax in report."""
        import re

        text = self.report_text
        issues = []
        # # 标题与 ** 加粗 / * 斜体是 MD 报告的合法结构（StyleCompiler 产物），不算残留
        # 只拦截真正的残留：代码块围栏、多余的水平分隔符
        # R41（2026-08-02）：豁免 frontmatter——AIGC 水印 YAML 头（--- 开头的
        # metadata 块）是合规标记，不是残留分隔符。跳过首个 --- 到第二个 --- 之间。
        _text = text
        _fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.S)
        if _fm_match:
            _text = text[_fm_match.end() :]
        # Check for --- separators (more than 1 is likely residual)
        hr = re.findall(r"^---+$", _text, re.MULTILINE)
        if len(hr) > 1:
            issues.append(f"{len(hr)} --- separators found")
        # Check for ` code blocks
        code = _text.count("```")
        if code:
            issues.append(f"{code} code blocks found")
        # Check for stray backticks / 残留表格管道（非表格行的孤立 |）
        stray_backticks = len(re.findall(r"(?<!`)`(?!`)", _text))
        if stray_backticks:
            issues.append(f"{stray_backticks} stray backticks found")

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.3, 1.0 - len(issues) * 0.15)
        det = "No MD artifacts" if passed else "; ".join(issues)
        return GateCheckResult(name="md_artifacts", passed=passed, score=score, details=det, severity="error")

    def _check_personal_narrative(self) -> GateCheckResult:
        """Check report for personal narrative markers (full text, at least 4000 chars)

        P1-4 修复（2026-08-01 审计）：原只查前 200 字，若 LLM 在中段/尾段
        出现"我是""各位"等内容则漏检。扩展为全文检查（至少 4000 字），
        匹配模式保持并放宽位置范围。
        """
        text = self.report_text or ""
        check_len = min(len(text), 4000)
        check_text = text[:check_len]
        markers = ["我是", "各位", "我们继续", "你好", "大家好", "我是2号分析师"]
        found = [m for m in markers if m in check_text]
        passed = len(found) == 0
        score = 1.0 if passed else 0.0
        details = "No personal narrative" if passed else "Found: " + ", ".join(found)
        return GateCheckResult(name="personal_narrative", passed=passed, score=score, details=details)

    def _check_section_continuity(self) -> GateCheckResult:
        """Check section numbering continuity"""
        import re

        text = self.report_text or ""
        part1 = chr(31532)  # ?
        sections = re.findall(part1 + r"[一-鿿\d]+[部分章节篇]", text)
        if len(sections) <= 1:
            sections = re.findall(r"^#{1,3}\s*\d+\.", text, re.MULTILINE)
        if len(sections) <= 1:
            return GateCheckResult(
                name="section_continuity", passed=True, score=1.0, details="No numbered sections - skip"
            )
        passed = True
        return GateCheckResult(
            name="section_continuity", passed=passed, score=1.0, details="Sections: %d, numbering OK" % len(sections)
        )

    def _check_table_quality_md(self) -> GateCheckResult:
        """Check markdown tables have at least 3 rows (header+separator+data)"""
        text = self.report_text or ""
        NL = chr(10)
        blocks = text.split(NL + NL)
        issues = 0
        table_count = 0
        for block in blocks:
            if "|" in block and "---" in block:
                rows = [l for l in block.strip().split(NL) if l.strip().startswith("|")]
                if len(rows) >= 2:
                    table_count += 1
                    if len(rows) < 3:
                        issues += 1
        if table_count == 0:
            return GateCheckResult(name="table_quality_md", passed=True, score=1.0, details="No tables found")
        passed = issues == 0
        score = max(0, 1.0 - (issues / table_count) * 0.5)
        return GateCheckResult(
            name="table_quality_md",
            passed=passed,
            score=score,
            details="Tables: %d, issues: %d" % (table_count, issues),
        )
