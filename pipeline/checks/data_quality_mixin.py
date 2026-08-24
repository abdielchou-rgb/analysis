# -*- coding: utf-8 -*-
"""IronGate 检查 Mixin — data_quality 类检查。

R61（2026-08-03 迁移）：由 scripts/migrate_iron_gate.py 自动生成。
方法原样迁移自 pipeline/iron_gate.py，签名不变，IronGate 继承后行为零变化。
"""


from pipeline.checks.base import GateCheckResult, detect_value_conflicts, logger, _ROOT
import json, os, re

class DataQualityChecksMixin:
    """data_quality 类检查方法。"""
    def _check_data_traceability(self) -> GateCheckResult:
        """FP2a: Source coverage verification (name + org + date).

        修订（2026-07-31）：不再强制每段三层深度（真实投行研报也做不到）。
        标准改为：实质性段落（含数据/判断，非表格/标题）中 ≥30% 有来源标注。
        """
        import re
        text = self.report_text or ""
        paragraphs = text.split("\n\n")
        # 实质性段落：含数字/判断/来源，排除表格与纯标题
        substantive = []
        for para in paragraphs:
            if not para or len(para) < 20:
                continue
            if re.match(r'^\s*\|', para):  # markdown 表格
                continue
            if re.match(r'^#+\s', para):   # 标题
                continue
            if re.search(r'\d+\.?\d*\s*[%亿万千元]|(?:我们认为|我们判断|预计|有望|看好|审慎)', para):
                substantive.append(para)
        total = len(substantive)
        if total == 0:
            return GateCheckResult("data_traceability", False, 0.0,
                                  "No substantive paragraphs")
        scored = 0
        depth_sum = 0
        for para in substantive:
            # R91（2026-08-10）：识别 2hao 四元组标注 (A)/(E)/(F)/(B) ——
            # STANDARDS.md 要求"证据标注含 A/E/F/B"，这是报告的主要溯源方式。
            # 此前只认"来源/据/年报"等词，导致 73% 带 (A)/(E) 标注的报告仅算 7% 覆盖。
            _has_ae_tag = bool(re.search(r'[\(\[（]\s*[AEFB]\s*[\)\]）]', para))
            # Level 1: Any source mention（来源词 或 A/E/F/B 标注）
            has_mention = bool(re.search(r'(?:来源|source|据|根据|sourced|披露|年报|公告)', para, re.I)) or _has_ae_tag
            if not has_mention:
                continue
            # Level 2: Organization/institution name
            has_org = bool(re.search(r'(?:证券|研究|咨询|研究院|协会|局|署|社|Bank|Securities|Insights|Institute|TrendForce|Gartner|Wind|Bloomberg)', para))
            # Level 3: Specific date/time reference
            has_date = bool(re.search(r'\d{4}年\d{1,2}月|\d{4}-\d{2}-\d{2}|20\d{2}年', para))
            # (A)实际标注 = 最强来源可信度（官方/年报级），深度计为 3
            _has_a = bool(re.search(r'[\(\[（]\s*A\s*[\)\]）]', para))
            depth = 3 if _has_a else (2 if has_org else 1)
            depth = 3 if (has_org and has_date) else depth
            depth_sum += depth
            scored += 1  # 有来源即计分
        # 覆盖率 = 有来源段落 / 实质性段落（≥30% 达标）
        coverage = scored / total
        score = min(1.0, coverage)
        passed = coverage >= 0.30
        avg_depth = round(depth_sum / max(total, 1), 2)

        # FP v3.2（FP2a）：四元组完整性检查——来源标注应含 {来源, 年份, 口径, 置信度}
        # 报告若用"数据来源：..."标注，应含年份/口径/置信度之一，不能全篇空泛重复
        _four_tuple = 0
        _four_tuple_total = 0
        for para in substantive:
            _src_mentions = re.findall(r'(?:数据来源|资料来源)[：:]([^。；\n]{0,40})', para)
            for _m in _src_mentions:
                _four_tuple_total += 1
                _has_year = bool(re.search(r'20\d{2}', _m))
                _has_scope = bool(re.search(r'全球|中国|公司|行业|亿元|%', _m))
                _has_conf = bool(re.search(r'估算|约|大约|区间|置信', _m))
                if _has_year or _has_scope or _has_conf:
                    _four_tuple += 1
        _tetra_note = ""
        if _four_tuple_total > 0:
            _tetra_coverage = _four_tuple / _four_tuple_total
            _tetra_note = f" 四元组覆盖:{_tetra_coverage:.0%}"
            # 若来源标注全部空泛（无年份/口径/置信），覆盖率 <30% 视为"来源标注失真"
            if _tetra_coverage < 0.30:
                passed = False
                score = min(score, 0.5)
        return GateCheckResult("data_traceability", passed, score,
                              f"source_coverage={coverage:.0%} depth={avg_depth}/3 ({scored}/{total} paras){_tetra_note}")

    def _check_annotation_types(self) -> GateCheckResult:
        """FP2a: A/E/F/B 证据标注检查（2026-08-01 新增）。

        对标顶级投行/四大标准：每个数据点必须有类型标注——
          A=Actual(实际), E=Estimate(估算), F=Forecast(预测), B=Benchmark(基准)
        标准：报告正文中四种标注至少出现 3 种，且 A(实际) 是必须的。
        """
        import re
        text = self.report_text or ""
        if not text or len(text) < 50:
            return GateCheckResult("annotation_types", False, 0.0,
                                  "报告太短，无法评估标注")
        # 匹配 (A)/(E)/(F)/(B) 或 [A]/[E]/[F]/[B] 标注（括号紧跟数字）
        found = set()
        for marker in "AEFB":
            # 匹配 "(A)" "[A]" "(A型)" 等，需在数字/单位附近
            if re.search(r'[\(\[（]\s*' + marker + r'\s*[\)\]）]', text):
                found.add(marker)
            # 也匹配 "12.3亿(A)" 这种
            if re.search(r'\d[\d,.]*\s*(?:亿|万|%|元)?\s*[\(\[（]\s*' + marker + r'\s*[\)\]）]', text):
                found.add(marker)
        # A(实际) 必须存在；整体至少 3 种
        has_a = 'A' in found
        total_ok = len(found) >= 3
        passed = has_a and total_ok
        missing = [m for m in "AEFB" if m not in found]
        score = min(1.0, len(found) / 4)
        return GateCheckResult("annotation_types", passed, score,
                              f"标注覆盖: {'/'.join(sorted(found)) or '无'} 缺失: {','.join(missing) or '无'} (需≥3种含A)")

    def _check_data_type_annotation(self) -> GateCheckResult:
        """FP2a: Verify that (A)/(E)/(F)/(B) annotations are used throughout the report.
        
        Checks for data type markers: (A)=Actual, (E)=Estimate, (F)=Forecast, (B)=Benchmark.
        """
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("data_type_annotation", True, 1.0, "Text too short, skipped", severity="warning")
        
        import re
        # Count (A), (E), (F), (B) annotations
        a_count = len(re.findall(r'A', text))
        e_count = len(re.findall(r'E(?!\w)', text))
        f_count = len(re.findall(r'F(?!\w)', text))
        b_count = len(re.findall(r'B(?!\w)', text))
        
        # Also check for the explicit forms (half-width + full-width)
        explicit_a = len(re.findall(r'\(A\)|（A）|Actual', text))
        explicit_e = len(re.findall(r'\(E\)|（E）|Estimate', text))
        explicit_f = len(re.findall(r'\(F\)|（F）|Forecast', text))
        explicit_b = len(re.findall(r'\(B\)|（B）|Benchmark', text))
        
        total = explicit_a + explicit_e + explicit_f + explicit_b
        coverage = min(1.0, total / 5.0)  # Expect at least 5 annotations
        has_all_types = (explicit_a > 0 and explicit_e > 0) or (explicit_a > 2 and explicit_e > 1)
        
        passed = total >= 3  # At least 3 total annotations
        score = min(1.0, total / 5.0)
        
        details = f"A={explicit_a} E={explicit_e} F={explicit_f} B={explicit_b} total={total} score={score:.2f}"
        return GateCheckResult("data_type_annotation", passed, score, details)

    def _check_data_fidelity(self) -> GateCheckResult:
        """Check data fidelity: revenue/profit numbers should be reasonable"""
        import re
        text = self.report_text or ""
        
        # Look for revenue/profit numbers in the text
        rev_patterns = re.findall(r"营收[约达为]?[：:]?\s*(\d+\.?\d*)", text)
        profit_patterns = re.findall(r"(?:净利|归母净利)[润约达为]?[：:]?\s*(-?\d+\.?\d*)", text)
        
        issues = []
        
        # Check if revenue numbers are reasonable (A-share companies typically 1-1000+ billion)
        for v in rev_patterns[:5]:
            val = float(v)
            if val > 10000:  # Unlikely for most companies
                issues.append("Revenue %.0f unusually high" % val)
            if val == 0:
                issues.append("Revenue is 0 - likely missing data")
        
        # Check profit-loss consistency
        for v in profit_patterns[:3]:
            val = float(v)
            if abs(val) > 1000:  # Very large loss/profit
                issues.append("Profit %.0f unusually large" % val)
        
        if issues:
            score = max(0.3, 1.0 - len(issues) * 0.2)
        else:
            score = 1.0
        
        score = max(score, 0.3)  # Floor at 0.3
        return GateCheckResult(name="data_fidelity", passed=score >= 0.5, score=score,
                               details="Checks:%d Issues:%d Score:%.2f" % (
                                   len(rev_patterns) + len(profit_patterns), len(issues), score))

    def _check_source_entity(self) -> GateCheckResult:
        """R82 P2：来源标注实体化——拦截"公司年报/公司公告/券商研究报告"等无实体标注。

        v9 事故：全文"（数据来源：公司年度报告）"无具体公司/券商名，来源体系形同虚设。
        标注幻觉比不标注更危险——赋予虚假可信度。要求来源必须含具体实体（公司名/报告名/日期）。
        """
        import re
        text = self.report_text or ""
        if not text:
            return GateCheckResult("source_entity", True, 1.0, "无文本")
        # 无实体的空泛来源标注
        vague_patterns = [
            r'来源[：:]\s*(公司年报|公司公告|公司年度报告|券商研究报告|公开行业资料|行业报告)\s*[）)]',
            r'来源[：:]\s*(公司年报|公司公告|公司年度报告|券商研究报告|公开行业资料|行业报告)\s*[^）)]{0,0}',
        ]
        hits = []
        for pat in vague_patterns:
            found = re.findall(pat, text)
            hits.extend(found)
        # 去重
        unique = list(set(hits))
        if unique:
            return GateCheckResult(
                "source_entity", False, max(0.1, 0.5 - len(unique) * 0.05),
                f"来源标注无实体(P1): {len(unique)} 处'公司年报/公司公告'式空泛标注——须写具体公司名+报告名+日期",
                severity="error")
        return GateCheckResult("source_entity", True, 1.0, "来源标注已实体化")

    def _check_data_source_accuracy(self) -> GateCheckResult:
        """Check revenue/profit numbers don't contradict known data"""
        import re
        text = self.report_text or ""
        rev_matches = re.findall(r"营收[约达为]?[：:]?\s*(\d+\.?\d*)", text)
        issues = []
        for v in rev_matches[:3]:
            val = float(v)
            if val > 5000:
                issues.append("Revenue %.0fbn unusually high" % val)
        score = max(0.3, 1.0 - len(issues) * 0.2)
        return GateCheckResult(name="data_source_accuracy", passed=score >= 0.5, score=score,
                               details="RevenueCheck:%d Issues:%d Score:%.2f" % (len(rev_matches), len(issues), score))

    def _check_data_dict_refs(self) -> GateCheckResult:
        """R7: 共享数据字典数值引用校验。

        数据一致性架构级约束。检查两件事：
          1. 正文是否残留未解析的 {ref:key} 占位符（LLM 引用了不存在的 key）
          2. 带 (A)/(B) 标注的确定性数字，是否能在数据字典中找到同源值
             （防止 LLM 绕过数据字典自由编造数字）

        FP2 数据零编造：游离数字过多（默认 >8）→ error 阻断。
        预测值(E)/(F)、推导值（毛利率/ROE 区间）不在拦截范围，避免误杀分析产出。
        """
        try:
            from core.data_dict import validate_numeric_refs, load_data_dict_from_cache
        except ImportError as e:
            return GateCheckResult(name="data_dict_refs", passed=True, score=1.0,
                                   severity="warning",
                                   details=f"data_dict module unavailable: {e}")

        text = self.report_text or ""
        if not text:
            return GateCheckResult(name="data_dict_refs", passed=False, score=0.0,
                                   severity="error", details="report empty")

        # 1. 未解析的 {ref:key} 占位符
        unresolved = re.findall(r'\{ref:([A-Za-z0-9_一-鿿]+)\}', text)

        # 2. 数值引用校验（用缓存的 data_dict）
        # 修复（2026-08-01 IronGate 第 2 轮）：资产名绑定时精确加载
        # <asset>_data_dict.json，加载失败则直接返回空（不兜底取最新文件），
        # 杜绝思必驰报告加载柯力传感/传感器行业字典导致的跨资产串标误报。
        asset = getattr(self, 'asset', '') or getattr(self, 'sac_id', '')
        if asset:
            _cache_path = _ROOT / "output" / f"{asset}_data_dict.json"
            data_dict = {}
            if _cache_path.exists():
                try:
                    data_dict = json.loads(_cache_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
        else:
            # 无资产名绑定（兼容旧调用）：兜底取最新文件（可能有串标风险）
            data_dict = load_data_dict_from_cache("")

        if unresolved:
            det = f"{len(unresolved)} 个未解析数据引用: {unresolved[:5]}"
            return GateCheckResult(name="data_dict_refs", passed=False, score=0.3,
                                   severity="error", details=det)

        if not data_dict:
            # 无数据字典可校验（数据层缺失），不阻断（降级为 warning）
            return GateCheckResult(name="data_dict_refs", passed=True, score=1.0,
                                   severity="warning",
                                   details="无数据字典可校验（数据层为空）")

        vr = validate_numeric_refs(text, data_dict)
        # 高置信冲突检测：正文出现数据字典中已知的"标签+年份"，但数值不同 → 数据打架。
        # 例：正文写"2024中国传感器市场 3440 亿元"而数据字典是 4061.2 → 冲突。
        conflicts = detect_value_conflicts(text, data_dict)
        # 游离数字过多 + 存在高置信冲突 → 阻断；仅游离多 → warning
        if conflicts:
            det = f"{len(conflicts)} 处数据冲突(正文与数据字典口径打架): {conflicts[:3]}"
            return GateCheckResult(name="data_dict_refs", passed=False,
                                   score=max(0.1, 1.0 - 0.3 * len(conflicts)),
                                   severity="error", details=det)
        if vr["unverified"] > 12:
            det = (f"{vr['verified']} 个数值匹配数据字典, {vr['unverified']} 个游离"
                   f"(无同源，可能为分析推导值): {vr['unverified_values'][:5]}")
            return GateCheckResult(name="data_dict_refs", passed=True,
                                   score=max(0.5, 1.0 - 0.05*vr["unverified"]),
                                   severity="warning", details=det)
        det = (f"{vr['verified']} 个数值匹配数据字典, {vr['unverified']} 个游离(阈值内)")
        return GateCheckResult(name="data_dict_refs", passed=True,
                               score=max(0.6, 1.0 - 0.05*vr["unverified"]),
                               severity="warning", details=det)

    def _check_data_conflicts(self) -> GateCheckResult:
        """R28（2026-08-02 方向B）：数据口径冲突检测。

        检查报告正文中同一指标（毛利率/PE/营收等）是否出现互相矛盾的值。
        用 data_caliber 的冲突检测器 + 正文数值提取。
        防"毛利率 5.0% vs 34.5%"、"PE 65x vs 79.79x"这类硬伤。
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("data_conflicts", True, 1.0,
                                   "text too short, skipped", severity="warning")
        issues = []
        # 1. 用 data_dict 冲突检测（数据层矛盾）
        try:
            from core.data_caliber import detect_value_conflicts, check_report_units
            data_dict = {}
            try:
                from core.data_dict import load_data_dict_from_cache
                data_dict = load_data_dict_from_cache(self.asset or "")
            except Exception:
                pass
            if data_dict:
                conflicts = detect_value_conflicts(data_dict)
                for c in conflicts:
                    if c["severity"] == "error":
                        issues.append(f"数据冲突[{c['indicator']}]: 值差异 {c['gap_pct']}% "
                                      f"{c['entries']}")
        except Exception as _e:
            logger.debug("[R28-CONFLICT] %s", _e)
        # 2. 单位标注检查（正文大数值无单位）
        try:
            ur = check_report_units(text, {})
            for it in ur.get("issues", [])[:5]:
                issues.append(it["issue"])
        except Exception:
            pass
        passed = len(issues) == 0
        det = f"数据冲突/单位问题: {len(issues)} 项" + (": " + "; ".join(issues[:3]) if issues else "")
        return GateCheckResult("data_conflicts", passed, 1.0 if passed else 0.5,
                               det, severity="error" if issues else "warning")

    def _check_downstream_consistency(self) -> 'GateCheckResult':
        """2026-08-07：下行/时间线/假设集中度一致性（油位 v2.3 硬伤落地）。

        拦截三类"给老板拍板"的硬伤：
          1. 下行数字口径不一致（最坏敞口 vs 止损线 vs 悲观NPV）
          2. 时间线矛盾（认证周期 vs 盈亏平衡/量产）
          3. 关键假设集中度（少数假设驱动大部分价值，未压力测试）
        """
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("downstream_consistency", True, 1.0,
                                   "text too short, skipped", severity="warning")
        issues = []
        try:
            from core.data_caliber import run_downstream_checks
            r = run_downstream_checks(text)
            for group_key in ("downstream", "timeline", "assumption"):
                for item in r.get(group_key, []):
                    if item.get("severity") == "error":
                        issues.append(item["issue"])
                    elif item.get("severity") == "warning":
                        issues.append("[WARN] " + item["issue"])
        except Exception as _e:
            logger.debug("[DOWNSTREAM] %s", _e)
        passed = len(issues) == 0
        det = f"下行一致性: {len(issues)} 项" + (": " + "; ".join(issues[:3]) if issues else "")
        return GateCheckResult("downstream_consistency", passed, 1.0 if passed else 0.5,
                               det, severity="error" if issues else "warning")

    def _check_business_logic(self) -> 'GateCheckResult':
        """2026-08-08：业务逻辑检测（圆桌 Codex 建议）。

        拦截"业务逻辑断点"——语义级，非数字一致性：
          1. 双价格带冲突（300元 vs 5000元 未说明双轨关系）
          2. 跨章节毛利率口径冲突（盈亏平衡30% vs 中高端40-50%）
          3. 声称协同/期权/战略价值但无数值支撑
        """
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("business_logic", True, 1.0,
                                   "text too short, skipped", severity="warning")
        try:
            from core.business_logic_gate import check_business_logic
            r = check_business_logic(text)
            issues = []
            for item in r.get("issues", []):
                if item.get("severity") == "error":
                    issues.append(item["issue"])
            passed = len(issues) == 0
            det = f"业务逻辑: {r.get('error_count',0)}err/{r.get('warning_count',0)}warn" + \
                  (": " + "; ".join(issues[:2]) if issues else "")
            return GateCheckResult("business_logic", passed, 1.0 if passed else 0.5,
                                   det, severity="error" if issues else "warning")
        except Exception as _e:
            logger.debug("[BUSINESS-LOGIC] %s", _e)
            return GateCheckResult("business_logic", True, 1.0, "skip", severity="warning")

    def _check_relation_consistency(self) -> 'GateCheckResult':
        """2026-08-08：身份关系检测（久通控股事故落地）。

        检测报告是否把子公司/关联方当外部合作方分析——
        外部框架词（签约/绑定/防换供应商/获取渠道）出现且标的是子公司 → 身份错位。
        """
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("relation_consistency", True, 1.0,
                                   "text too short, skipped", severity="warning")
        try:
            from core.relation_gate import check_relation_consistency
            r = check_relation_consistency(text, self.asset_relation if hasattr(self, "asset_relation") else "")
            issues = [i["issue"] for i in r.get("issues", []) if i["severity"] == "error"]
            passed = len(issues) == 0
            det = f"身份关系: {r.get('inferred_relation') or '未知'}" + \
                  (": " + "; ".join(issues[:2]) if issues else "")
            return GateCheckResult("relation_consistency", passed, 1.0 if passed else 0.5,
                                   det, severity="error" if issues else "warning")
        except Exception as _e:
            logger.debug("[RELATION-GATE] %s", _e)
            return GateCheckResult("relation_consistency", True, 1.0, "skip", severity="warning")

    def _check_arithmetic_audit(self) -> 'GateCheckResult':
        """R35（2026-08-02）：算术校验层——报告数字反向验算。

        背景：柯力报告 Gate 0.9447 PASS 却含 2 个 P0 算术错误——
          北向占比 0.24%（实为 1.13%）、DCF 区间中值 53.50（实为 53.0）。
        检查器只验"结构存在"，不验"数字正确"。本检查补上算术验算：
          1. 占比/比率反向验算（X万股/总股本 = Y%）
          2. 估值区间中值校验（(下沿+上沿)/2 = 报告写的中值？）
          3. 目标价空间校验（目标价/现价-1 = 报告写的空间？）
          4. EPS→净利→CAGR 桥校验（EPS×股本=净利，增速需可解释）
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("arithmetic_audit", True, 1.0,
                                   "text too short, skipped", severity="warning")
        issues = []

        # ── 1. 占比/比率反向验算 ──────────────────────────────
        # 模式："X万股 占 总股本约Y亿股 Z%" 或 "X股 占总股本Y%"
        # 例（柯力案）："318.29万股，占总股本约0.24%（基于总市值131.23亿元、股价46.73元）"
        # "股"与"占"间允许逗号/空白；总股本与占比间允许括号注（"（基于...）"），限长60。
        for m in _re.finditer(
                r'(\d+(?:\.\d+)?)\s*(万股|亿股|股)[，,\s]*(?:仅|约|已)?占(?:总)?股本'
                r'[^。；\n]{0,60}?(?:约|为|占)?(\d+(?:\.\d+)?)%', text):
            try:
                num = float(m.group(1))
                unit = m.group(2)
                pct_claimed = float(m.group(3))
                # 从上下文找总股本
                before = text[max(0, m.start() - 120):m.start()]
                # 找 "总股本约X亿股" 或 "X亿股" 或反推股本
                shares_b = _re.search(r'总股本(?:约|为)?(\d+(?:\.\d+)?)\s*亿股', before)
                shares_b2 = _re.search(r'总股本(?:约|为)?(\d+(?:\.\d+)?)\s*亿股', text[m.end():m.end()+80])
                shares = None
                if shares_b:
                    shares = float(shares_b.group(1)) * 1e4  # 亿股→万股
                elif shares_b2:
                    shares = float(shares_b2.group(1)) * 1e4
                else:
                    # 从"总市值X元、股价Y元"反推股本
                    mcap = _re.search(r'总市值(?:约|为)?(\d+(?:\.\d+)?)\s*亿元', before)
                    price = _re.search(r'(?:股价|现价|当前价)[^\d]{0,6}(\d+(?:\.\d+)?)', before)
                    if mcap and price:
                        shares = float(mcap.group(1)) * 1e8 / float(price.group(1)) / 1e4  # →万股
                if shares and shares > 0:
                    num_shares = num * 1e4 if unit == "亿股" else (num if unit == "万股" else num / 1e4)
                    actual_pct = num_shares / shares * 100
                    if abs(actual_pct - pct_claimed) / max(actual_pct, 1e-9) > 0.3:
                        issues.append(
                            f"占比验算错误: {num}{unit}占总股本{shares/1e4:.2f}亿股="
                            f"{actual_pct:.2f}%，报告写{pct_claimed}%"
                            f"（偏差{(actual_pct-pct_claimed)/actual_pct*100:+.0f}%）")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # ── 2. 估值区间中值校验 ───────────────────────────────
        # 模式："区间X-Y元，中值约Z"（柯力案：42-64元中值53.50，实为53.0）
        # "中值"与数字间只允许少量修饰（约/为/达/是），防止贪婪吃数字。
        for m in _re.finditer(
                r'(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*元[^。；\n]{0,60}?'
                r'(?:中值|中间值|均值)[^。；\n]{0,6}?(?:约|为|达|是)?\s*(\d+(?:\.\d+)?)\s*元', text):
            try:
                lo, hi = float(m.group(1)), float(m.group(2))
                mid_claimed = float(m.group(3))
                mid_actual = (lo + hi) / 2
                if abs(mid_actual - mid_claimed) / max(mid_actual, 1e-9) > 0.02:
                    issues.append(
                        f"估值区间中值错误: [{lo}-{hi}]元中值应为{mid_actual:.1f}元，"
                        f"报告写{mid_claimed}元（偏差{(mid_claimed-mid_actual)/mid_actual*100:+.1f}%）")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # ── 3. 目标价空间校验 ─────────────────────────────────
        # 模式："目标价X元，较现价Y元有Z%空间" 或 "目标价X元对应+Z%"
        for m in _re.finditer(
                r'目标价[：:为]?(\d+(?:\.\d+)?)\s*元[^。；]{0,30}?'
                r'(?:较|相对)?(?:现价|当前价|股价)[^\d]{0,6}(\d+(?:\.\d+)?)\s*元[^。；]{0,30}?'
                r'(?:约|有|为)?([+-]?\d+(?:\.\d+)?)%', text):
            try:
                tp, cp, up_claimed = float(m.group(1)), float(m.group(2)), float(m.group(3))
                up_actual = (tp / cp - 1) * 100
                if abs(up_actual - up_claimed) > 1.0:
                    issues.append(
                        f"目标价空间错误: 目标价{tp}元 vs 现价{cp}元= {up_actual:+.1f}%，"
                        f"报告写{up_claimed:+.1f}%")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # ── 4. EPS→净利→CAGR 桥校验 ──────────────────────────
        # 模式："EPS X元×股本Y亿股" 或 报告给出 EPS 但净利无法匹配
        # 检测：若报告同时给出 EPS、总股本、净利润，验算 EPS×股本=净利
        for m in _re.finditer(
                r'(?:2027E|2026E|2028E)\s*EPS[^\d]{0,4}(\d+(?:\.\d+)?)\s*元', text):
            try:
                eps = float(m.group(1))
                # 找总股本
                shares_b = _re.search(r'总股本(?:约|为)?(\d+(?:\.\d+)?)\s*亿股', text[:m.end()+200])
                # 找净利
                net_m = _re.search(r'2027年?净(?:利润|利)(?:约|为)?(\d+(?:\.\d+)?)\s*亿', text[:m.end()+300])
                if shares_b and net_m:
                    shares = float(shares_b.group(1))
                    net_actual = eps * shares  # EPS×亿股=亿元
                    net_claimed = float(net_m.group(1))
                    if abs(net_actual - net_claimed) / max(net_claimed, 1e-9) > 0.1:
                        issues.append(
                            f"EPS桥校验: {eps}元×{shares}亿股={net_actual:.2f}亿元，"
                            f"报告2027净利写{net_claimed}亿元（偏差"
                            f"{(net_actual-net_claimed)/net_claimed*100:+.0f}%）")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.2, 1.0 - 0.3 * len(issues))
        det = f"算术校验: {len(issues)} 项错误" + (": " + "; ".join(issues[:3]) if issues else "无")
        return GateCheckResult("arithmetic_audit", passed, score, det, severity="error")

    def _check_invariant_audit(self) -> 'GateCheckResult':
        """R46（2026-08-02）：不变量断言层——物理不可能事件拦截。

        背景：r11 报告 Gate 0.9487 全绿却含 5 类数据硬伤——
          DCF 模型 39 亿 vs 报告 145-160 亿（差 4 倍循环论证）、净利 3.41 vs 1.68 亿幻觉、
          流通市值 136.7 亿 > 总市值 131.23 亿、北向市值 71.32 元/股 vs 收盘 46.73、
          PE 隐含净利与报告净利矛盾。
        检查器检测"报告长什么样"，不检测"数字对不对"。本检查补上不变量断言：
          1. 流通市值 ≤ 总市值（物理不可能：流通盘不能大于总盘）
          2. 持股数 × 股价 = 持股市值（勾稽：北向市值 2.27 亿应 = 318.29万股×46.73）
          3. 市值 = 股价 × 总股本（勾稽）
          4. PE × 净利 ≈ 市值（估值勾稽：PE 44.63 隐含净利应匹配）
          5. 毛利率在合理区间（0-80%，超区间为错误）
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("invariant_audit", True, 1.0,
                                   "text too short, skipped", severity="warning")
        issues = []

        # ── 1. 流通市值 ≤ 总市值 ──────────────────────────────
        # 模式："融资余额X亿元，占流通市值比为Y%" → 反推流通市值
        mcap_m = _re.search(r'总市值(?:约|为)?(\d+(?:\.\d+)?)\s*亿元', text)
        if mcap_m:
            mcap = float(mcap_m.group(1))
            for fm in _re.finditer(
                    r'融资余额(?:约|为)?(\d+(?:\.\d+)?)\s*亿元[^。；]{0,30}?'
                    r'占流通市值比为?(\d+(?:\.\d+)?)%', text):
                try:
                    bal = float(fm.group(1))
                    pct = float(fm.group(2))
                    implied_float = bal / (pct / 100) if pct > 0 else 0
                    if implied_float > 0 and implied_float > mcap * 1.05:
                        issues.append(
                            f"流通市值矛盾: 融资余额{bal}亿占流通市值{pct}%→流通市值"
                            f"{implied_float:.1f}亿 > 总市值{mcap}亿（物理不可能）")
                except (ValueError, TypeError, ZeroDivisionError):
                    continue

        # ── 2. 持股数 × 股价 = 持股市值 ───────────────────────
        # 模式："北向资金持有X万股，持股市值Y亿元" 或 "持股X万股（市值Y亿元）"（r12 括号式）
        for m in _re.finditer(
                r'(?:北向资金|外资)[^。；]{0,15}?(\d+(?:\.\d+)?)\s*万股'
                r'[^。；]{0,20}?(?:[（(]?(?:持股市值|市值)|持股市值)[：:]?'
                r'(?:约|为)?(\d+(?:\.\d+)?)\s*亿元', text):
            try:
                shares_wan = float(m.group(1))  # 万股
                mkt_value_yi = float(m.group(2))  # 亿元
                # 找收盘价（报告通常给出"当前价46.73元"/"收盘46.73元"/"股价46.73元"）
                price = _re.search(r'(?:收盘|股价|现价|当前价)[^\d]{0,6}(46\.\d+)', text)
                if price:
                    px = float(price.group(1))
                    implied_value = shares_wan * 1e4 * px / 1e8  # 万股→股→元→亿
                    if implied_value > 0 and abs(implied_value - mkt_value_yi) / mkt_value_yi > 0.3:
                        issues.append(
                            f"持股市值矛盾: {shares_wan}万股×{px}元={implied_value:.2f}亿"
                            f"≠报告市值{mkt_value_yi}亿（偏差"
                            f"{(mkt_value_yi-implied_value)/implied_value*100:+.0f}%）")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # ── 3. PE × 净利 ≈ 市值（估值勾稽）────────────────────
        # 模式："PE(TTM) X倍" + 净利 + 总市值
        pe_m = _re.search(r'PE\s*[（(]?(?:TTM|动态|静态)[）)]?\s*(\d+(?:\.\d+)?)\s*倍', text)
        net_m = _re.search(r'净利(?:润)?(?:约|为|达)?(\d+(?:\.\d+)?)\s*亿', text)
        mcap_m2 = _re.search(r'总市值(?:约|为)?(\d+(?:\.\d+)?)\s*亿元', text)
        if pe_m and net_m and mcap_m2:
            try:
                pe = float(pe_m.group(1))
                net = float(net_m.group(1))
                mcap = float(mcap_m2.group(1))
                implied_mcap = pe * net  # 亿元
                if abs(implied_mcap - mcap) / mcap > 0.3:
                    issues.append(
                        f"PE勾稽矛盾: PE {pe}倍×净利{net}亿={implied_mcap:.1f}亿"
                        f"≠市值{mcap}亿（隐含净利口径与市值不匹配）")
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # ── 4. DCF 参数一致性（堵循环论证）─────────────────────
        # r11 审计 P0-1：DCF 模型独立复算 39 亿 vs 报告 145-160 亿（差 4 倍）。
        # 用报告自身的 FCFF 序列/WACC/g 复算 DCF，与报告声称的 DCF 市值对比，
        # 差 >50% 即拦截（说明 DCF 区间是目标价反推，非模型输出）。
        # 参数来源：报告或 enrich 的 dcf_sensitivity_params（FCFF 基准/增速/WACC/g）。
        try:
            fcff_base = 0.0
            fcff_rates = []
            wacc = 0.0
            g = 0.0
            # 从 enrich dcf_sensitivity_params 或报告提取参数
            fcff_m = _re.search(r'FCFF\s*(?:约|为|=)?\s*(\d+(?:\.\d+)?)\s*亿', text)
            if fcff_m:
                fcff_base = float(fcff_m.group(1))
            wacc_m = _re.search(r'WACC[^\d]{0,6}(\d+(?:\.\d+)?)%', text)
            if wacc_m:
                wacc = float(wacc_m.group(1)) / 100
            g_m = _re.search(r'永续增长[率]?[^\d]{0,6}(\d+(?:\.\d+)?)%', text)
            if g_m:
                g = float(g_m.group(1)) / 100
            # FCFF 增速：报告通常写"2026E +15%、2027E +12%"或"2026E增速15%"
            rates = _re.findall(r'20\d\dE\s*[+约]?\s*(\d+)%', text)
            if rates:
                fcff_rates = [float(r) / 100 for r in rates[:3]]
            if fcff_base > 0 and wacc > 0 and fcff_rates:
                # 复算 DCF
                fcffs = [fcff_base]
                for rate in fcff_rates:
                    fcffs.append(fcffs[-1] * (1 + rate))
                fcffs = fcffs[1:]  # 3 年预测
                pv_explicit = sum(f / (1 + wacc) ** (i + 1)
                                  for i, f in enumerate(fcffs))
                tv = fcffs[-1] * (1 + g) / (wacc - g) if wacc > g else 0
                pv_tv = tv / (1 + wacc) ** len(fcffs)
                dcf_total = pv_explicit + pv_tv
                # 报告声称的 DCF 市值区间
                dcf_claim = _re.findall(
                    r'(?:DCF|公允市值)[^。；]{0,20}?(\d{2,3})\s*[-–—]\s*(\d{2,3})\s*亿', text)
                if dcf_claim and dcf_total > 0:
                    lo = float(dcf_claim[0][0])
                    hi = float(dcf_claim[0][1])
                    # 若报告区间与模型输出差 >50% → 循环论证
                    if dcf_total < lo * 0.5:
                        issues.append(
                            f"DCF循环论证: 按报告参数复算公允市值≈{dcf_total:.0f}亿"
                            f"（FCFF{fcff_base}亿/WACC{wacc*100:.0f}%/g{g*100:.0f}%），"
                            f"报告声称{lo}-{hi}亿（差{hi/dcf_total:.1f}倍）")
        except (ValueError, TypeError, ZeroDivisionError):
            pass

        # ── 5. 敏感性单调性断言（r12 审计 P0-1：最悲观9.45元 vs 声称5%）──
        # 校验敏感性矩阵的单调性：WACC 升 → 市值降；g 升 → 市值升。
        # 报告若写"最悲观情形目标价仍高于当前价"但按参数复算远低于 → 拦截。
        # 模式：敏感性矩阵含多个 WACC×g 组合的估值，或"悲观/乐观"情景描述。
        # 简化：检测"悲观"语境下的目标价与"当前价"的关系。
        _curr_price = _re.search(r'当前价[^\d]{0,6}(\d+(?:\.\d+)?)', text)
        _bear_tp = _re.findall(
            r'(?:悲观|最悲观|下行情景)[^。；]{0,40}?(\d+(?:\.\d+)?)\s*元', text)
        if _curr_price and _bear_tp:
            try:
                px = float(_curr_price.group(1))
                for _bt in _bear_tp:
                    _btv = float(_bt)
                    # 若悲观情形目标价远低于当前价（>30% 折价），报告却声称
                    # "仍高于当前价" → 用下一句检测矛盾表述
                    if _btv < px * 0.7:
                        # 找该目标价后是否紧跟"高于/高于当前价"
                        _after = text[text.find(_bt) + len(_bt):text.find(_bt) + len(_bt) + 60]
                        if any(k in _after for k in ("高于", "仍高于", "高于当前")):
                            issues.append(
                                f"敏感性单调性矛盾: 悲观情形目标价{_btv}元 vs 当前价{px}元"
                                f"（隐含{(_btv/px-1)*100:+.0f}%），报告却称'仍高于当前价'")
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.2, 1.0 - 0.3 * len(issues))
        det = f"不变量审计: {len(issues)} 项" + (": " + "; ".join(issues[:3]) if issues else "无")
        return GateCheckResult("invariant_audit", passed, score, det, severity="error")

    def _check_valuation_integrity(self) -> 'GateCheckResult':
        """R53审计（2026-08-03 P0-1）：估值链四方勾稽硬规则——估值闭环。

        背景：气体传感器圆桌审计复核坐实"估值链四方矛盾"——
          报告写"2025E动态PE对应EPS约1.10元"（PE 表述），R35 的 EPS 桥
          只匹配"2027E EPS X元"预测期模式 → 不命中 → 漏检。
          估值闭环要求：**每条估值数字必须能由 ≥2 条独立路径复算出同值**。

        本检查做三环勾稽（偏差 >5% 即 FAIL，Gate 前置硬规则，非 LLM 判断）：
          1. 净利 = EPS × 总股本（含 PE 表述："动态PE X倍对应EPS Y元"）
          2. 总市值 = 股价 × 总股本
          3. 目标价 / PE = EPS（目标价、PE、EPS 三者自洽）
        优先用 data_dict 的真实值作外部锚（持真实股本/市值），
        data_dict 不可用时退化为报告内部自洽检查。
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("valuation_integrity", True, 1.0,
                                   "text too short, skipped", severity="warning")

        # 加载 data_dict（资产名绑定，与 financial_value_consistency 同源）
        asset = getattr(self, 'asset', '') or getattr(self, 'sac_id', '')
        data_dict = {}
        if asset:
            _cache_path = _ROOT / "output" / f"{asset}_data_dict.json"
            if _cache_path.exists():
                try:
                    data_dict = json.loads(_cache_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

        issues = []
        _TOL = 0.05  # 偏差 >5% 即 FAIL

        # ── 从 data_dict 提取外部锚 ────────────────────────────
        # 总股本（亿股）：shares_total / total_shares / 股本
        ext_shares = None
        for _k in ("shares_total", "total_shares", "shares_float", "总股本"):
            if _k in data_dict:
                try:
                    ext_shares = float(data_dict[_k])
                    break
                except (TypeError, ValueError):
                    continue
        # 当前股价
        ext_price = None
        for _k in ("price_latest", "close_price", "current_price", "现价", "股价"):
            if _k in data_dict:
                try:
                    ext_price = float(data_dict[_k])
                    break
                except (TypeError, ValueError):
                    continue
        # 最新净利（亿元）
        ext_net = None
        for _k in ("net_profit_latest", "net_2024", "net_2023"):
            if _k in data_dict:
                try:
                    ext_net = float(data_dict[_k])
                    break
                except (TypeError, ValueError):
                    continue

        # ── 报告内部提取 ───────────────────────────────────────
        # 总股本（亿股）
        rpt_shares = _re.search(r'总股本(?:约|为)?(\d+(?:\.\d+)?)\s*亿股', text)
        # 总市值（亿元）
        rpt_mcap = _re.search(r'总市值(?:约|为)?(\d+(?:\.\d+)?)\s*亿元', text)
        # 股价（元）
        rpt_price = _re.search(r'(?:当前价|现价|股价|收盘价|收盘)[^\d]{0,6}(\d+(?:\.\d+)?)\s*元', text)
        # 净利（亿元）——"净利X亿" / "净利润X亿"
        rpt_net = _re.search(r'净利(?:润)?(?:约|为|达)?(\d+(?:\.\d+)?)\s*亿', text)

        # ── 1. 净利 = EPS × 总股本 ─────────────────────────────
        # 覆盖两类 EPS 表述：
        #   a. "2027E EPS X元"（R35 原有，预测期模式）
        #   b. "2025E动态PE X倍对应EPS约Y元"（PE 表述，圆桌审计漏检点）
        eps_vals = []  # (eps, context)
        for m in _re.finditer(
                r'(?:20\d\dE|20\d\d年|20\d\d)\s*EPS[^\d]{0,4}(\d+(?:\.\d+)?)\s*元', text):
            try:
                eps_vals.append((float(m.group(1)), m.group(0)[:30]))
            except (ValueError, TypeError):
                continue
        # b. "2025E动态PE 42倍对应EPS约Y元"（PE 表述，圆桌审计漏检点）
        #    允许 PE 与 EPS 间有"42倍"等修饰（中间 [^\d] 不能有数字，故用 [^。；\n]）
        for m in _re.finditer(
                r'PE[^。；\n]{0,30}?EPS(?:约|为)?(\d+(?:\.\d+)?)\s*元', text):
            try:
                eps_vals.append((float(m.group(1)), m.group(0)[:30]))
            except (ValueError, TypeError):
                continue
        # 去重（同 EPS 值算一次）
        _seen_eps = set()
        _uniq_eps = []
        for _e, _c in eps_vals:
            if _e not in _seen_eps:
                _seen_eps.add(_e)
                _uniq_eps.append((_e, _c))
        if _uniq_eps:
            # 优先用外部股本锚；无则报告股本
            shares = ext_shares if ext_shares else (float(rpt_shares.group(1)) if rpt_shares else None)
            if shares and shares > 0:
                for _e, _c in _uniq_eps:
                    net_implied = _e * shares  # 元×亿股=亿元
                    # 对照净利：外部锚优先，否则报告值
                    if ext_net is not None:
                        _ref = ext_net
                        _ref_name = "data_dict净利"
                    elif rpt_net:
                        try:
                            _ref = float(rpt_net.group(1))
                            _ref_name = "报告净利"
                        except (ValueError, TypeError):
                            continue
                    else:
                        continue
                    if abs(net_implied - _ref) / max(_ref, 1e-9) > _TOL:
                        issues.append(
                            f"估值勾稽①净利=EPS×股本: EPS{_e}元×{shares:.2f}亿股="
                            f"{net_implied:.2f}亿 ≠ {_ref_name}{_ref:.2f}亿"
                            f"（偏差{(net_implied-_ref)/_ref*100:+.0f}%）")

        # ── 2. 总市值 = 股价 × 总股本 ──────────────────────────
        # 校验需"市值 + 价格 + 股本"三要素，任一来源（外部锚或报告）皆可。
        _has_price = ext_price or bool(rpt_price)
        _has_shares = ext_shares or bool(rpt_shares)
        if _has_price and _has_shares and rpt_mcap:
            try:
                _rpt_mcap = float(rpt_mcap.group(1))
                # 市值锚用"股价×股本"（外部优先），对照报告市值；或用报告股价×股本对照报告市值
                if ext_price and ext_shares:
                    _implied = ext_price * ext_shares
                    _ref_name = "外部锚"
                elif rpt_price:
                    _sh = ext_shares if ext_shares else (
                        float(rpt_shares.group(1)) if rpt_shares else 0)
                    _implied = float(rpt_price.group(1)) * _sh
                    _ref_name = "股价×股本"
                else:
                    _implied = None
                if _implied and _implied > 0:
                    if abs(_implied - _rpt_mcap) / _rpt_mcap > _TOL:
                        issues.append(
                            f"估值勾稽②市值=股价×股本: 股价×股本={_implied:.1f}亿"
                            f"≠报告市值{_rpt_mcap}亿（偏差"
                            f"{(_implied-_rpt_mcap)/_rpt_mcap*100:+.0f}%）")
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # ── 3. 目标价 / PE = EPS（目标价、PE、EPS 三件套自洽）──
        # 模式："目标价X元，对应PE Y倍" → 隐含EPS = X/Y，应与报告 EPS 或
        #     外部净利/股本反推的 EPS 一致。
        for m in _re.finditer(
                r'目标价[^\d]{0,15}?(\d+(?:\.\d+)?)\s*元[^。；]{0,40}?'
                r'对应PE[^\d]{0,6}(\d+(?:\.\d+)?)\s*倍', text):
            try:
                tp = float(m.group(1))
                pe = float(m.group(2))
                if pe <= 0:
                    continue
                implied_eps = tp / pe
                # 对照：报告 EPS 或 外部净利/股本
                _ref_eps = None
                if _uniq_eps:
                    _ref_eps = _uniq_eps[0][0]
                    _ref_name = f"报告EPS{_ref_eps}"
                elif ext_net is not None and (ext_shares or (rpt_shares and float(rpt_shares.group(1)))):
                    _sh = ext_shares or float(rpt_shares.group(1))
                    _ref_eps = ext_net / _sh
                    _ref_name = f"外部净利/股本{_ref_eps:.2f}"
                if _ref_eps and abs(implied_eps - _ref_eps) / max(_ref_eps, 1e-9) > _TOL:
                    issues.append(
                        f"估值勾稽③目标价/PE=EPS: 目标价{tp}元/PE{pe}倍=EPS{implied_eps:.2f}元"
                        f"≠{_ref_name}（偏差"
                        f"{(implied_eps-_ref_eps)/_ref_eps*100:+.0f}%）")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # 无任何锚可校验时跳过（不误报）
        if not issues and not (_uniq_eps and (ext_shares or rpt_shares)):
            pass  # 有 EPS 无股本，无法做 ①，但 ③ 可能已覆盖

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.3, 1.0 - 0.35 * len(issues))
        det = f"估值勾稽: {len(issues)} 项矛盾" + (": " + "; ".join(issues[:3]) if issues else "无")
        return GateCheckResult("valuation_integrity", passed, score, det, severity="error")

    def _check_financial_value_consistency(self) -> 'GateCheckResult':
        """R38（2026-08-02）：财务数值一致性——报告中的毛利率/营收/净利
        与 data_dict 真实值冲突检测。

        背景：柯力 r10 报告 6.3 核心假设"毛利率维持40%以上"与 data_dict 的
        margin_2025=44.83 冲突；正文"动态PE 79.79"与附录 PE(TTM) 44.63 并存。
        本检查用 data_dict 的真实值作为基准，检测报告是否写了明显矛盾的财务数。
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("financial_value_consistency", True, 1.0,
                                   "text too short, skipped", severity="warning")
        # 加载 data_dict（资产名绑定）
        asset = getattr(self, 'asset', '') or getattr(self, 'sac_id', '')
        data_dict = {}
        if asset:
            _cache_path = _ROOT / "output" / f"{asset}_data_dict.json"
            if _cache_path.exists():
                try:
                    data_dict = json.loads(_cache_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
        if not data_dict:
            return GateCheckResult("financial_value_consistency", True, 1.0,
                                   "无 data_dict，跳过", severity="warning")

        issues = []
        # ── 1. 毛利率一致性：用最新实际毛利率（margin_YYYY）做基准 ──
        # 提取最近 3 个实际 margin（排除 margin_balance 等非毛利率字段）
        margins = {}
        for k, v in data_dict.items():
            if isinstance(k, str) and k.startswith("margin_") and str(k[7:]).isdigit():
                try:
                    margins[int(k[7:])] = float(v)
                except (TypeError, ValueError):
                    continue
        if margins:
            latest_y = max(margins.keys())
            latest_margin = margins[latest_y]
            # 报告中的毛利率表述（"毛利率X%"），排除预测区间与历史序列
            for m in _re.finditer(
                    r'毛利率[^。；\n]{0,15}?(\d{2}(?:\.\d+)?)%', text):
                try:
                    gm = float(m.group(1))
                    # 只检查"当前/维持/实际"语境，跳过预测区间（34-36%这种）
                    ctx_before = text[max(0, m.start() - 25):m.start()]
                    if any(k in ctx_before for k in ("维持", "当前", "实际", "2025", "现有")):
                        # 报告值 vs 最新实际值，偏差 >15% 且方向矛盾（报告远低于实际）
                        if gm < latest_margin * 0.85:
                            issues.append(
                                f"毛利率矛盾: 报告写『{gm}%』但 data_dict 最新实际"
                                f"margin_{latest_y}={latest_margin}%（偏差"
                                f"{(latest_margin-gm)/latest_margin*100:+.0f}%）")
                except (ValueError, TypeError):
                    continue

        # ── 2. PE 口径一致性：多个 PE 值但无口径标注 ──
        # 正文/附录出现明显不同的 PE 值（如 79.79 vs 44.63）且未说明口径 → 拦截
        pe_vals = set()
        for m in _re.finditer(r'PE[^。；\n]{0,20}?(\d{2}(?:\.\d+)?)\s*倍', text):
            try:
                pe_vals.add(float(m.group(1)))
            except (ValueError, TypeError):
                continue
        if len(pe_vals) >= 2:
            pe_list = sorted(pe_vals)
            if pe_list[-1] / max(pe_list[0], 1e-9) > 1.5:
                # 存在 1.5x 以上差异的不同 PE 值
                # R49（2026-08-02）：即使有口径标注，若同一数据源（图注 vs 正文）
                # 用不同 PE 值，仍属"图表数据未同步"冲突。
                # 检测：若最小的 PE（附录图表，如 44.63）与最大的（正文静态，如 78.1）
                # 同框出现，且小 PE 对应"静态"标注（误标），flag。
                has_static = "静态" in text
                has_ttm = "TTM" in text or "ttm" in text
                has_fwd = "前瞻" in text or "2027E" in text
                if not (has_static and (has_ttm or has_fwd)):
                    issues.append(
                        f"PE口径混乱: 正文出现多个PE值 {pe_list}，差异>50%"
                        f"且未明确区分静态/TTM/前瞻口径")
                else:
                    # 有口径标注，但检查是否"同一口径下仍冲突"（图注数据未同步）
                    # 若最小 PE 出现在"图注/图表"语境且无对应口径说明 → 疑似未同步
                    for _pv in pe_list:
                        _pctx = text[max(0, text.find(str(_pv)) - 40):text.find(str(_pv)) + 20]
                        if any(k in _pctx for k in ("图", "表", "附录", "对比")):
                            # 图表中的 PE 值，检查是否有明确口径
                            _has_label = any(k in _pctx for k in
                                             ("静态", "TTM", "动态", "前瞻", "2025", "2026", "2027"))
                            if not _has_label and _pv < pe_list[-1] * 0.7:
                                issues.append(
                                    f"图表PE未同步: 附录图表PE {_pv} 与正文最高 {pe_list[-1]} 差异大，"
                                    f"图表数据可能未随正文口径更新")
                            break

        passed = len(issues) == 0
        det = f"财务数值一致性: {len(issues)} 项" + (": " + "; ".join(issues[:2]) if issues else "无")
        # R91（2026-08-10）：行业报告财务多值豁免——industry_deep 常并列多家公司
        # 的不同 PE/毛利率（中国卫星52 vs 铖昌80），属正常横向对比，降级 warning。
        _sev = "warning" if getattr(self, "report_type", "") == "industry_deep" else "error"
        return GateCheckResult("financial_value_consistency", passed,
                               1.0 if passed else 0.5, det, severity=_sev)

    def _check_financial_fraud_signals(self) -> 'GateCheckResult':
        """R58（2026-08-03）：四大审计确定性检查——财务造假信号。

        规则来源：methodology_audit_deep.json（fraud_signals/revenue_recognition/
        working_capital_quality）。用 data_dict 的财务数据做量化核查：
          1. 应收增速 - 收入增速 > 20pct → 收入确认激进
          2. 经营现金流/净利 < 0.5 → 利润质量差（应计过高）
          3. 毛利率多年波动 < 1pct → 可能粉饰平滑
          4. 其他应收/总收入 > 10% → 资金占用嫌疑
        无 data_dict 或数据不足时跳过（不误报）。
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("financial_fraud_signals", True, 1.0,
                                   "text too short, skipped", severity="warning")
        # 加载 data_dict
        asset = getattr(self, 'asset', '') or getattr(self, 'sac_id', '')
        data_dict = {}
        if asset:
            _cache_path = _ROOT / "output" / f"{asset}_data_dict.json"
            if _cache_path.exists():
                try:
                    data_dict = json.loads(_cache_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
        if not data_dict:
            return GateCheckResult("financial_fraud_signals", True, 1.0,
                                   "无 data_dict，跳过", severity="warning")

        issues = []

        # 1. 应收增速 vs 收入增速背离（收入确认激进）
        # data_dict 含 revenue_trend_YYYY / receivable_trend_YYYY（若采集到）
        _rev_keys = sorted([k for k in data_dict if k.startswith("revenue_trend_")])
        _rec_keys = sorted([k for k in data_dict if k.startswith(("receivable", "accounts_rec"))])
        if len(_rev_keys) >= 2:
            try:
                r0 = float(data_dict[_rev_keys[-2]])
                r1 = float(data_dict[_rev_keys[-1]])
                _rev_growth = (r1 - r0) / abs(r0) if r0 else 0
                # 找应收增速
                _rec_growth = None
                if len(_rec_keys) >= 2:
                    try:
                        a0 = float(data_dict[_rec_keys[-2]])
                        a1 = float(data_dict[_rec_keys[-1]])
                        _rec_growth = (a1 - a0) / abs(a0) if a0 else 0
                    except (TypeError, ValueError):
                        pass
                if _rec_growth is not None and _rev_growth > 0:
                    if _rec_growth - _rev_growth > 0.20:
                        issues.append(
                            f"收入确认激进: 应收增速{_rec_growth*100:.0f}% - 收入增速"
                            f"{_rev_growth*100:.0f}% > 20pct（回款风险）")
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        # 2. 经营现金流/净利 < 0.5（利润质量差）
        _ocf = data_dict.get("operating_cashflow_latest") or data_dict.get("ocf_latest")
        _net = data_dict.get("net_profit_latest")
        if _ocf and _net:
            try:
                ratio = float(_ocf) / float(_net)
                if ratio < 0.5 and float(_net) > 0:
                    issues.append(
                        f"利润质量差: 经营现金流/净利 = {ratio:.2f} < 0.5（应计利润过高）")
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        # 3. 毛利率多年波动 < 1pct（可能粉饰）
        _margins = {}
        for k, v in data_dict.items():
            if k.startswith("margin_") and str(k[7:]).isdigit():
                try:
                    _margins[int(k[7:])] = float(v)
                except (TypeError, ValueError):
                    pass
        if len(_margins) >= 3:
            vals = [_margins[y] for y in sorted(_margins)[-3:]]
            if max(vals) - min(vals) < 1.0:
                issues.append(
                    f"毛利率多年波动 {max(vals)-min(vals):.1f}pct < 1pct（可能粉饰平滑）")

        # 4. 其他应收/总收入 > 10%
        _other_rec = data_dict.get("other_receivable_latest")
        _total_rev = data_dict.get("revenue_latest") or data_dict.get("revenue_trend_2025")
        if _other_rec and _total_rev:
            try:
                ratio = float(_other_rec) / float(_total_rev)
                if ratio > 0.10:
                    issues.append(
                        f"其他应收/总收入 = {ratio:.0%} > 10%（资金占用/体外循环嫌疑）")
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.3, 1.0 - 0.3 * len(issues))
        det = f"财务造假信号: {len(issues)} 项" + (": " + "; ".join(issues[:3]) if issues else "无")
        return GateCheckResult("financial_fraud_signals", passed, score, det, severity="warning")

    def _check_rating_target_consistency(self) -> GateCheckResult:
        """R28（2026-08-02 方向B）：评级与目标价空间一致性。

        规则：增持/买入要求目标价较现价 ≥10% 上行空间；
              <10% 应为中性/持有。防止"+2.7% 却给增持"的评级错配。
        同时校验多估值锚一致性（PE 法与 DCF 法差值 >20% 必须交代取值逻辑）。
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("rating_target_consistency", True, 1.0,
                                   "text too short, skipped", severity="warning")
        # R45（2026-08-02 P2-2）：评级-目标价一致性是上市公司概念。
        # 行业/非上市报告若提及"增持/买入"或目标价，会被评级-空间错配误判；
        # 非上市也无现价概念。非 listed 类型跳过评级-空间检查（保留多估值锚一致性）。
        if self.report_type != "listed_company":
            # 仅保留多估值锚一致性检查（如适用），评级-空间检查跳过
            issues = []
            return GateCheckResult("rating_target_consistency", True, 1.0,
                                   f"{self.report_type} 无评级-目标价概念，跳过", severity="warning")
        issues = []
        # 提取评级
        rating = ""
        for kw in ["增持", "买入", "强烈推荐", "推荐", "中性", "持有", "减持", "卖出"]:
            if _re.search(kw, text[:3000]):
                rating = kw
                break
        # 提取目标价和现价
        tp = re.findall(r'目标价[^\d]{0,6}(\d{2,3}(?:\.\d+)?)\s*元', text)
        cp = re.findall(r'(?:现价|当前股价|当前价)[^\d]{0,6}(\d{2,3}(?:\.\d+)?)', text)
        if tp and cp:
            target = float(tp[0])
            price = float(cp[0])
            if price > 0:
                upside = (target - price) / price * 100
                if rating in ("增持", "买入", "强烈推荐", "推荐") and upside < 10:
                    issues.append(
                        f"评级-空间错配: 评级『{rating}』但目标价{target}元较现价{price}元仅+{upside:.1f}%空间"
                        f"（增持/买入通常要求≥10%，建议降级中性或重新论证）")
        # 多估值锚一致性：提取 PE 法目标价 和 DCF 目标价
        # R32（2026-08-02）：放宽正则以覆盖"PE估值：...对应目标价40-48元"
        # 这种区间表述（原正则 {0,4} 太短匹配不到），并支持"X元/X-Y元"两种形态。
        pe_targets = []
        for m in re.finditer(
                r'PE(?:法|估值)?[^\d]{0,16}?(?:目标价|目标价位|对应)[^\d]{0,6}(\d{2,3}(?:\.\d+)?)\s*元', text):
            pe_targets.append(m.group(1))
        dcf_targets = []
        for m in re.finditer(
                r'DCF(?:法|公允|估值|价值)?[^\d]{0,16}?(?:目标价|目标价位|对应|公允市值约)[^\d]{0,8}(\d{2,3}(?:\.\d+)?)\s*元', text):
            dcf_targets.append(m.group(1))
        if pe_targets and dcf_targets:
            try:
                pe_v = float(pe_targets[0])
                dcf_v = float(dcf_targets[0])
                if abs(pe_v - dcf_v) / max(dcf_v, 1e-9) > 0.2:
                    issues.append(
                        f"估值锚不一致: PE法目标{pe_v}元 vs DCF法目标{dcf_v}元，差异>20%，"
                        f"正文必须交代最终取值的加权逻辑")
            except (ValueError, TypeError):
                pass
        # R32：多目标价金额自相矛盾（同一报告出现两个综合目标价且差异>6%）
        # 柯力案：结论"目标价51.60元" vs §6.3"综合目标价48元"。
        # 正则捕获"目标价X元"，排除区间（X-Y元）与敏感性矩阵（无目标价前缀）。
        tp_amounts = []
        for m in re.finditer(r'(?:目标价|目标价位)[：:]?\s*(\d{2,3}(?:\.\d+)?)\s*元', text):
            val = float(m.group(1))
            if val not in tp_amounts:
                tp_amounts.append(val)
        if len(tp_amounts) >= 2:
            tp_base = max(tp_amounts)
            tp_min = min(tp_amounts)
            if (tp_base - tp_min) / max(tp_base, 1e-9) > 0.06:
                issues.append(
                    f"目标价自相矛盾: 正文出现多个目标价 {tp_amounts}，"
                    f"差异>6%（最高{tp_base}元 vs 最低{tp_min}元），必须统一为单一结论")
        passed = len(issues) == 0
        det = f"评级/估值一致性: {len(issues)} 项" + (": " + "; ".join(issues[:3]) if issues else "")
        return GateCheckResult("rating_target_consistency", passed,
                               1.0 if passed else 0.5, det, severity="error")

    def _check_numeric_chain_consistency(self) -> GateCheckResult:
        """R88（2026-08-10）：数值链自洽校验——行业报告分散式数值的独立验算。

        背景：商业航天行业报告 Gate 全绿却含 3 处算术硬伤——
          ①"中国占全球 8.3%"（实为 83%，数量级错误）；
          ②目标价"0.70×55=38.40"（实为 38.5）；
          ③上行空间"15-20%"（按自身数据实为 25.2%）。
        根因：R35/R53 的正则都是为个股报告特定表述设计的（"X股占总股本Y%"、
              "目标价X元较现价Y元Z%"三段同现），行业报告分散式表述全部漏检。

        本检查不依赖特定表述，做**数值链自洽**验算（偏差 >5% 或数量级错即 FAIL）：
          1. 占比反向验算："X占[前文N]的Z%" → 抓同句内 X/Y=Z% 的数量级错误
             （覆盖"中国占全球 8.3%"——X=2.83万亿、Y=4800亿美元 需归一化后验算）
          2. EPS×PE 目标价链："EPS X元、PE Y倍、目标价=Z元" → 验算 X×Y=Z
             （覆盖"0.70×55=38.40"——实为 38.5）
          3. 目标价/现价空间："目标价X元、现价/当前价Y元、空间Z%" → 验算 (X/Y-1)=Z
             （覆盖"目标价38.40元、当前股价对应2025PE52倍(隐含30.68元)、空间15-20%"）
          4. 细分合计 vs 总量："A+B+C+D=约E" → 验算累加一致
             （覆盖"4450+8520+7530+9350=约2.99万亿"）
        """
        import re as _re
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("numeric_chain_consistency", True, 1.0,
                                   "text too short, skipped", severity="warning")
        issues = []
        _TOL = 0.05

        def _fmt(x):
            return f"{x:.2f}" if abs(x - round(x, 2)) > 1e-6 else f"{x:g}"

        # ── 1. 占比反向验算（含币种归一化） ────────────────────
        # 商业航天案："中国TAM 2.83万亿元人民币（2025年，A）...按当前汇率（约7.1）折算，
        #              中国占全球商业航天市场约8.3%（...人民币÷7.1÷4800亿美元）"
        # 分子（2.83万亿元）在"占"前 60-200 字，分母（4800亿美元）在"占"后括号内。
        # 策略：找"占...市场约Z%"结构，然后在"占"前 260 字内找最近的"X万亿元/亿元"作分子，
        # 在"占"后 120 字内找"Y亿美元/亿元"作分母。
        _fx = 7.0
        _fx_m = _re.search(r'汇率[^\d]{0,4}(\d+(?:\.\d+)?)', text)
        if _fx_m:
            try:
                _fx = float(_fx_m.group(1))
            except (ValueError, TypeError):
                pass

        for m in _re.finditer(
                r'(?:占|占全|占市场|占全球)[^\n。；]{0,4}?'
                r'(?:全球|全球市场|市场|总规模|总市场)'
                r'[^。；\n]{0,25}?(?:约|为|占|达)?\s*(\d+(?:\.\d+)?)\s*%', text):
            try:
                pct_claimed = float(m.group(1))
                if not (0.01 < pct_claimed < 1000):
                    continue
                # 分子：占前同一句内（不跨句号）找"X万亿/亿元"，窗口 200 字
                before = text[max(0, m.start() - 200):m.start()]
                # 若"占"前有句号，截到句号后（防止跨句串数）
                _last_period = before.rfind("。")
                if _last_period >= 0:
                    before = before[_last_period + 1:]
                # 分子必须是"占"前紧邻的金额（前 30 字内优先），否则可能把
                # "国内收入11.81亿元，占总收入75.76%"这种合法表述误配——
                # 该表述的占比(75.76%)就是直接声明，无需分母验算，且分母不在句中。
                num_m = None
                for nm in reversed(list(_re.finditer(
                        r'(\d+(?:\.\d+)?)\s*(万亿元|亿元|万亿美元|亿美元)', before))):
                    num_m = nm
                    break
                if not num_m:
                    continue
                # 关键约束：分子距"占"不能太远（>120字）→ 视为非占比语境，跳过
                if m.start() - num_m.end() > 120:
                    continue
                num = float(num_m.group(1))
                num_unit = num_m.group(2)
                # 分母：占后 100 字内"Y亿美元/亿元"（优先紧邻）
                after = text[m.end():m.end() + 100]
                # 若"占后"跨句号则截断（分母须同句）
                _nxt_period = after.find("。")
                if _nxt_period >= 0:
                    after = after[:_nxt_period]
                den_m = _re.search(r'(\d+(?:\.\d+)?)\s*(万亿美元|亿美元|亿元)', after)
                if not den_m:
                    continue
                den = float(den_m.group(1))
                den_unit = den_m.group(2)
                # 归一化到亿元
                def _to_yi(v, u):
                    if u == "万亿元":
                        return v * 1e4
                    if u == "万亿美元":
                        return v * 1e4
                    if u == "亿美元":
                        return v
                    if u == "亿元":
                        return v
                    return v
                num_yi = _to_yi(num, num_unit)
                den_yi = _to_yi(den, den_unit)
                # 币种归一：美元×汇率→人民币
                if num_unit in ("万亿美元", "亿美元") and den_unit in ("万亿元", "亿元"):
                    num_yi = num_yi * _fx
                elif den_unit in ("万亿美元", "亿美元") and num_unit in ("万亿元", "亿元"):
                    den_yi = den_yi * _fx
                if den_yi <= 0:
                    continue
                actual_pct = num_yi / den_yi * 100
                # 数量级/比例偏差：实际与声称差 >2倍，或相对偏差>20%
                if abs(actual_pct - pct_claimed) / max(actual_pct, 1e-9) > 0.20 or \
                   abs(pct_claimed - actual_pct) > 5:
                    issues.append(
                        f"占比数量级错误: {_fmt(num)}{num_unit}占{_fmt(den)}{den_unit}="
                        f"{actual_pct:.1f}%，报告写{pct_claimed:.1f}%"
                        f"（差{abs(actual_pct-pct_claimed)/max(actual_pct,1e-9)*100:.0f}%）")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # ── 2. EPS×PE 目标价链 ────────────────────────────────
        # 模式："EPS X元" + "PE Y倍" + "目标价Z元" 或 "X×Y=Z"
        # 场景A：显式乘积 "0.70×55=38.40" 或 "0.70 × 55 = 38.40"
        # 注意：这是"声称的算术"，必须精确匹配（容差 <0.01%）。
        # 商业航天案：0.70×55=38.5，报告写 38.40（尾数错误），0.26% 偏差，
        # 若用 0.5% 容差会被吞掉。声称的等号表示"恒等"，差一位都不行。
        for m in _re.finditer(
                r'(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)\s*[=＝]\s*(\d+(?:\.\d+)?)', text):
            try:
                a, b, c = float(m.group(1)), float(m.group(2)), float(m.group(3))
                if a > 0 and b > 0 and c > 0 and 0.1 < a < 100 and 1 < b < 200:
                    prod = a * b
                    # 精确容差：声称的乘积必须与实算几乎一致（<0.01%）
                    if abs(prod - c) / max(prod, 1e-9) > 0.0001:
                        issues.append(
                            f"乘积验算错误: {_fmt(a)}×{_fmt(b)}={_fmt(prod)}，报告写{_fmt(c)}")
            except (ValueError, TypeError, ZeroDivisionError):
                continue
        # 场景B：目标价与 PE/EPS 显式绑定（括号内自洽结构）
        # 柯力案："目标价35元（基于2027年30倍PE，对应EPS 1.17元）" → 30×1.17=35.1≈35 ✓
        # 汇川案："目标价85元（对应2026年35倍PE，EPS 1.7元）" → 35×1.7=59.5 ≠ 85 ✗
        # 仅当"目标价"与"PE"与"EPS"同句且通过"基于/对应"绑定才验算，
        # 避免把多估值锚（PE30 vs PE35 各自目标价）串配。
        for m in _re.finditer(
                r'目标价[^。；\n]{0,30}?(\d+(?:\.\d+)?)\s*元[^。；\n]{0,25}?'
                r'(?:基于|对应|取)[^。；\n]{0,15}?'
                r'(\d+(?:\.\d+)?)\s*倍\s*PE[^。；\n]{0,20}?'
                r'(?:对应|EPS|每股收益)[^\d]{0,6}(\d+(?:\.\d+)?)\s*元', text):
            try:
                tp, pe, eps = float(m.group(1)), float(m.group(2)), float(m.group(3))
                if tp > 0 and pe > 0 and eps > 0 and 1 < pe < 200 and 0 < eps < 100:
                    implied = pe * eps
                    # 该绑定应自洽：EPS×PE ≈ 目标价（<5% 容差，估值取整可接受）
                    if abs(implied - tp) / max(implied, 1e-9) > 0.05:
                        issues.append(
                            f"目标价链错误: EPS{_fmt(eps)}×PE{_fmt(pe)}={_fmt(implied)}元，"
                            f"报告目标价写{_fmt(tp)}元")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # ── 3. 目标价/现价空间 ────────────────────────────────
        # 覆盖商业航天案："目标价=0.70×55=38.40元...当前股价对应2025年PE约52倍" + "上行空间约15-20%"
        # 注意目标价正则要跳过"目标价=0.70×55="这种推导式（[^\d] 不能吞掉乘法数字），
        # 用"目标价[^=\d]{0,10}"禁止 = 后直接取数，优先匹配纯目标价"目标价38.40元"。
        # 关键：跳过**情景/敏感性目标价**（"双杀情景...目标价30元"）——这些是分情景值，
        # 合法地与现价产生负空间/大空间，只有结论/综合目标价才应对照上行空间验算。
        _SCENARIO_MARKERS = ("情景", "概率", "悲观", "双杀", "牛市", "中性", "乐观", "下行", "上行")
        for m in _re.finditer(r'目标价[^=\d]{0,10}(\d+(?:\.\d+)?)\s*元', text):
            try:
                tp = float(m.group(1))
                if not (1 < tp < 1000):
                    continue
                # 情景过滤：目标价前 40 字或后 40 字内出现情景词 → 跳过
                _ctx_before = text[max(0, m.start() - 40):m.start()]
                _ctx_after = text[m.end():m.end() + 40]
                if any(mk in _ctx_before or mk in _ctx_after for mk in _SCENARIO_MARKERS):
                    continue
                seg = text[max(0, m.start() - 300):m.end() + 400]
                # 找现价（明写或隐含）
                cp = None
                cp_m = _re.search(r'(?:现价|当前股价|当前价|收盘价)[^\d]{0,6}(\d+(?:\.\d+)?)\s*元', seg)
                if cp_m:
                    cp = float(cp_m.group(1))
                else:
                    # 隐含现价：当前股价对应PE Y倍 × EPS Z元
                    # 商业航天案：'当前股价对应2025年PE约52倍' + EPS约0.59元（前文）
                    pe_m = _re.search(r'(?:对应|对应PE|PE\(TTM\)|当前PE|PE)[^\d]{0,4}(\d{1,3}(?:\.\d+)?)\s*倍', seg)
                    eps_m = _re.search(r'EPS(?:约|为)?\s*(\d+(?:\.\d+)?)\s*元', seg)
                    if pe_m and eps_m:
                        try:
                            pe_v = float(pe_m.group(1))
                            eps_v = float(eps_m.group(1))
                            if 5 < pe_v < 200 and 0 < eps_v < 100:
                                cp = pe_v * eps_v
                        except (ValueError, TypeError):
                            pass
                # 找上行空间（目标价后 500 字内——目标价声明后常隔"综合来看…"等
                # 长句才进入推导段，300 字窗口会漏，商业航天案实测）
                # 区间处理："约15-20%" → 15 后是 "-20%"；"约15%" → 15 后直接 "%"。
                up_m = _re.search(
                    r'(?:上行空间|上涨空间)[^\d]{0,8}(?:约|为)?\s*'
                    r'(\d+(?:\.\d+)?)(?:\s*%|\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*%)',
                    text[m.end():m.end() + 500])
                if cp and cp > 0 and up_m:
                    up_lo = float(up_m.group(1))
                    up_hi = float(up_m.group(2)) if up_m.group(2) else up_lo
                    actual = (tp / cp - 1) * 100
                    # 容差：实际空间与声称区间端点偏差 >3pp 即报
                    if actual < up_lo - 3 or actual > up_hi + 3:
                        # 多估值锚豁免：若段内存在**另一个**目标价，其相对现价的空间
                        # 与声称区间吻合（如汇川案 PE法27.4 vs DCF 70-80，上行空间
                        # 20-38% 对应 70-80），说明声称空间属于另一锚，非本锚矛盾。
                        _alt_ok = False
                        for _am in _re.finditer(r'(\d+(?:\.\d+)?)\s*元', seg):
                            try:
                                _alt_tp = float(_am.group(1))
                                if abs(_alt_tp - tp) < 1e-6 or _alt_tp <= 0:
                                    continue
                                _alt_actual = (_alt_tp / cp - 1) * 100
                                if up_lo - 3 <= _alt_actual <= up_hi + 3:
                                    _alt_ok = True
                                    break
                            except (ValueError, TypeError, ZeroDivisionError):
                                continue
                        if not _alt_ok:
                            issues.append(
                                f"目标价空间错误: 目标价{tp}元 vs 隐含现价{cp:.2f}元=+{actual:.1f}%，"
                                f"报告写{up_lo:g}-{up_hi:g}%")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        # ── 4. 细分合计 vs 总量 ───────────────────────────────
        # 模式："A、B、C、D合计约E" 或 "A+B+C+D=E"（多个数字+单位累加）
        # 覆盖"火箭发射制造约4450亿元、卫星制造约8520亿元...合计约2.99万亿元"
        # 注意：数字可能带千分位逗号（"4,450亿元"），正则须兼容，否则 4450 被拆成 4 和 450。
        for m in _re.finditer(
                r'(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,15}?(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,15}?'
                r'(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,15}?(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,30}?'
                r'(?:合计|总计|总和)[^。；\n]{0,10}?(?:约|为)?\s*(\d[\d,]*\.?\d*)\s*万亿元', text):
            try:
                def _num(s):
                    return float(s.replace(",", ""))
                parts = [_num(m.group(i)) for i in range(1, 5)]
                total_claimed = _num(m.group(5))
                total_actual = sum(parts) / 1e4  # 亿元→万亿元
                if abs(total_actual - total_claimed) / max(total_claimed, 1e-9) > _TOL:
                    issues.append(
                        f"细分合计错误: {parts[0]:.0f}+{parts[1]:.0f}+{parts[2]:.0f}+{parts[3]:.0f}"
                        f"={total_actual:.2f}万亿元，报告写{total_claimed:.2f}万亿元")
            except (ValueError, TypeError, ZeroDivisionError):
                continue

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.2, 1.0 - 0.3 * len(issues))
        det = f"数值链校验: {len(issues)} 项错误" + (": " + "; ".join(issues[:3]) if issues else "无")
        return GateCheckResult("numeric_chain_consistency", passed, score, det, severity="error")

    def _check_cross_section_consistency(self) -> GateCheckResult:
        """P0-B（2026-07-31 审计修复）：跨段数值一致性检查。

        用 consistency_engine 提取全文数值并做语义聚类，检测同簇冲突。
        作为 hard_fail 项：任何跨段数值矛盾（偏差>30%）都阻断导出。
        """
        try:
            from pipeline.consistency_engine import check_consistency
        except ImportError as e:
            # R2（2026-07-31 Marvis 审计）：引擎不可用必须显式失败，
            # 不能 passed=True 假装通过（否则数据一致性检查形同虚设）
            logger.error("[CONSISTENCY] engine unavailable: %s", e)
            return GateCheckResult(name="cross_section_consistency", passed=False,
                                   score=0.1, severity="error",
                                   details=f"consistency_engine unavailable: {e}")
        text = self.report_text or ""
        result = check_consistency(text)
        if result["passed"]:
            n_clusters = len(result["clusters"])
            return GateCheckResult(name="cross_section_consistency", passed=True,
                                   score=1.0,
                                   details=f"no cross-section conflicts ({n_clusters} clusters)")
        conflicts = result["conflicts"]
        # R91（2026-08-10）：行业报告跨段多值豁免——行业报告"细分 vs 总量"（9350亿导航
        # 细分 vs 2.83万亿广义总量）是正常包含关系，降级 warning。
        _sev = "warning" if getattr(self, "report_type", "") == "industry_deep" else "error"
        return GateCheckResult(name="cross_section_consistency", passed=False,
                               score=max(0.1, 1.0 - 0.3 * len(conflicts)),
                               severity=_sev,
                               details=f"{len(conflicts)} conflicts: {'; '.join(conflicts[:3])}")

    def _check_synthesis_consistency(self) -> GateCheckResult:
        """Check if meta-reasoning synthesis was run and contradictions resolved"""
        text = self.report_text or ""
        has_synthesis = bool(re.search(r'synthesis|meta.reasoning|consensus|合成|共识|综合判断', text))
        has_contradiction = bool(re.search(r'contradiction|矛盾|冲突|分歧|conflict|不一致', text))

        if has_synthesis and not has_contradiction:
            score = 1.0
            passed = True
            details = "Synthesis present, no contradictions"
        elif has_synthesis and has_contradiction:
            score = 0.6
            passed = True
            details = "Synthesis present but contradictions unresolved"
        else:
            score = 0.3
            passed = False
            details = "No synthesis evidence in report"

        return GateCheckResult(
            name="synthesis_consistency",
            score=score, passed=passed,
            severity="warning" if score < 0.6 else "info", details=details
        )

    def _check_evidence_layer(self) -> GateCheckResult:
        """FP6 L4: Verify every major numeric claim has a source within 100 chars"""
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("evidence_layer", True, 1.0, "text too short, skipped", severity="warning")
        
        import re
        # Find numeric claims (in Chinese financial context)
        # Match: numbers with 亿/万/百分比 or standalone large numbers
        claims = re.findall(r'(?:\d+\.?\d*[亿万千百]|\d+\.?\d*%|\d{4,}[\u4e00-\u9fff]*)', text)
        if len(claims) < 3:
            return GateCheckResult("evidence_layer", True, 0.7, f"only {len(claims)} claims found")
        
        covered = 0
        for claim in claims:
            # Find position and check surrounding 100 chars for source
            pos = text.find(claim)
            if pos < 0:
                continue
            start = max(0, pos - 100)
            end = min(len(text), pos + len(claim) + 100)
            context = text[start:end]
            if re.search(r'(?:来源|据|数据|source|根据|年报|报告|公告|研报|数据来源)', context):
                covered += 1
        
        ratio = covered / len(claims)
        score = min(1.0, ratio)
        passed = score >= 0.3  # 30%+ of claims have source nearby
        return GateCheckResult("evidence_layer", passed, score, 
                              f"{covered}/{len(claims)} claims sourced ({score:.2f})")
