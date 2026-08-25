"""IronGate 检查 Mixin — analysis 类检查。

R61（2026-08-03 迁移）：由 scripts/migrate_iron_gate.py 自动生成。
方法原样迁移自 pipeline/iron_gate.py，签名不变，IronGate 继承后行为零变化。
"""

import json
import os
import re

from pipeline.checks.base import GateCheckResult


class AnalysisChecksMixin:
    """analysis 类检查方法。"""

    def _check_sac_coverage(self) -> GateCheckResult:
        try:
            dim_keywords = self.sac.get_dimension_keywords()
            if not dim_keywords:
                return GateCheckResult(name="SAC维度覆盖", passed=False, score=0.0, details="SAC维度未加载")
            # R6（2026-08-01 圆桌升级）：SAC 维度覆盖从"整体百分比阈值"改为
            # "必需维度缺一即阻断"。此前 18 维缺 3 维（83% 覆盖）仍能通过 70% 阈值，
            # 导致 core_disagreement / elasticity_analysis / capital_flow 等
            # 必需维度整段缺失的报告照样出厂 —— 这是"发散根因第3层"。
            # 现在：required_dimensions 中任一维度关键词全缺失 → error 阻断。
            required_ids = set()
            try:
                sac_data = self.sac._data or {}
                for dim in sac_data.get("required_dimensions", []):
                    if isinstance(dim, dict) and dim.get("id"):
                        required_ids.add(dim["id"])
            except Exception:
                pass
            covered = 0
            total = len(dim_keywords)
            missing = []
            missing_required = []
            for dim, keywords in dim_keywords.items():
                if any(kw in self.report_text for kw in keywords):
                    covered += 1
                else:
                    missing.append(dim)
                    if dim in required_ids:
                        missing_required.append(dim)
            ratio = covered / max(total, 1)
            # 必需维度全部覆盖 + 整体覆盖率达到阈值才算过
            _sac_threshold = self._get_threshold("sac_coverage", 0.7)
            required_ok = len(missing_required) == 0
            ratio_ok = ratio >= _sac_threshold
            # 2026-08-01 修订：非上市/IPO申报企业部分 PE/VC 维度（创始人质押/
            # 烧钱率/down round）在招股书中天然无数据。若整体覆盖率高（≥85%）
            # 且仅缺 ≤2 个必需维度，且报告声明了数据缺口，则豁免（透明声明原则）。
            # 防止逼 LLM 编造私有市场数据（违反 FP2）。
            _high_coverage = ratio >= 0.80
            _small_gap = len(missing_required) <= 2
            _declared = bool(
                re.search(r"(数据有限|数据不足|待尽调|待核实|无法评估|信息缺口|数据缺失|无公开数据)", self.report_text)
            )
            # 2026-08-05 PE/VC 维度豁免通道：非上市企业 PE/VC 类维度天然缺数据，
            # 若缺失的 required 维度全部属于 PE/VC 类且已声明数据缺口，则不限数量直接豁免
            PE_VC_DIM_IDS = {
                "deal_win_analysis",
                "reference_class_forecast",
                "founder_risk_signals",
                "milestone_runway_map",
                "exit_cycle_analysis",
                "exit_analysis",
            }
            _all_pevc = bool(missing_required) and all(d in PE_VC_DIM_IDS for d in missing_required)
            if _all_pevc and _declared:
                required_ok = True
                _pevc_exempt = True
            elif _high_coverage and _small_gap and _declared:
                required_ok = True
                _pevc_exempt = False
            else:
                _pevc_exempt = False
            passed = required_ok and ratio_ok
            detail = "覆盖: %d/%d (%.0f%%)" % (covered, total, ratio * 100)
            if missing_required:
                # R12（2026-08-01 全量优化）：完整维度名进 feedback（不再截断到 10 字符），
                # 让写循环能精确定位要补齐的 SAC 维度。
                detail += " [必需维度缺失=%s]" % ", ".join(str(m)[:40] for m in missing_required[:8])
            if missing:
                detail += " 缺失: %s" % ", ".join(str(m)[:10] for m in missing[:3])
            if _pevc_exempt:
                detail += " (PE/VC维度豁免,已声明缺口)"
            elif _high_coverage and _small_gap and _declared:
                detail += " (已声明数据缺口,豁免)"
            return GateCheckResult(name="SAC维度覆盖", passed=passed, score=ratio, details=detail, severity="error")
        except Exception as e:
            return GateCheckResult(name="SAC维度覆盖", passed=False, score=0.0, details="失败: %s" % str(e)[:50])

    def _check_chart_density(self) -> GateCheckResult:
        charts = self._count_charts()
        tables = self._count_tables()
        min_t = 2 if self.report_type in ("industry_deep", "industry") else 3
        mc = self.min_charts
        # 2026-08-05 图表空产出阻断：L1 降级场景下区分"声明缺失"与"静默缺失"
        if self._allow_placeholder_degradation:
            if charts == 0:
                # 从 context 读取 chart_failures（chart_pipeline 写入）
                chart_failures = getattr(self, "context", {}) or {}
                cf_list = chart_failures.get("chart_failures", []) if isinstance(chart_failures, dict) else []
                _declared = bool(
                    re.search(
                        r"(数据有限|数据不足|待尽调|待核实|无法评估|信息缺口|数据缺失|无公开数据)", self.report_text
                    )
                )
                if not cf_list and not _declared:
                    # 静默缺失：管线未记录失败原因，报告也未声明缺口 → 阻断
                    return GateCheckResult(
                        name="图表密度",
                        passed=False,
                        score=0.0,
                        details="图表: 0/%d — 静默缺失（无chart_failures记录且未声明数据缺口）" % mc,
                        severity="error",
                    )
                # 声明缺失或有失败记录 → 保持原有豁免
                passed = tables >= min_t
            else:
                passed = tables >= min_t
        else:
            passed = charts >= mc and tables >= min_t
        score = min(charts / max(mc, 1), 1.0) * 0.5 + min(tables / max(min_t, 1), 1.0) * 0.5
        return GateCheckResult(
            name="图表密度",
            passed=passed,
            score=score,
            details="图表: %d/%d 表格: %d/%d%s"
            % (
                charts,
                mc,
                tables,
                min_t,
                " (L1 degradation: charts not required)" if self._allow_placeholder_degradation else "",
            ),
        )

    def _check_chart_completeness(self) -> GateCheckResult:
        """图表完整性：报告必须嵌入 SAC 声明的每张图（2026-08-01 新增）。

        对标投行标准：配置声明 8 张图，报告就必须嵌入 8 张对应的
        [CHART:fig_xxx] 或 ![](chart:fig_xxx)。缺一张 → 失败。
        防 LLM 只写文字不嵌图、或生成失败的图被静默忽略。
        """
        import re

        text = self.report_text or ""
        # 提取报告中嵌入的图 id
        embedded = set()
        # 格式1: [CHART:fig_id, title]
        for m in re.finditer(r"\[CHART:\s*([A-Za-z0-9_\-]+)", text):
            embedded.add(m.group(1))
        # 格式2: ![](chart:fig_id)
        for m in re.finditer(r"!\[[^\]]*\]\(chart:([A-Za-z0-9_\-]+)", text):
            embedded.add(m.group(1))
        # 格式3: ![](fig_id.png) 或任何图片路径含 fig_id
        for m in re.finditer(r"!\[[^\]]*\]\([^)]*(fig_[A-Za-z0-9_\-]+)[^)]*\)", text):
            embedded.add(m.group(1))
        # 格式4（2026-08-01 第三轮修复）: 装配器实际输出 ![cid](charts\cid.png)
        # 兼容任意图片路径：取文件名（去扩展名）与 SAC id 做集合比对
        for m in re.finditer(r"!\[[^\]]*\]\([^)]*?([A-Za-z0-9_\-]+)\.(?:png|jpg|jpeg|svg|webp)[^)]*\)", text):
            embedded.add(m.group(1))
        # 格式5: 表格/正文中的「图表N：xxx（cid）」占位引用（LLM 常写这种）
        for m in re.finditer(r"图表\s*\d*[：:]\s*[^（(]*[（(]([A-Za-z0-9_\-]+)[)）]", text):
            embedded.add(m.group(1))

        # SAC 声明的图
        try:
            # R73（2026-08-05）：chart_assembler 实际生成图优先于 SAC 声明。
            # 数据不足时 chart_pipeline 跳过部分图（如 capital_flow），
            # 以实际生成图集合为检查基准，避免"SAC 声明 21 张但只生成 16 张"被误判为致命失败。
            sac_ids = (
                set(self._chart_ids) if self._chart_ids else {c["id"] for c in self.sac.get_chart_config()["charts"]}
            )
        except Exception:
            return GateCheckResult("chart_completeness", False, 0.0, "无法获取 SAC 图表声明")
        if not sac_ids:
            return GateCheckResult("chart_completeness", True, 1.0, "SAC 无图表声明，跳过")

        missing = sac_ids - embedded
        if not missing:
            return GateCheckResult("chart_completeness", True, 1.0, f"已嵌入全部 {len(sac_ids)} 张图")
        # 部分缺失：按缺失比例扣分
        ratio = len(embedded & sac_ids) / len(sac_ids)
        # 降级感知（2026-08-01 修复）：L1+ 数据不足时允许缺图（FP7b），
        # 不硬阻断，score 照常扣分由整体阈值把关。避免数据缺时报告卡死。
        if self._allow_placeholder_degradation:
            return GateCheckResult(
                "chart_completeness",
                True,
                ratio,
                f"图嵌入: {len(embedded & sac_ids)}/{len(sac_ids)}"
                f" (L1降级: 允许缺图, 缺失: {','.join(sorted(missing)[:3])})",
            )
        return GateCheckResult(
            "chart_completeness",
            False,
            ratio,
            f"图嵌入: {len(embedded & sac_ids)}/{len(sac_ids)} 缺失: {','.join(sorted(missing)[:5])}",
        )

    def _check_global_perspective(self) -> GateCheckResult:
        """全球视野检查（2026-08-01 新增，对标顶级投行全球估值锚定）。

        所有报告类型必须包含全球视角：全球市场/全球对标/海外收入/地缘风险
        至少覆盖一类。缺失 → warning（非上市数据有限可豁免）。
        """
        import re

        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("global_perspective", True, 1.0, "报告过短，跳过")
        # 全球视角关键词：全球/海外/国际/跨境/北美/欧洲/亚太/地缘/汇率
        global_kw = re.compile(
            r"(全球|海外|国际|跨境|北美|欧洲|亚太|东南亚|地缘|汇率|foreign|global|overseas|export)", re.I
        )
        hits = global_kw.findall(text)
        # 去重统计覆盖的类别
        categories = set()
        if re.search(r"全球[^。]{0,10}(市场|规模|对标|竞争)", text):
            categories.add("全球市场/对标")
        if re.search(r"海外[^。]{0,10}(收入|占比|市场|扩张|出海)", text):
            categories.add("海外收入/出海")
        if re.search(r"地缘|中美|出口管制|关税|供应链脱钩|汇率", text):
            categories.add("地缘/汇率风险")
        if len(categories) >= 1:
            return GateCheckResult(
                "global_perspective", True, min(1.0, len(categories) / 3), f"全球视角覆盖: {'/'.join(categories)}"
            )
        return GateCheckResult(
            "global_perspective",
            False,
            0.0,
            "缺乏全球视野：未覆盖全球市场/海外收入/地缘风险任一维度",
            severity="warning",
        )

    def _check_bold_call_consistency(self) -> GateCheckResult:
        """R79 P0-2：Bold Call 一致性检查——单一事实源。

        油位报告圆桌评审：Bold Call 全文 4 处定义不一致（时间窗口/核心变量/增速全对不上）。
        分段并行生成的产物。检查：提取全文所有 Bold Call 表述，比对时间窗口与增速，
        不一致 → error（说明未用开头定义的单一事实源）。
        """
        import re

        text = self.report_text or ""
        if not text:
            return GateCheckResult("bold_call_consistency", True, 1.0, "无文本")
        # 提取所有 Bold Call 相关表述
        bc_blocks = re.findall(r"Bold Call[^。\n]{0,200}", text)
        if len(bc_blocks) < 2:
            return GateCheckResult("bold_call_consistency", True, 1.0, "Bold Call 定义单一")

        # 提取时间窗口
        time_windows = set()
        for b in bc_blocks:
            m = re.search(r"(20\d{2}Q[1-4])\s*[-至]\s*(20\d{2}Q[1-4])", b)
            if m:
                time_windows.add(f"{m.group(1)}-{m.group(2)}")
            else:
                m2 = re.search(r"(20\d{2}Q[1-4])", b)
                if m2:
                    time_windows.add(m2.group(1))
        # 提取增速
        growths = set()
        for b in bc_blocks:
            m = re.search(r"(\d{1,2})[-~至](\d{1,2})%", b)
            if m:
                growths.add(f"{m.group(1)}-{m.group(2)}%")

        issues = []
        if len(time_windows) > 1:
            issues.append(f"时间窗口不一致: {sorted(time_windows)}")
        if len(growths) > 1:
            issues.append(f"增速不一致: {sorted(growths)}")

        if issues:
            return GateCheckResult(
                "bold_call_consistency",
                False,
                0.3,
                f"Bold Call 不一致(P1): {'; '.join(issues)}——必须全文引用开头单一定义",
                severity="error",
            )
        return GateCheckResult("bold_call_consistency", True, 1.0, "Bold Call 一致")

    def _load_market_anchors(self) -> dict:
        """R85（2026-08-06）：加载市场规模外部权威锚点。

        优先从环境变量 ENRICH_ANCHOR_FILE 指定的 enrich JSON 读取；
        glob 兜底**必须标的匹配**：候选文件的顶层 asset 字段或文件名
        需与 self.asset 匹配——P3-audit 2026-08-24 修复跨标的污染：
        原实现按 mtime 取最近任意 *_enrich*.json，A 标的报告会被
        B 标的（如油位传感器）的权威值误判口径冲突。
        返回 {"全球市场规模": {"unit": "亿美元", "values": {year: value}}, ...}；
        无可用锚点返回 {}（不阻断检查）。
        """
        import glob

        cands = []
        env_path = os.environ.get("ENRICH_ANCHOR_FILE", "")
        if env_path and os.path.exists(env_path):
            cands.append((env_path, True))  # 显式指定 = 无条件信任
        _asset = (getattr(self, "asset", "") or "").strip()
        if _asset:
            _bases = [os.getcwd()]
            _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if _root not in _bases:
                _bases.append(_root)
            for _b in _bases:
                for _sub in ("data", "output"):
                    _pat = os.path.join(_b, _sub, "*_enrich*.json")
                    try:
                        _ms = sorted(glob.glob(_pat), key=os.path.getmtime, reverse=True)
                        cands.extend((_p, False) for _p in _ms[:3])
                    except Exception:
                        pass

        def _asset_match(path_or_str: str, payload_asset: str = "") -> bool:
            """文件名或 JSON 顶层 asset 字段与当前标的双向子串匹配。"""
            a, b = _asset, (payload_asset or "").strip()
            if not a:
                return False
            hay = path_or_str.replace("\\", "/").lower()
            if a.lower() in hay:
                return True
            return bool(b) and (a in b or b in a)

        for p, trusted in cands:
            try:
                with open(p, encoding="utf-8") as fh:
                    enrich = json.load(fh)
                if not trusted and not _asset_match(
                    os.path.basename(p), str(enrich.get("asset", "")) if isinstance(enrich, dict) else ""
                ):
                    continue  # 跨标的 enrich 文件 → 不作锚点
                items = enrich.get("items", []) if isinstance(enrich, dict) else []
                out = {}
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    key = it.get("key") or it.get("field") or ""
                    val = it.get("data") if it.get("data") is not None else it.get("value")
                    _unit = it.get("unit", "")
                    if key == "fig_market_size_global" and isinstance(val, dict):
                        out["全球市场规模"] = {
                            "unit": _unit or "亿美元",
                            "values": {str(k): v for k, v in val.items() if isinstance(v, (int, float))},
                        }
                    elif key == "fig_market_size_china" and isinstance(val, dict):
                        out["中国市场规模"] = {
                            "unit": _unit or "亿元",
                            "values": {str(k): v for k, v in val.items() if isinstance(v, (int, float))},
                        }
                if out:
                    return out
            except Exception:
                continue
        return {}

    def _check_indicator_consistency(self) -> GateCheckResult:
        """R82 P1：关键指标跨章节一致性——渗透率/份额/增速/替换需求多值冲突拦截。

        v9 事故：渗透率40%vs50%、份额50%-73%、替换需求差2倍。
        用 data_single_source 扫描全文，同一指标多值偏差>20% → error。
        """
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("indicator_consistency", True, 1.0, "报告过短")
        try:
            from core.data_single_source import validate_indicators

            issues = validate_indicators(text)
        except Exception:
            return GateCheckResult("indicator_consistency", True, 0.8, "校验器不可用")
        if issues:
            # R91（2026-08-10）：行业报告指标多值豁免——行业报告渗透率/份额常同时
            # 出现"当前值 vs 天花板""细分 vs 总量"，是正常分析结构，降级 warning。
            _sev = "warning" if getattr(self, "report_type", "") == "industry_deep" else "error"
            return GateCheckResult(
                "indicator_consistency",
                False,
                max(0.1, 0.6 - len(issues) * 0.1),
                f"关键指标冲突(P1): {'; '.join(issues)}——须统一到单一事实源",
                severity=_sev,
            )
        return GateCheckResult("indicator_consistency", True, 1.0, "关键指标一致")

    def _check_market_size_consistency(self) -> GateCheckResult:
        """R79 P0-3：市场规模/增速口径统一检查。

        油位报告圆桌评审：全球 32.5 vs 46 亿美元、中国 58.6 vs 166 亿元双口径冲突，
        consistency_engine 语义聚类未捕获（0 clusters）。原因：同一指标出现在不同
        上下文（汽车电子窄口径 vs 工业全口径），语义被当不同簇。
        本检查：提取全文"全球/中国 + 市场规模 + 数字 + 单位"，同一指标多值偏差>20% → error。
        """
        import re

        text = self.report_text or ""
        if not text:
            return GateCheckResult("market_size_consistency", True, 1.0, "无文本")

        # 提取 "全球/中国 ... 亿美元/亿元" 模式
        # R81 修复（2026-08-06）：带年份的为时间序列值（"2024年46亿美元/2030年65亿美元"），
        # 按 (指标, 年份) 分组——同一年份多值才判口径冲突（"2024年32.5 vs 46亿美元"）；
        # 无年份限定的是主口径锚定值（"全球市场规模50亿美元(E)"），单独成组比对。
        # 派生口径（对应/约合/隐含/折合/SAM）与区间上界（约1.2-2.3亿元）不计入。
        issues = []
        # 带年份值： (label, year) -> [(num, unit)]
        _yearly: dict[tuple, list] = {}
        # 无年份主口径： label -> [(num, unit)]
        _anchor: dict[str, list] = {}
        _re_year = re.compile(
            r"(全球|中国)(?![。；\n])(?:[^。；\n]{0,30}?)(20\d{2})\s*[年Ee]?\s*(\d+(?:\.\d+)?)\s*(亿美元|亿元)"
        )
        _re_anchor = re.compile(r"(全球|中国)(?:(?!20\d{2}\s*[年Ee])[^。；\n]){0,30}?(\d+(?:\.\d+)?)\s*(亿美元|亿元)")
        for _m in _re_year.finditer(text):
            _label = "全球市场规模" if _m.group(1) == "全球" else "中国市场规模"
            _key = (_label, _m.group(2))
            _yearly.setdefault(_key, []).append((float(_m.group(3)), _m.group(4)))
        for _m in _re_anchor.finditer(text):
            _before = text[max(0, _m.start() - 15) : _m.start()]
            if re.search(r"对应|约合|隐含|折合|SAM|按", _before):
                continue
            # R86（2026-08-06）：广义液位/仪表口径排除——"广义液位市场2024年全球规模约120亿美元"
            # 中"全球规模120亿美元"属液位行业全口径，非油位传感器口径，不得与权威油位值(46亿美元)比对。
            # 扩大 before 窗口至 45 字并检查匹配文本内部，防止广义口径混入油位主口径簇。
            _before45 = text[max(0, _m.start() - 45) : _m.start()]
            _span = _m.group(0)
            if re.search(r"广义|液位仪表|液位市场|液位类|含液位|含油位|整体液位", _before45 + _span):
                continue
            if re.search(r"约\s*\d+\.?\d*\s*[-~～至]\s*$", _before):
                continue
            # R84（2026-08-06）：句内过滤强化——派生/区间标记可能出现在匹配文本内部
            # （"中国SAM合计约9-17亿元/年"的 SAM 字样与区间上界 17 均不在 before15 窗口内），
            # 仅看匹配前 15 字会漏过滤，导致 SAM 区间上界误入主口径簇。
            _span = _m.group(0)
            if re.search(r"SAM|对应|约合|隐含|折合|占比|份额", _span):
                continue
            # R90（2026-08-06）：区间残值过滤——"虽小（1-5亿元/年）"中 5 被误抽为主口径，
            # 但 5 是区间上界。匹配数字前 20 字内存在 \d+[-~～] 区间模式则跳过。
            _num_pos = _m.start(2)
            _before20 = text[max(0, _num_pos - 20) : _num_pos]
            if re.search(r"\d+\s*[-~～]\s*$", _before20):
                continue
            # 区间上界判定：数字前 30 字内以 数字-数字 / 数字~数字 / 数字至数字 结尾 → 上界值，跳过
            _before30 = text[max(0, _m.start() - 30) : _m.start()]
            if re.search(r"\d+\.?\d*\s*(?:[-~～至]|至)\s*\d+\.?\d*\s*$", _before30):
                continue
            # R84：同一句内"中国+全球"并存时按数值前近邻区域词判定归属，防止
            # "中国占全球46亿美元规模的比例"这类句式中全球值被误计入中国口径簇。
            _num_pos = _m.start(2)
            _near = text[max(0, _num_pos - 8) : _num_pos]
            _lead = _m.group(1)
            if _lead == "中国" and re.search(r"全球", _near):
                continue
            if _lead == "全球" and re.search(r"中国|国内", _near):
                continue
            # R82: 过滤 Gate 反馈污染——LLM 可能将 "口径冲突说明：中国市场规模存在多口径冲突[1.0,...]亿元"
            # 这种自引用披露文本嵌入正文，导致递归检测失败。检查匹配所在句子是否含自引用关键词。
            _sent_start = text.rfind("。", 0, _m.start())
            _sent_end = text.find("。", _m.end())
            if _sent_start == -1:
                _sent_start = 0
            else:
                _sent_start += 1
            if _sent_end == -1:
                _sent_end = len(text)
            _sentence = text[_sent_start:_sent_end]
            if re.search(r"口径冲突|多口径冲突|口径一致性说明|偏差[>＞]20%|口径说明|口径说明", _sentence):
                continue
            _label = "全球市场规模" if _m.group(1) == "全球" else "中国市场规模"
            # P1-3（2026-08-07）：年份窗口归组——"全球65亿美元（2030年）"、
            # "以2024年全球46亿美元为锚点"、"中国约200亿元人民币（2030年预估）"等
            # 句式年份在数字前/后而非"全球|中国"与数字之间，_re_year 捕获不到，
            # 若并入无年份主口径组会与 2024 年值误判跨年冲突。数字前 45 字/后 35 字
            # 窗口内出现 20xx 年份时，归入带年份组 _yearly（该年独立成组，不参与
            # 无年份主口径比对，也不触发跨年冲突）。
            _num_pos = _m.start(2)
            _win_before = text[max(0, _num_pos - 45) : _num_pos]
            _win_after = text[_m.end() : _m.end() + 35]
            _yr = re.search(r"(20\d{2})\s*[年Ee]?", _win_before) or re.search(r"(20\d{2})\s*[年Ee]?", _win_after)
            if _yr:
                _yearly.setdefault((_label, _yr.group(1)), []).append((float(_m.group(2)), _m.group(3)))
                continue
            # P1-3（2026-08-07）：汇率派生口径过滤——"按2024年人民币兑美元平均汇率7.1
            # 计算，全球市场规模约326.6亿元人民币"中 326.6 亿元是 46 亿美元按汇率折算的
            # 派生值，不是独立主口径。数字前 45 字窗口出现"汇率|折算|按…计算"则跳过。
            if re.search(r"汇率|折算|平均汇率", _win_before) or re.search(r"按[^。；\n]{0,15}?计算", _win_before):
                continue
            _anchor.setdefault(_label, []).append((float(_m.group(2)), _m.group(3)))
        for _key, _nums in _yearly.items():
            if len(_nums) < 2:
                continue
            # P1-3（2026-08-07）：年内币种归一化。
            # 同一年可能存在 46（亿美元）与 326（亿元）两个值，它们分属不同币种，
            # 并非真正口径冲突。归一化后再比对：如存在美元和人民币混合，统一按
            # 1 USD ≈ 7 CNY 换算到同一币种再进行偏差检测。
            _usd_vals = [n for n, u in _nums if "美元" in u]
            _cny_vals = [n for n, u in _nums if "元" in u and "美元" not in u]
            if _usd_vals and _cny_vals:
                # 混合币种：将人民币值按 1USD=7CNY 换算为美元值，统一比对
                _vals = _usd_vals + [v / 7.0 for v in _cny_vals]
            else:
                _vals = [n for n, _u in _nums]
            _mx, _mn = max(_vals), min(_vals)
            if _mn > 0 and (_mx - _mn) / _mn > 0.20:
                issues.append(f"{_key[0]}({_key[1]}年)多口径冲突: {_vals}（偏差>20%）")
        for _label, _nums in _anchor.items():
            if len(_nums) < 2:
                continue
            # P1-3（2026-08-07）：币种归一化（同 _yearly 分支逻辑）
            _usd_vals = [n for n, u in _nums if "美元" in u]
            _cny_vals = [n for n, u in _nums if "元" in u and "美元" not in u]
            if _usd_vals and _cny_vals:
                _vals = _usd_vals + [v / 7.0 for v in _cny_vals]
            else:
                _vals = [n for n, _u in _nums]
            _mx, _mn = max(_vals), min(_vals)
            if _mn > 0 and (_mx - _mn) / _mn > 0.20:
                issues.append(f"{_label}多口径冲突: {_vals}（偏差>20%）")

        # R85（2026-08-06）：外部权威锚点比对——enrich 文件中的市场规模为权威口径。
        # 修复根因：LLM 自创"加油站窄口径"（全球18.6亿/中国15.2亿）规避内部多值比对，
        # 与权威值（全球46亿/中国166亿）严重冲突却检测不到（v9 三连败的根因）。
        # R87（2026-08-06）：单位归一化——正文可能出现"46.0亿元"（权威为46亿美元），
        # 数值相同但单位错乱（差7倍）。比对前统一按 1美元=7元 换算，防止漏检单位错乱。
        anchors = self._load_market_anchors()
        if anchors:
            for label, ymap in anchors.items():
                _unit_anchor = ymap.get("unit", "亿美元") if isinstance(ymap, dict) else "亿美元"
                _ymap_vals = ymap.get("values", ymap) if isinstance(ymap, dict) else ymap
                _auth_items = [
                    (str(y), float(v))
                    for y, v in _ymap_vals.items()
                    if str(y).isdigit() and isinstance(v, (int, float))
                ]
                if not _auth_items:
                    continue
                _auth_vals = [v for _, v in _auth_items]

                def _norm(_num, _unit):
                    # 统一到权威单位口径：非权威单位按汇率7换算为权威单位
                    if _unit == _unit_anchor:
                        return _num
                    _u_dollar = ("美元" in _unit) or ("USD" in _unit.upper())
                    _a_dollar = ("美元" in _unit_anchor) or ("USD" in _unit_anchor.upper())
                    if _u_dollar == _a_dollar:
                        # 同为美元或同为人民币口径（亿元/亿元人民币），数值直接可比
                        return _num
                    # 口径基准不同：美元→人民币 ×7，人民币→美元 ÷7
                    return _num * 7.0 if _u_dollar else _num / 7.0

                # 1) 带年份值比对
                for year, av in _auth_items:
                    if (label, year) in _yearly:
                        for bv, bunit in _yearly[(label, year)]:
                            _bvn = _norm(bv, bunit)
                            _u_dollar = ("美元" in bunit) or ("USD" in bunit.upper())
                            _a_dollar = ("美元" in _unit_anchor) or ("USD" in _unit_anchor.upper())
                            if av > 0 and abs(_bvn - av) / av > 0.20:
                                _tag = f"（单位{bunit}≠权威{_unit_anchor}）" if _u_dollar != _a_dollar else ""
                                issues.append(
                                    f"{label}({year}年)正文值{bv}{bunit}{_tag}与权威值{av}{_unit_anchor}偏差>20%"
                                    f"（权威口径: {'/'.join(f'{y}={v}' for y, v in _auth_items)}{_unit_anchor}，必须采用权威值）"
                                )
                # 2) 无年份主口径值比对（与最早权威年份值比较，防口径漂移）
                _base = _auth_vals[0]
                for bv, bunit in _anchor.get(label, []):
                    _bvn = _norm(bv, bunit)
                    _u_dollar = ("美元" in bunit) or ("USD" in bunit.upper())
                    _a_dollar = ("美元" in _unit_anchor) or ("USD" in _unit_anchor.upper())
                    if _base > 0 and abs(_bvn - _base) / _base > 0.20:
                        _tag = f"（单位{bunit}≠权威{_unit_anchor}）" if _u_dollar != _a_dollar else ""
                        issues.append(
                            f"{label}正文主口径{bv}{bunit}{_tag}与权威口径{_auth_vals}{_unit_anchor}偏差>20%"
                            f"（权威口径: {'/'.join(f'{y}={v}' for y, v in _auth_items)}{_unit_anchor}，必须采用权威值）"
                        )

        if issues:
            # R91（2026-08-10）：行业报告口径豁免——industry_deep 天然多环节/多口径
            # （全球航天总量 vs 商业航天子集、不同环节PE），口径冲突是正常分析结构。
            # 降级为 warning（不阻断），listed/unlisted/earnings 保持 error 严格性。
            _sev = "warning" if getattr(self, "report_type", "") == "industry_deep" else "error"
            return GateCheckResult(
                "market_size_consistency",
                False,
                0.3,
                f"市场规模口径不一致(P1): {'; '.join(issues)}——须统一口径并显式标注口径差异",
                severity=_sev,
            )
        return GateCheckResult("market_size_consistency", True, 1.0, "市场规模口径一致")

    def _check_geopolitical_depth(self) -> GateCheckResult:
        """中美竞争分析深度检查（R78 全量优化）。

        浅层"提到地缘"不算数——要求报告有具体政策事件（日期/名称）+ 量化影响
        （受益标的/占比/概率/指标）。对标高盛政策时间线、大摩双轨情景。
        """
        import re

        text = self.report_text or ""
        if len(text) < 800:
            return GateCheckResult("geopolitical_depth", True, 1.0, "报告过短，跳过")
        # 1. 有具体事件：日期（年/月/日）+ 政策主体
        has_event = bool(
            re.search(r"(20\d{2}[年\-/]\d{1,2}[月\-/]?\d{0,2}|实体清单|出口管制|关税|制裁|BIS|大基金)", text)
        )
        # 2. 有量化影响：受益/影响 + 数字或概率
        has_impact = bool(re.search(r"(影响|受益|替代|占比|概率|提升|受限|暴露度|自主可控|\d+%|\d+\s*pp)", text))
        # 3. 有传导/应对：国产替代/去风险/应对
        has_response = bool(re.search(r"(国产替代|去风险|自主可控|应对|反制|供应链本土化|信创)", text))
        depth_score = sum([has_event, has_impact, has_response])
        # R78：事件是硬门槛——没有具体政策事件（日期/实体清单/管制）只算浅层。
        # warning 级不硬阻断，但 score 反映深度不足。
        if has_event and depth_score >= 2:
            return GateCheckResult(
                "geopolitical_depth",
                True,
                min(1.0, 0.4 + depth_score * 0.2),
                f"中美竞争分析深度: 事件={has_event} 量化={has_impact} 传导={has_response}",
            )
        return GateCheckResult(
            "geopolitical_depth",
            False,
            0.3,
            f"中美竞争分析浅层: 事件={has_event} 量化={has_impact} 传导={has_response}（需具体政策事件+量化影响+传导路径）",
            severity="warning",
        )

    def _check_financial_statements_coverage(self) -> GateCheckResult:
        """三表引用检查（2026-08-01 新增，对标四大审计标准）。

        报告必须引用财务报表关键数据：利润表（营收/净利）、资产负债表（资产/负债/权益）、
        现金流量表（经营现金流）。缺失维度标注「数据缺口」。

        非上市企业（unlisted）允许缺资产负债表/现金流（数据有限），但必须声明缺口。
        """
        import re

        text = self.report_text or ""
        if not text or len(text) < 40:
            return GateCheckResult("financial_statements", False, 0.0, "报告太短，无法评估财务引用")
        # 利润表：营收/净利
        has_revenue = bool(re.search(r"营收|营业收入|销售额|revenue|收入[：:]\s*[\d.]", text, re.I))
        has_profit = bool(re.search(r"净利|净利润|亏损|盈利|profit|EPS|每股收益", text, re.I))
        # 资产负债表：资产/负债/权益
        has_assets = bool(re.search(r"总资产|资产总额|资产[：:]\s*[\d.]|负债率|资产负债", text))
        has_equity = bool(re.search(r"股东权益|净资产|权益合计|equity", text, re.I))
        # 现金流量表：经营现金流
        has_cashflow = bool(re.search(r"现金流|经营活动.*净额|经营现金流|OCF|烧钱率|货币资金", text, re.I))

        # 得分：利润表核心，资产负债/现金流加分
        present = sum([has_revenue, has_profit, has_assets or has_equity, has_cashflow])
        missing = []
        if not has_revenue:
            missing.append("营收")
        if not has_profit:
            missing.append("净利")
        if not (has_assets or has_equity):
            missing.append("资产负债表")
        if not has_cashflow:
            missing.append("现金流")
        # R45（2026-08-02 P1-1）：行业深度报告无单公司三表——以市场规模/增速/集中度
        # 为主体，强制"营收+净利+资产"会导致结构性误判 FAIL。
        # 行业口径：市场规模 + 增速 + 集中度（至少2项），不要求单公司三表。
        score = present / 4.0
        if self.report_type == "industry_deep":
            has_mkt_size = bool(
                re.search(
                    r"市场规模|市场空间|TAM|销售额\s*[约达为]?[：:]?\s*[\d.]|规模\s*[约达为]?[：:]?\s*[\d.]", text, re.I
                )
            )
            has_growth = bool(re.search(r"增速|增长[率率]|CAGR|年复合|同比[^。]*\d+%", text, re.I))
            has_concentration = bool(re.search(r"集中度|CR3|CR5|CR10|份额|市占率", text, re.I))
            ind_present = sum([has_mkt_size, has_growth, has_concentration])
            ind_passed = ind_present >= 2
            ind_score = ind_present / 3.0
            ind_detail = f"行业口径: 市场规模({has_mkt_size}) 增速({has_growth}) 集中度({has_concentration})"
            if ind_passed:
                return GateCheckResult(
                    "financial_statements",
                    True,
                    max(score, ind_score),
                    ind_detail + "（行业报告以市场数据为主体，通过）",
                    severity="warning",
                )
            return GateCheckResult(
                "financial_statements",
                False,
                ind_score,
                ind_detail + " 行业报告须含市场规模/增速/集中度至少2项",
                severity="error",
            )
        if self.report_type == "unlisted_company":
            passed = has_revenue and has_profit
            severity = "warning"  # 非上市数据有限，缺失降为警告
        else:
            passed = has_revenue and has_profit and (has_assets or has_equity)
            severity = "error"
        detail = (
            f"引用: 营收({has_revenue}) 净利({has_profit}) 资产负债({has_assets or has_equity}) 现金流({has_cashflow})"
        )
        if missing:
            detail += f" 缺口: {','.join(missing)}"
        return GateCheckResult("financial_statements", passed, score, detail, severity=severity)

    def _check_persuasion_architecture(self) -> GateCheckResult:
        has_counter = bool(re.search(r"反对|反方|看空|悲观|担忧|风险|然而|但是|不过", self.report_text))
        has_consensus = bool(re.search(r"市场共识|市场认为|市场预期|普遍认为|一致预期", self.report_text))
        has_sowhat = bool(
            re.search(r"这意味着|这意味着|因此建议|我们的建议|投资启示|投资含义|对投资者", self.report_text)
        )
        has_falsify = bool(
            re.search(r"证伪|如果.*就错了|如果.*判断就错了|如果.*发生.*就|可观察|均值回归", self.report_text)
        )
        has_target = bool(re.search(r"目标价\d+|[买卖增持中]*评级|买入|增持|中性|卖出|持有|推荐", self.report_text))
        # FP7b L1 降级：非上市标的无公开市场一致预期，consensus 表达天然稀缺 → 降级时不硬要求
        if self._allow_placeholder_degradation:
            passed = has_counter and has_target
        else:
            passed = has_counter and has_consensus and has_target
        score = (has_counter + has_consensus + has_sowhat + has_falsify + has_target) / 5.0
        detail = "反方:%s 共识:%s SoWhat:%s 证伪:%s 评级:%s" % (
            "Y" if has_counter else "N",
            "Y" if has_consensus else "N",
            "Y" if has_sowhat else "N",
            "Y" if has_falsify else "N",
            "Y" if has_target else "N",
        )
        return GateCheckResult(name="说服力架构", passed=passed, score=score, details=detail)

    def _check_table_density(self) -> GateCheckResult:
        tables = self._count_tables()
        min_n = {"industry_deep": 3, "listed_company": 3, "unlisted_company": 2, "earnings_notes": 1}
        mc = min_n.get(self.report_type, 3)
        score = min(1.0, tables / max(mc, 1))
        passed = tables >= mc
        return GateCheckResult(
            name="表格密度", passed=passed, score=score, details="表格: %d, 最低要求: %d" % (tables, mc)
        )

    def _check_moat_analysis(self) -> GateCheckResult:
        patterns = {
            "moat_type": bool(re.search(r"护城河|竞争壁垒|竞争优势|进入壁垒", self.report_text)),
            "moat_strength": bool(re.search(r"强[度]|中[等]|弱|评级|评分.*[1-5]", self.report_text)),
            "dupont": bool(re.search(r"杜邦|ROE[分解]|[三层|三层次]分解", self.report_text)),
            "brand": bool(re.search(r"品牌|专利|技术领先|转换成本", self.report_text)),
            "greenwald": bool(re.search(r"格林沃德|供给优势|需求优势|规模经济", self.report_text)),
        }
        pc = sum(1 for v in patterns.values() if v)
        score = pc / max(len(patterns), 1)
        passed = score >= 0.4
        det = "护城河: " + "/".join(k for k, v in patterns.items() if v) + " score=%.2f" % score
        return GateCheckResult(name="护城河分析", passed=passed, score=score, details=det)

    def _check_multi_model(self) -> GateCheckResult:
        models = [
            "霍华德马克斯|二阶思维|周期",
            "索罗斯|反身性|反身",
            "芒格|能力圈|格栅",
            "达摩达兰|估值|DCF",
            "波特五力|五力",
            "SWOT",
            "PEST",
        ]
        found = []
        for m in models:
            if re.search(m, self.report_text):
                found.append(m.split("|")[0])
        score = min(len(found) / 3.0, 1.0)
        passed = len(found) >= 2
        det = "模型: " + ("/".join(found) if found else "无") + " count=%d" % len(found)
        return GateCheckResult(name="多模型验证", passed=passed, score=score, details=det)

    def _check_decision_gate(self) -> GateCheckResult:
        has_gate = bool(re.search(r"决策门|GO[^O]|NO.GO|值得.*分析", self.report_text))
        has_verdict = bool(re.search(r"GO|值得|通过|结论", self.report_text[:1000]))
        passed = has_gate
        score = (has_gate + has_verdict) / 2.0
        return GateCheckResult(
            name="决策门判断", passed=passed, score=score, details="决策门: %s" % ("有" if has_gate else "无")
        )

    def _check_dcf_sensitivity(self) -> "GateCheckResult":
        """检查报告是否包含DCF敏感性分析"""
        # R12（2026-08-01 全量优化）：unlisted（非上市）与 industry 一样豁免 DCF——
        # 非上市公司无公开 DCF 数据，硬要求 DCF 敏感性是检查器误配。
        if self.report_type in ("industry_deep", "industry", "unlisted_company"):
            from pipeline.checks.base import GateCheckResult

            return GateCheckResult(
                name="dcf_sensitivity", passed=True, score=1.0, details="Skipped for industry/unlisted report"
            )

        text = self.report_text if hasattr(self, "report_text") and self.report_text else ""
        from pipeline.checks.base import GateCheckResult

        # 检查DCF敏感性分析的关键模式
        patterns = [
            (r"WACC.*\u6210\u957f\u7387", 0.3),
            (r"\u654f\u611f\u6027\u5206\u6790", 0.4),
            (r"\u4f30\u503c\u77e9\u9635", 0.5),
            (r"WACC.*\u7ec8\u7aef", 0.5),
            (r"\u76c8\u5229\u9884\u6d4b\u8868", 0.3),
            (r"\u7ec8\u7aef\u589e\u957f\u7387", 0.4),
        ]

        score = 0.0
        hits = 0
        for pat, weight in patterns:
            if re.search(pat, text):
                score = max(score, weight)
                hits += 1

        # DCF sensitivity matrix check (WACC rows x growth rate columns)
        matrix_pattern = r"\d+[\.\,]\d+%.{0,20}\d+[\.\,]\d+%.{0,20}\d+[\.\,]\d+%"
        has_matrix = len(re.findall(matrix_pattern, text)) >= 2
        if has_matrix:
            score = max(score, 0.9)

        # FP7b L1 降级：非上市/降级场景 DCF 敏感性属锦上添花（非上市无公开 DCF 数据），
        # 降为 advisory；正常模式保持硬阻断
        # P3-audit 2026-08-24：earnings_notes（业绩快评）以 PE/EPS 快速定价为主，
        # 完整 DCF 敏感性矩阵非常规配置——与 industry/unlisted 豁免同理降为
        # advisory，防类型错配把快评卡死在 0.5 分档（宁德时代 E2E 实测触发）。
        if self.report_type == "earnings_notes":
            return GateCheckResult(
                name="dcf_sensitivity",
                passed=score >= 0.3,
                score=min(score, 1.0),
                details="DCF sensitivity: %.2f (patterns: %d/6, matrix: %s) [advisory]" % (score, hits, has_matrix),
                severity="warning",
            )
        severity = "warning" if self._allow_placeholder_degradation else "error"
        return GateCheckResult(
            name="dcf_sensitivity",
            passed=score >= 0.55,
            score=min(score, 1.0),
            details="DCF sensitivity: %.2f (patterns: %d/6, matrix: %s)" % (score, hits, has_matrix),
            severity=severity,
        )

    def _check_so_what_chain(self) -> "GateCheckResult":
        """增强版：检查报告中So What链的完整性和密度（逐段扫描）"""
        text = self.report_text if hasattr(self, "report_text") and self.report_text else ""
        from pipeline.checks.base import GateCheckResult

        sections = re.split(
            r"(?:^## |^[一二三四五六七八九十百]+[、.．]|^第[一二三四五六七八九十百]+部分)", text, flags=re.MULTILINE
        )
        # 标题切分失败时回退到按段落扫描（兼容 StyleCompiler 编译后的无标题结构）
        if len(sections) <= 1:
            paras = [p for p in text.split("\n\n") if len(p) >= 50]
            if len(paras) >= 3:
                sections = paras
            else:
                return GateCheckResult("so_what_chain", False, 0.3, "Too few sections to check")

        # R12（2026-08-01 全量优化）：排除附录段（图表附录/来源附录/免责声明等非分析段），
        # 否则附录段无推理链会拉低 min_score，导致正文 So What 达标却被误判失败。
        _appendix_marks = ("附录", "数据图表", "数据补充来源", "AGENT_ENRICH", "免责声明", "来源")
        sections = [s for s in sections if not any(m in s[:30] for m in _appendix_marks)]
        if not sections:
            return GateCheckResult("so_what_chain", False, 0.3, "No analyzable sections (all appendix)")

        # R34（2026-08-02）：跳过纯表格/短结论段——表格行（|...|）占比高、
        # 无实质论证链的段（如"关键跟踪指标"表、"风险提示"表）不应计入 min_score。
        # 此前柯力草稿因 2 个表格段 score=0 拉低 min_score → 误判 so_what_chain ERROR。
        def _is_table_section(sec: str) -> bool:
            lines = [l.strip() for l in sec.split("\n") if l.strip()]
            if not lines:
                return False
            table_lines = sum(1 for l in lines if l.startswith("|") and l.endswith("|"))
            # 表格行占比 >60% 或 表格行 >=3 且段内无可论证文本
            ratio = table_lines / len(lines)
            return ratio >= 0.6 or (table_lines >= 3 and len(sec) < 400)

        # R93：纯标题/元信息段（报告标题+日期/分析师），无推理链不计分
        def _is_heading_meta(sec: str) -> bool:
            lines = [l.strip() for l in sec.split("\n") if l.strip()]
            if not lines:
                return True
            _text = "".join(lines)
            # 段内主要是标题行（# 开头）或元信息（日期/分析师/报告级别）
            _heading_ratio = sum(
                1 for l in lines if l.startswith("#") or re.search(r"报告日期|报告级别|分析师|报告类型", l)
            ) / len(lines)
            return _heading_ratio >= 0.5 and len(_text) < 150

        sections = [s for s in sections if not _is_table_section(s)]
        # R93（2026-08-10）：跳过纯标题/元信息段——"# 报告标题 + 报告日期/分析师"这类
        # 开头段无推理链，不应计为 So What 死角段。标题或元信息占比高即跳过。
        sections = [s for s in sections if not _is_heading_meta(s)]
        # R93（2026-08-10）：跳过纯标题/元信息段——"# 报告标题 + 报告日期/分析师"这类
        # 开头段无推理链，不应计为 So What 死角段。标题或元信息占比高即跳过。
        sections = [s for s in sections if not _is_heading_meta(s)]
        if not sections:
            return GateCheckResult("so_what_chain", False, 0.3, "No analyzable sections (all tables)")

        # Reasoning chain markers (数据→分析→判断→行动)
        chain_patterns = [
            r"\u56e0\u6b64",
            r"\u8fd9\u610f\u5473\u7740",
            r"\u6211\u4eec\u5224\u65ad",
            r"\u6211\u4eec\u5efa\u8bae",
            r"\u7efc\u4e0a\u6240\u8ff0",
            r"\u56e0\u6b64\u6211\u4eec\u8ba4\u4e3a",
            r"\u5bfc\u81f4",
            r"\u4ece\u800c",
            r"\u5f71\u54cd",
            r"\u610f\u5473\u7740",
            r"So\s*What",
            r"\u6570\u636e\u8868\u660e",
            r"\u5bf9\u6295\u8d44\u8005\u610f\u5473\u7740",
            r"\u7efc\u5408\u5224\u65ad",
            r"\u6982\u7387\u8bc4\u4f30",
            r"\u8bc1\u4f2a\u6761\u4ef6",
            r"\u53cd\u65b9\u8bba\u8bc1",
            r"\u5224\u65ad[：:]",
            # R93：判断驱动推理链（验证/印证/兑现/传导）
            r"验证",
            r"印证",
            r"兑现",
            r"传导",
            r"行业判断",
            r"判断①",
        ]

        # Score per section
        section_scores = []
        for sec in sections:
            if len(sec) < 50:
                continue
            hits = sum(1 for p in chain_patterns if re.search(p, sec))
            expected = max(2, len(sec) // 300)
            sec_score = min(hits / expected if expected > 0 else 0.3, 1.0)
            section_scores.append(sec_score)

        if not section_scores:
            return GateCheckResult("so_what_chain", False, 0.3, "No analyzable sections")

        avg_score = sum(section_scores) / len(section_scores)
        min_score = min(section_scores)

        # P1-3 修复（2026-08-01 审计）：min_score >= 0.3 约束防止均值掩盖短板，
        # 并将 min_score 纳入 final_score 计算（加权：avg 60% + min 40%）。
        passed = avg_score >= 0.6 and min_score >= 0.3
        final_score = min(avg_score * 0.6 + min_score * 0.4 + (0.1 if avg_score >= 0.7 else 0), 1.0)

        # R77（2026-08-06 P0）：死角段定位——Gate 反馈中携带 min=0 的段标题/首句
        # 让 fail_locator 能精确定位到死角段而非全量重写
        _min_segments = []
        for i, (sec, sc) in enumerate(zip(sections, section_scores)):
            if sc <= 0.0:
                _heading = sec[:80].replace("\n", " ").strip() or f"段{i + 1}"
                _min_segments.append(_heading)
        detail = "So What: %.2f avg/%d sections (min: %.2f)" % (avg_score, len(section_scores), min_score)
        if _min_segments:
            detail += " | 死角段: %s" % "; ".join(_min_segments[:3])
        # FP7b L1 降级：数据受限导致 LLM 推理链密度不足，So What 链降为 advisory（不阻断），
        # 由整体 score 反映质量水平；非降级模式保持硬阻断
        severity = "warning" if self._allow_placeholder_degradation else "error"
        return GateCheckResult("so_what_chain", passed, final_score, detail, severity=severity)

    @staticmethod
    def _content_depth_score(section_text: str) -> float:
        """A-08：评估一段文字的内容深度（0~1）。

        深度标准：
        - 含具体数字/百分比 → +0.2
        - 含因果连接词（因为/由于/驱动/导致/归因于）→ +0.2
        - 含比较级或变化方向（提升/下降/超过/低于/优于）→ +0.2
        - 含条件句（如果/若/假设/在…情况下）→ +0.2
        - 不含重复短语（同一段内同一 8 字片段出现 ≤1 次）→ +0.2
        """
        import re

        score = 0.0
        if re.search(r"\d+\.?\d*\s*(?:%|亿|万|倍|元|pp)", section_text):
            score += 0.2
        if re.search(r"(?:因为|由于|驱动|导致|归因于|来自)", section_text):
            score += 0.2
        if re.search(r"(?:提升|下降|超过|低于|优于|恶化|改善)", section_text):
            score += 0.2
        if re.search(r"(?:如果|若|假设|在.{1,8}情况| scenario)", section_text):
            score += 0.2
        # 重复检测：8 字滑窗去重比
        clean = re.sub(r"\s", "", section_text)
        if len(clean) > 20:
            grams = [clean[i : i + 8] for i in range(0, len(clean) - 7, 4)]
            unique_ratio = len(set(grams)) / max(len(grams), 1)
            if unique_ratio > 0.85:
                score += 0.2
        return min(score, 1.0)

    def _check_explicit_conclusion(self) -> GateCheckResult:
        """FP6 L1: Check that report contains an explicit conclusion/investment thesis.

        验证报告开头或摘要部分包含明确的结论句。
        R12（2026-08-01 全量优化）：unlisted（非上市）语义不同于上市——
        非上市没有"评级/目标价"概念，价值判断是"投资价值/估值区间/退出路径"。
        检查器按 report_type 分支：listed 查评级+目标价，unlisted 查投资价值+估值+退出。
        """
        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("explicit_conclusion", False, 0.0, "text too short")

        import re as _re

        first_2000 = text[:2000]

        if self.report_type in ("unlisted_company",):
            # 非上市语义：投资价值/估值区间/退出路径/核心判断
            has_value = bool(_re.search(r"(?:投资价值|投资判断|值得投资|投资建议|建议关注|值得关注)", first_2000))
            has_val_range = bool(_re.search(r"(?:估值区间|估值范围|估值[在约为])[^。]*?\d+", first_2000))
            has_exit = bool(_re.search(r"(?:退出路径|退出方式|IPO|并购|转让|退出可行)", first_2000))
            has_thesis = bool(_re.search(r"(?:核心判断|核心观点|我们认为|我们判断|投资逻辑|决策门)", first_2000))
            elements = sum([has_value, has_val_range, has_exit, has_thesis])
            score = elements / 4.0
            passed = score >= 0.34  # 至少 2/4
            details = (
                f"投资价值={'Y' if has_value else 'N'} 估值区间={'Y' if has_val_range else 'N'} "
                f"退出路径={'Y' if has_exit else 'N'} 核心判断={'Y' if has_thesis else 'N'} = {score:.2f}"
            )
            return GateCheckResult("explicit_conclusion", passed, score, details)

        if self.report_type == "industry_deep":
            # R93（2026-08-10）行业语义：行业评级 + 受益环节排序 + 核心判断。
            # 行业报告是"判断驱动"，公司作论据，不要求个股目标价。
            has_industry_rating = bool(
                _re.search(
                    r"(?:行业评级|建议|给予|看好)[^。]*(?:增持|中性|减持|超配|标配|低配|overweight|equalweight|underweight)",
                    first_2000,
                )
            )
            has_benefit_chain = bool(
                _re.search(r"(?:受益环节|受益标的|推荐标的|优先配置|配置建议|环节排序|首选|重点公司)", first_2000)
            )
            has_thesis = bool(
                _re.search(r"(?:核心判断|核心观点|我们认为|我们判断|投资逻辑|Bold Call|行业判断|主线)", first_2000)
            )
            elements = sum([has_industry_rating, has_benefit_chain, has_thesis])
            score = elements / 3.0
            passed = score >= 0.34  # 至少 1/3
            details = (
                f"行业评级={'Y' if has_industry_rating else 'N'} "
                f"受益环节={'Y' if has_benefit_chain else 'N'} "
                f"核心判断={'Y' if has_thesis else 'N'} = {score:.2f}"
            )
            return GateCheckResult("explicit_conclusion", passed, score, details)

        # 上市语义：评级 + 目标价 + 核心观点
        has_rating = bool(
            _re.search(
                r"(?:建议|评级|维持|给予)[^。]*(?:买入|增持|持有|中性|减持|卖出|outperform|buy|hold|reduce|sell|overweight|equalweight|underweight)",
                first_2000,
            )
        )
        has_target = bool(_re.search(r"(?:目标价|target\s*price|TP)[^。]*?\d+", first_2000))
        has_thesis = bool(
            _re.search(r"(?:核心判断|核心观点|我们认为|我们判断|投资要点|投资逻辑|Bold Call)", first_2000)
        )

        elements = sum([has_rating, has_target, has_thesis])
        score = elements / 3.0
        passed = score >= 0.34  # At least one of three

        details = f"Rating={'Y' if has_rating else 'N'} Target={'Y' if has_target else 'N'} Thesis={'Y' if has_thesis else 'N'} = {score:.2f}"
        return GateCheckResult("explicit_conclusion", passed, score, details)

    def _check_attribution_depth(self) -> GateCheckResult:
        """FP6 L3: Check that analysis contains multi-factor attribution with weights.

        验证报告是否有"归因分析"——将结果归因到多个驱动因素并给出各因素权重。
        """
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("attribution_depth", False, 0.0, "text too short")

        import re as _re

        # Check for multi-factor attribution patterns
        has_factor_analysis = bool(
            _re.search(
                r"(?:驱动因素|驱动因子|归因|attribution|主要原因|核心驱动|关键变量|多重因素|增长驱动|成长驱动|发展驱动|增长动力|驱动逻辑)",
                text,
            )
        )
        has_weight = bool(
            _re.search(r"(?:权重|占比|贡献|bps|百分点|主要|核心|关键|主导).{0,20}(?:因素|驱动|原因)", text)
        )
        has_sub_factor = bool(_re.search(r"(?:子因素|二级|细分|拆解)(?:分析|维度|指标)", text))
        has_causal_chain = bool(_re.search(r"(?:A.{0,10}导致B|因为.{0,20}所以.{0,20}|传递|传导|连锁)", text))

        # Check for 3+ explicit factors
        factors = _re.findall(
            r"(?:第一个|第二|第三|首先|其次|再次|另外|此外|同时)[^。]{0,50}(?:原因|因素|驱动|因为)", text
        )
        has_3plus_factors = len(factors) >= 2  # "首先...其次..." counts as 2, implying at least 2 more

        elements = sum([has_factor_analysis, has_weight, has_sub_factor, has_causal_chain, has_3plus_factors])
        score = elements / 5.0
        # FP7b L1 降级：数据受限报告归因框架不完整不阻断交付（warning），正常模式仍硬把关
        threshold = 0.2 if self._allow_placeholder_degradation else 0.4
        passed = score >= threshold
        severity = "warning" if self._allow_placeholder_degradation else "error"

        details = f"FactorAnalysis={'Y' if has_factor_analysis else 'N'} Weight={'Y' if has_weight else 'N'} SubFactor={'Y' if has_sub_factor else 'N'} CausalChain={'Y' if has_causal_chain else 'N'} 3+Factors={'Y' if has_3plus_factors else 'N'} = {score:.2f}"
        return GateCheckResult("attribution_depth", passed, score, details, severity=severity)

    def _check_falsification_conditions(self) -> GateCheckResult:
        """FP6 L5: Verify 'if...then...' falsification conditions exist"""
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("falsification_conditions", True, 1.0, "text too short, skipped", severity="warning")

        import re

        # Check for if-then falsification structures
        patterns = [
            r"(?:如果|假如|假设|倘若|一旦).{0,50}(?:那么|则|就会|可能)",
            r"(?:证伪|False|推翻|不成立|失效|例外|条件)",
            r"(?:前提|假设条件|前提假设|先决条件)",
            r"(?:如果).{0,30}(?:风险|下跌|不及预期|低于)",
        ]
        has_falsification = any(re.search(p, text) for p in patterns)

        # Check that Bold Call has falsification nearby
        bold_pos = re.search(r"(?:Bold Call|核心理念|核心判断|核心观点)", text)
        falsified_bold = False
        if bold_pos:
            start = max(0, bold_pos.start() - 200)
            end = min(len(text), bold_pos.end() + 500)
            bold_context = text[start:end]
            falsified_bold = any(re.search(p, bold_context) for p in patterns)

        score = 0.4 if has_falsification else 0.0
        if falsified_bold:
            score = max(score, 0.7)
        passed = score >= 0.4
        return GateCheckResult(
            "falsification_conditions",
            passed,
            score,
            f"falsification={'Y' if has_falsification else 'N'} bold_falsifiable={'Y' if falsified_bold else 'N'}",
        )

    def _check_template_leak(self) -> GateCheckResult:
        """FP4: Block report if template placeholder text is visible"""
        text = self.report_text or ""
        if not text:
            return GateCheckResult("template_leak", True, 1.0, "no text", severity="warning")
        import re

        # 模板占位文本模式
        patterns = [
            r"第[一二三四五六七八九十]章\s+行业概览",
            r"这是正文样例",
            r"1\.1\s+市场规模",
            r"Key\s+Takeaways",
        ]
        hits = []
        for pat in patterns:
            matches = re.findall(pat, text)
            hits.extend(matches)
        passed = len(hits) == 0
        score = 0.0 if hits else 1.0
        details = f"模板泄露: {len(hits)}处" if hits else "无模板泄露"
        return GateCheckResult("template_leak", passed, score, details, severity="error")

    def _check_meta_cognition(self) -> GateCheckResult:
        """FP6 L6: Verify confidence markers (H/M/L) and blind spots mention"""
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("meta_cognition", True, 1.0, "text too short, skipped", severity="warning")

        import re

        # Count confidence markers
        confidence = len(re.findall(r"(?:H=High|M=Medium|L=Low|\d+%|置信度|confidence|确信度)", text))

        # Check for blind spots / uncertainty / limitations
        has_blind_spot = bool(re.search(r"(?:不确定|局限|盲区|未覆盖|假设|风险因素|未知|未考虑|局限)", text))

        score = 0.0
        if confidence >= 3:
            score = 0.4
        if has_blind_spot:
            score += 0.4
        if confidence >= 5:
            score += 0.2
        score = min(1.0, score)

        passed = score >= 0.4  # At least 3 confidence markers OR blind spot mention
        return GateCheckResult(
            "meta_cognition", passed, score, f"confidence={confidence} blind_spot={'Y' if has_blind_spot else 'N'}"
        )

    def _check_counterargument_strength(self) -> GateCheckResult:
        """R75（2026-08-05 Phase 6）：反方论证强度量化——对标 Bernstein DES。

        R73 审计发现：Gate 当前只查"存在反方观点"不查"反方观点对主判断构成多大威胁"。
        油位v6有20处反方观点但全是弱反驳（"此概率30%/40%"的无证据声明）。
        真正强反方论证需要：①具体概率基数（不是凭空估计）；②证伪条件+时间窗口；
        ③若反方成立对主判断的杀伤力评估（"若为真→目标价下调X%"）。

        DES 评分：强反方（有具体证伪条件+杀伤力评估）→高分（反方越强主判断仍成立=越可信）。
        弱反方（只有"此概率X%"的空壳）→低分（反方太弱=主判断未经有效检验）。
        """
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("counterargument_strength", True, 1.0, "text too short, skipped", severity="warning")

        import re

        # 查找所有反方/证伪段落
        counter_sections = re.findall(
            r"(?:反方(?:论证|观点|论)|证伪|Bear Case|risk scenario)"
            r".{0,200}?(?=\n\n|\n##|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        strong_count = 0
        weak_count = 0

        for sec in counter_sections:
            has_specific_condition = bool(re.search(r"(?:若|如果|当|一旦|触发).{0,40}(?:则|那么|就会|将)", sec))
            has_kill_assessment = bool(
                re.search(
                    r"(?:下调|减少|降|跌|风险)"
                    r".{0,30}(?:\d+%|\d+元|\d+点|百分点|pct)",
                    sec,
                )
            )
            has_probability = bool(re.search(r"(?:概率|可能性).{0,15}(?:\d+%)", sec))
            has_time_window = bool(re.search(r"(?:\d{4}年|Q[1-4]|\d+个月|\d+季度|时间窗口)", sec))

            if has_specific_condition and has_kill_assessment:
                strong_count += 1
            elif has_probability and not (has_specific_condition and has_kill_assessment):
                weak_count += 1

        total = strong_count + weak_count
        if total == 0:
            return GateCheckResult(
                "counterargument_strength", True, 1.0, "无反方段落（不扣分但建议增加）", severity="info"
            )

        strong_ratio = strong_count / total if total > 0 else 0
        # DES: 强反方占比越高，报告可信度越高（反方越强主判断仍成立=越可信）
        # 阈值：≥50% 强反方=DES合格；全弱反方=FAIL
        score = 0.3 + 0.7 * strong_ratio
        passed = strong_ratio >= 0.3  # 至少30%反方是"强反方"

        details = f"DES={strong_count}/{total}强({strong_ratio:.0%}) (阈值30%)——强=有条件+杀伤力评估；弱=仅有概率空壳"
        return GateCheckResult("counterargument_strength", passed, score, details, severity="warning")

    def _check_so_what_per_judgment(self) -> GateCheckResult:
        """FP2b upgrade: Each judgment must have its own So What chain (not paragraph average)"""
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("so_what_per_judgment", True, 1.0, "text too short, skipped", severity="warning")

        import re

        # Find judgment sentences (allow So What to follow in next sentence)
        judgments = re.findall(
            r"[^。]*?(?:我们认为|我们判断|我们预计|我们建议|核心判断|核心结论|判断[：:])[^。]*。[^。]*?(?:因此|这意味着|所以|导致|从而|影响|So\s*What|数据表明|对投资者意味着|综合判断|证伪条件)[^。]*。",
            text,
        )
        if not judgments:
            # 回退：只要判断句后紧跟"因此..."也算完整（兼容 StyleCompiler 追加）
            j_simple = re.findall(
                r"[^。]*(?:我们认为|我们判断|我们预计|我们建议|核心判断|核心结论|判断[：:])[^。]*。", text
            )
            if not j_simple:
                return GateCheckResult("so_what_per_judgment", False, 0.0, "no explicit judgments found")
            complete = 0
            search_from = 0
            for j in j_simple:
                # 从当前判断句位置往后找（避免每次都从全文开头）
                pos = text.find(j, search_from)
                if pos < 0:
                    pos = text.find(j)
                tail = text[pos + len(j) : pos + len(j) + 150]
                has_implication = bool(
                    re.search(
                        r"(?:因此|这意味着|所以|导致|从而|影响|So\s*What|数据表明|对投资者意味着|综合判断|证伪条件)",
                        tail,
                    )
                )
                if has_implication:
                    complete += 1
                search_from = pos + len(j)
            ratio = complete / len(j_simple)
            score = min(1.0, ratio)
            # FP7b L1 降级：数据受限下判断句 So What 链覆盖放宽（段落级 so_what_chain 仍把关）
            threshold = 0.25 if self._allow_placeholder_degradation else 0.5
            passed = score >= threshold
            severity = "warning" if self._allow_placeholder_degradation else "error"
            return GateCheckResult(
                "so_what_per_judgment",
                passed,
                score,
                f"{complete}/{len(j_simple)} complete chains ({score:.2f})",
                severity=severity,
            )

        complete = len(judgments)
        ratio = complete / max(len(judgments), 1)
        score = min(1.0, ratio)
        threshold = 0.25 if self._allow_placeholder_degradation else 0.5  # FP7b L1 降级放宽
        passed = score >= threshold
        severity = "warning" if self._allow_placeholder_degradation else "error"
        return GateCheckResult(
            "so_what_per_judgment", passed, score, f"{complete} complete chains ({score:.2f})", severity=severity
        )

    def _check_subjective_scoring(self) -> GateCheckResult:
        """FP4: Ban subjective scoring patterns like '评分8分', '8/10分', '综合评分7分'"""
        text = self.report_text or ""
        if not text:
            return GateCheckResult("subjective_scoring", True, 1.0, "no text")
        import re

        patterns = [
            r"(?:评分\d+[分/]|综合评分[:： ]*\d+|\d+/\d+分|评级[:： ]*[A-D][+\-])",
            r"(?:评分)[\s\S]{0,10}\d+[\s\S]{0,3}分",
        ]
        hits = []
        for pat in patterns:
            matches = re.findall(pat, text)
            hits.extend(matches)
        # Deduplicate
        unique_hits = list(set(hits))
        passed = len(unique_hits) == 0
        score = 0.0 if unique_hits else 1.0
        details = (
            f"{len(unique_hits)} subjective scores found: {', '.join(unique_hits[:3])}"
            if unique_hits
            else "No subjective scoring"
        )
        return GateCheckResult("subjective_scoring", passed, score, details, severity="error")

    def _check_bold_call(self) -> GateCheckResult:
        """Check Bold Call: direction + catalyst + probability + time + conviction"""
        import re

        text = self.report_text or ""
        has_direction = bool(
            re.search(r"看涨|看多|看好|买入|outperform|buy|上涨|看空|看跌|减持|卖出|reduce|sell|增持|持有|推荐", text)
        )
        has_catalyst = bool(re.search(r"催化剂|驱动|触发|catalyst|trigger|拐点|转折", text))
        has_probability = bool(re.search(r"\d+%|概率|可能性|置信度|\d+\.\d+%", text))
        has_time = bool(re.search(r"\d{4}|未来.*月|Q[1-4]|H[12]|年内|季度|月度|半年", text))
        has_conviction = bool(re.search(r"确信|强烈|核心判断|核心观点|我们认为|我们判断|Bold Call", text))

        elements = sum([has_direction, has_catalyst, has_probability, has_time, has_conviction])
        score = elements / 5.0
        passed = score >= 0.8

        details = "Bold Call 5要素: 方向(%s) 催化剂(%s) 概率(%s) 时间(%s) 确信度(%s) = %.0f%%" % (
            "Y" if has_direction else "N",
            "Y" if has_catalyst else "N",
            "Y" if has_probability else "N",
            "Y" if has_time else "N",
            "Y" if has_conviction else "N",
            score * 100,
        )

        return GateCheckResult(name="bold_call", passed=passed, score=score, details=details)

    def _check_chart_analysis_quality(self) -> GateCheckResult:
        """Check each chart has substantive analysis using weighted scoring

        P0-5 修复（2026-08-01 审计）：废除纯关键词计数（"观察|可见|显示"等），
        改用加权评分：(图表后文本长度/图表复杂度) × 引用密度。
        关键词仅作为辅助信号（权重 ≤30%）。
        """
        import re

        text = self.report_text or ""
        charts = re.findall(r"(?:!\[.*?\]\(.*?\)|\[CHART:\w+\])", text)
        if not charts:
            return GateCheckResult(
                name="chart_analysis_quality", score=0.0, passed=False, severity="warning", details="No charts found"
            )

        chart_analyses = re.split(r"!\[.*?\]\(.*?\)", text)
        scores = []

        for i, seg in enumerate(chart_analyses[1:], 1):
            seg = seg.strip()
            # ── 主要信号：文本长度/图表复杂度（截取分析段的有限长度） ──
            analysis_text = seg[:600]
            char_count = len(analysis_text)
            # 图表复杂度：从图表路径/标题推断（含 subplot/multi/combine 关键词则复杂）
            chart_label = charts[i - 1] if i - 1 < len(charts) else ""
            complexity = (
                2.0 if re.search(r"(?:subplot|multi|combine|对比|vs\.|VS)", chart_label, re.IGNORECASE) else 1.0
            )
            length_score = min(char_count / (200.0 * complexity), 1.0)

            # ── 主要信号：引用密度（引用图表 id 或数据点次数） ──
            chart_refs = len(
                re.findall(r"(?:图\s*\d+|图表\s*\d+|上图|下图|如图|图中|chart\s*\d+|figure\s*\d+)", analysis_text)
            )
            data_point_refs = len(
                re.findall(r"(?:\d+\.\d+%|\d+\.\d+[万亿千百]|[A-Z][A-Z0-9]+指标|数据显示|数据点)", analysis_text)
            )
            ref_density = min((chart_refs + data_point_refs) / 4.0, 1.0)

            # ── 辅助信号：关键词（权重30%） ──
            kw_count = len(re.findall(r"(?:观察|可见|显示|表明|体现|趋势|对比|变动|增长|下降|提升)", analysis_text))
            kw_score = min(kw_count / 5.0, 1.0)

            # ── 来源引用信号 ──
            has_citation = bool(
                re.search(r"(?:数据来源|数据源|来源|Wind|Bloomberg|Reuters|公司公告|年报)", analysis_text)
            )

            # 加权评分：主体70%（长度35%+引用密度35%）+ 辅助30%（关键词20%+来源10%）
            seg_score = length_score * 0.35 + ref_density * 0.35 + kw_score * 0.20 + (0.10 if has_citation else 0)
            scores.append(seg_score)

        avg_score = sum(scores) / len(scores) if scores else 0
        min_seg_score = min(scores) if scores else 0
        if self._allow_placeholder_degradation:
            passed = avg_score >= 0.4
        else:
            passed = avg_score >= 0.6 and min_seg_score >= 0.3
        details = "Charts:%d AnalysisQuality:%.0f%%%s" % (
            len(charts),
            avg_score * 100,
            " (L1: 放宽)" if self._allow_placeholder_degradation else "",
        )

        return GateCheckResult(
            name="chart_analysis_quality", passed=passed, score=avg_score, severity="warning", details=details
        )

    def _check_forecast_presence(self) -> GateCheckResult:
        """R16（2026-08-01 深度补强）：检查报告是否含盈利预测表 + 反共识/分歧表达。

        投行报告标配：未来 3 年盈利预测表 + 市场分歧点。缺失 = 深度不足。
        行业报告（industry_deep）预测表非强制（行业无单一公司预测），反共识强制。
        """
        text = self.report_text or ""
        import re as _re

        # 盈利预测表：未来年份 E 标记 + 营收/净利/EPS
        has_forecast = bool(_re.search(r"20\d{2}E[^。]{0,30}(?:营收|收入|净利|EPS|净利润)", text)) or bool(
            _re.search(r"(?:盈利预测|预测表|未来3年|三年预测|EPS.*20\d{2}E)", text)
        )
        # 反共识/分歧：市场共识 vs 我们判断
        has_disagreement = bool(_re.search(r"(?:市场共识|市场认为|普遍认为|一致预期|市场预期)", text)) and bool(
            _re.search(r"(?:我们判断|我们认为|我们的判断|分歧|不同|相反|质疑)", text)
        )

        if self.report_type in ("industry_deep", "industry"):
            # R93（2026-08-10）：行业报告的分歧是"判断驱动"——市场定价 vs 我们的行业判断，
            # 表达为"定价错/估值切换/主线判断/拐点"，不是个股式的"我们vs一致预期"框架。
            # 行业报告的核心是 Bold Call（行业判断+时间窗口+证伪），分歧自然融入判断。
            has_judgment = bool(
                _re.search(r"(?:行业判断|核心判断|Bold Call|主线|拐点|定价错|估值.*切换|受益环节排序)", text)
            )
            has_divergence = bool(_re.search(r"(?:分歧|市场预期|一致预期|定价|我们判断|我们认为|不同于)", text))
            # 判断驱动：有 Bold Call/行业判断 即视为有明确观点（行业报告的核心）
            passed = has_judgment
            score = 1.0 if (has_judgment and has_divergence) else (0.8 if has_judgment else 0.4)
            det = f"行业判断={'Y' if has_judgment else 'N'}; 定价分歧={'Y' if has_divergence else 'N'}; 预测表(行业可选)={'Y' if has_forecast else 'N'}"
            return GateCheckResult(
                name="forecast_presence",
                passed=passed,
                score=score,
                severity="error" if not passed else "warning",
                details=det,
            )

        # 个股报告：预测表 + 反共识都强制
        passed = has_forecast and has_disagreement
        score = (has_forecast + has_disagreement) / 2.0
        det = f"盈利预测表={'Y' if has_forecast else 'N'}; 反共识/分歧={'Y' if has_disagreement else 'N'}"
        return GateCheckResult(name="forecast_presence", passed=passed, score=score, severity="error", details=det)

    def _check_bottleneck_analysis(self) -> GateCheckResult:
        """R20（2026-08-02 王牌模块）：供应链瓶颈分析存在性校验。

        报告应包含卡点/瓶颈/稀缺环节分析（Serenity 卡点法）。
        行业报告：找行业卡点 + 利润池分布；个股报告：卡位评级 + BOM 逆向。
        校验报告是否有卡点评分/瓶颈/卡位/稀缺层等表达。

        R21（2026-08-02 全量优化）：新增利润池 + TOC 约束迭代两套表达校验。
        """
        text = self.report_text or ""
        import re as _re

        has_bottleneck = bool(
            _re.search(r"(?:瓶颈|卡点|卡位|稀缺层|稀缺环节|瓶颈环节|供应链瓶颈|关键环节|最难替代|供给最紧)", text)
        )
        has_rating = bool(_re.search(r"(?:卡位评级|卡点评分|瓶颈评级|强卡位|中卡位|强瓶颈|中瓶颈)", text))
        has_chain = bool(_re.search(r"(?:产业链|价值链|上游|中游|下游|供应)", text))
        # R21：利润池（各环节利润/利润流向/利润池）+ TOC（约束/迭代/五步/下一约束）
        has_profit_pool = bool(_re.search(r"(?:利润池|利润流向|环节利润|利润最厚|利润最薄|利润集中|利润分配)", text))
        has_toc = bool(_re.search(r"(?:约束|TOC|五步|挖尽|服从约束|下一约束|瓶颈转移)", text))

        detail_parts = [
            f"瓶颈/卡点={'Y' if has_bottleneck else 'N'}",
            f"产业链={'Y' if has_chain else 'N'}",
        ]
        if self.report_type == "industry_deep":
            passed = has_bottleneck and has_chain
            detail_parts.append(f"卡位评级(行业可选)={'Y' if has_rating else 'N'}")
        else:
            passed = has_bottleneck and has_chain
            detail_parts.append(f"卡位评级={'Y' if has_rating else 'N'}")
        # R21：行业报告利润池为强要求（有 supply_chain 数据时必须写利润流向）
        if self.report_type == "industry_deep":
            detail_parts.append(f"利润池/利润流向={'Y' if has_profit_pool else 'N'}")
            detail_parts.append(f"TOC约束迭代={'Y' if has_toc else 'N'}")
            if has_bottleneck and has_chain and has_profit_pool and has_toc:
                passed = True
            elif has_bottleneck and has_chain:
                passed = True  # 放宽：基础卡点分析已满足，利润池/TOC 为增强项
        # R22：非上市报告校验稀缺性评估表达
        elif self.report_type == "unlisted_company":
            has_scarcity = bool(_re.search(r"(?:稀缺|稀缺性|商业化|退出路径|融资验证|里程碑)", text))
            detail_parts.append(f"稀缺性评估={'Y' if has_scarcity else 'N'}")
            if has_bottleneck and has_chain and has_scarcity:
                passed = True
            elif has_bottleneck and has_chain:
                passed = True  # 放宽：基础卡点已满足，稀缺性为增强项
        score = 1.0 if passed else 0.5
        return GateCheckResult(
            name="bottleneck_analysis", passed=passed, score=score, severity="error", details="; ".join(detail_parts)
        )

    def _check_risk_layering(self) -> GateCheckResult:
        """P2-4（2026-08-01 审计）：风险四层框架检查。

        检查报告是否覆盖宏观/行业/公司/尾部四层风险。
        四层中至少三层有实质内容（非空段、非仅标题）才算通过。
        接入 run_all 检查链。
        """
        import re

        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("risk_layering", True, 1.0, "text too short, skipped", severity="warning")

        # ── 四层风险关键词定义 ──
        layer_patterns = {
            "macro": (
                r"(?:宏观经济|宏观风险|政策风险|利率风险|汇率风险|地缘政治|"
                r"GDP|通胀|CPI|PPI|货币政策|财政政策|贸易摩擦|制裁|关税)"
            ),
            "industry": (
                r"(?:行业风险|竞争格局|产能过剩|价格战|替代品|技术迭代|"
                r"监管风险|行业政策|需求萎缩|供给冲击|行业周期)"
            ),
            "company": (
                r"(?:公司风险|经营风险|管理层风险|治理风险|财务风险|"
                r"客户集中|供应商集中|应收账款|现金流|负债率|诉讼)"
            ),
            "tail": (
                r"(?:尾部风险|极端风险|黑天鹅|灰犀牛|不可抗力|流动性危机|"
                r"系统性风险|崩盘|恐慌|连锁反应|尾部|极值|压力测试)"
            ),
        }

        # 每个层级至少需要 30 个有实质内容的中文字符（过滤仅标题/列表符号）
        layers_found = {}
        for layer_name, pattern in layer_patterns.items():
            # 先定位该层风险段落
            matches = list(re.finditer(pattern, text))
            if not matches:
                layers_found[layer_name] = 0
                continue
            # 取匹配位置附近上下文（前后各200字），合并去重后计算中文实质内容
            context_set = set()
            for m in matches:
                start = max(0, m.start() - 200)
                end = min(len(text), m.end() + 200)
                context_set.add(text[start:end])
            context = " ".join(context_set)
            # 去除标点空白后统计中文字符
            cn_chars = len(re.findall(r"[\u4e00-\u9fff]", context))
            layers_found[layer_name] = cn_chars

        # 判定：至少三层有 ≥30 中文字符实质内容
        substantial_layers = sum(1 for v in layers_found.values() if v >= 30)
        total_layers = len(layer_patterns)
        passed = substantial_layers >= 3

        layer_detail = ", ".join(f"{k}:{v}c" for k, v in layers_found.items())
        details = f"风险层覆盖: {substantial_layers}/{total_layers} ({layer_detail})"
        score = min(1.0, substantial_layers / 3.0) if passed else max(0.0, substantial_layers / 4.0)

        return GateCheckResult("risk_layering", passed, score, details, severity="warning")

    def _check_stock_pick_chain(self) -> "GateCheckResult":
        """R55：选股传导链存在性——行业报告必须从行业逻辑推导受益标的。

        顶级投行行业报告终点是"从分析到可操作"：行业判断 → 受益标的 → 为什么是它。
        检查报告是否含"推荐标的/受益标的/首选/重点标的 + 评级/目标价"传导链。
        """
        import re as _re

        text = self.report_text or ""
        if self.report_type != "industry_deep" or len(text) < 300:
            return GateCheckResult("stock_pick_chain", True, 1.0, "非行业报告，跳过", severity="warning")
        has_pick = bool(_re.search(r"受益标的|推荐标的|重点标的|首选|选股|标的选择|最受益|受益环节", text))
        has_rating = bool(_re.search(r"增持|买入|推荐|评级|目标价|配置|优先", text))
        has_logic = bool(_re.search(r"行业逻辑|传导|受益于|弹性最大|环节排序", text))
        passed = has_pick and has_rating and has_logic
        score = (has_pick + has_rating + has_logic) / 3.0
        det = f"选股传导链: 标的={has_pick} 评级={has_rating} 逻辑={has_logic}"
        return GateCheckResult("stock_pick_chain", passed, score, det, severity="error")

    def _check_unlisted_threat(self) -> "GateCheckResult":
        """R55：非上市威胁判断存在性——行业报告必须有非上市关键玩家的威胁度判断。

        非上市龙头（华为/大疆/未上市厂商）是竞争格局的重要变量。报告须评估其战略
        动作对利润池的影响，且不假装有财务数据（FP2 诚实边界）。
        """
        import re as _re

        text = self.report_text or ""
        if self.report_type != "industry_deep" or len(text) < 300:
            return GateCheckResult("unlisted_threat", True, 1.0, "非行业报告，跳过", severity="warning")
        has_unlisted = bool(_re.search(r"非上市|未上市|非上市玩家|未上市玩家", text))
        has_threat = bool(_re.search(r"威胁|冲击|潜在进入者|新进入者|竞争格局演变|产能扩张|技术突破", text))
        has_source_note = bool(_re.search(r"无权威数据|无公开数据|数据不可得|估算|置信度", text))
        passed = has_unlisted and has_threat
        if passed and not has_source_note:
            score = 0.7
        else:
            score = (has_unlisted + has_threat) / 2.0
        det = f"非上市威胁: 覆盖={has_unlisted} 威胁度={has_threat} 来源标注={has_source_note}"
        return GateCheckResult("unlisted_threat", passed, score, det, severity="warning")

    def _check_tam_bottomup(self) -> "GateCheckResult":
        """R55：TAM/SAM/SOM 自底向上校验——市场规模必须可推导，禁"引一个数字就完事"。

        Gartner/IDC 方法论：市场规模应 top-down × bottom-up 双轨，TAM 逐层收缩
        （渗透率/可及渠道/竞争份额）。检查报告的市场规模是否含推导依据。
        """
        import re as _re

        text = self.report_text or ""
        if self.report_type != "industry_deep" or len(text) < 300:
            return GateCheckResult("tam_bottomup", True, 1.0, "非行业报告，跳过", severity="warning")
        # TAM/市场规模表述（"市场规模X亿美元"也是 TAM 声明）
        has_tam = bool(_re.search(r"TAM|总可寻址|总市场规模|可服务市场|可获得市场|SAM|SOM|市场规模", text))
        has_derivation = bool(
            _re.search(r"渗透率[^。]{0,10}%\d?|单价|价格.{0,4}数量|台数|出货量|假设|驱动因子|渗透率曲线", text)
        )
        has_source = bool(_re.search(r"来源|数据源|Gartner|IDC|Frost|灼识|机构预测|测算", text))
        if not has_tam:
            return GateCheckResult("tam_bottomup", True, 1.0, "无TAM表述，跳过", severity="warning")
        passed = has_derivation and has_source
        score = 1.0 if passed else 0.5
        det = f"TAM自底向上: 三层拆解={has_tam} 推导依据={has_derivation} 来源标注={has_source}"
        return GateCheckResult("tam_bottomup", passed, score, det, severity="error")

    def _check_regional_penetration(self) -> "GateCheckResult":
        """R55：区域渗透率错位判断——行业报告必须有"中国 vs 海外领先国"的渗透率错位分析。

        时光机逻辑：中国渗透率可能落后海外 3-5 年，海外路径是中国未来的参照。
        """
        import re as _re

        text = self.report_text or ""
        if self.report_type != "industry_deep" or len(text) < 300:
            return GateCheckResult("regional_penetration", True, 1.0, "非行业报告，跳过", severity="warning")
        has_regions = bool(_re.search(r"北美|欧洲|亚太|海外|美国|日本|韩国", text))
        has_penetration = bool(_re.search(r"渗透率", text))
        has_gap_judgment = bool(_re.search(r"错位|落后|领先|差距|时光机|对标|参照|滞后", text))
        passed = has_regions and has_penetration and has_gap_judgment
        score = (has_regions + has_penetration + has_gap_judgment) / 3.0
        det = f"区域渗透率错位: 区域={has_regions} 渗透率={has_penetration} 错位判断={has_gap_judgment}"
        return GateCheckResult("regional_penetration", passed, score, det, severity="error")

    def _check_industry_consolidation(self) -> "GateCheckResult":
        """R57：行业并购视角——行业报告必须有整合/并购信号。

        顶级投行行业报告必含行业整合趋势、谁是整合者/被整合者、并购估值倍数。
        判断行业终局（寡头/一超多强/分散）。
        """
        import re as _re

        text = self.report_text or ""
        if self.report_type != "industry_deep" or len(text) < 300:
            return GateCheckResult("industry_consolidation", True, 1.0, "非行业报告，跳过", severity="warning")
        has_consolidation = bool(_re.search(r"整合|并购|集中度提升|行业集中|整合者|被整合者", text))
        has_financial = bool(_re.search(r"EV/EBITDA|并购估值|ROIC|WACC|资本配置|估值倍数", text))
        has_winner = bool(_re.search(r"整合者|赢家|龙头集中|份额提升|谁受益|一超多强|寡头", text))
        passed = has_consolidation and (has_financial or has_winner)
        score = (has_consolidation + has_financial + has_winner) / 3.0
        det = f"行业并购: 整合趋势={has_consolidation} 财务/倍数={has_financial} 终局判断={has_winner}"
        return GateCheckResult("industry_consolidation", passed, score, det, severity="warning")

    def _check_core_hypothesis(self) -> "GateCheckResult":
        """R57：MBB假设驱动——行业报告必须有可证伪核心假设。

        麦肯锡假设驱动：'如果我们是对的，应观察到X；若X未发生，假设错'。
        报告开头必须给单句可证伪假设 + 先行指标。
        """
        import re as _re

        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("core_hypothesis", True, 1.0, "text too short, skipped", severity="warning")
        has_hypothesis = bool(_re.search(r"核心假设|假设[:：]|我们假设|如果.{0,10}(?:对|成立)", text))
        has_falsifiable = bool(_re.search(r"可证伪|证伪|如果.*就错|若.*未发生|失效触发", text))
        has_indicator = bool(_re.search(r"先行指标|观察|信号|应看到|应观察到", text))
        passed = has_hypothesis and (has_falsifiable or has_indicator)
        score = (has_hypothesis + has_falsifiable + has_indicator) / 3.0
        det = f"核心假设: 假设={has_hypothesis} 可证伪={has_falsifiable} 先行指标={has_indicator}"
        return GateCheckResult("core_hypothesis", passed, score, det, severity="warning")

    def _check_esg_materiality(self) -> "GateCheckResult":
        """R57：ESG实质性——行业报告必须有行业最实质ESG议题判断。

        对标 GRI/SASB/TCFD：判断行业最实质ESG风险（碳/治理/社会）及对估值影响。
        """
        import re as _re

        text = self.report_text or ""
        if self.report_type != "industry_deep" or len(text) < 300:
            return GateCheckResult("esg_materiality", True, 1.0, "非行业报告，跳过", severity="warning")
        has_esg = bool(_re.search(r"ESG|碳排放|碳排|双碳|碳中和|环境|社会|治理", text))
        has_material = bool(_re.search(r"实质性|最重要|核心议题|重点议题|关键风险", text))
        has_impact = bool(_re.search(r"影响估值|折价|溢价|风险.*估值|成本上升|合规风险", text))
        passed = has_esg and (has_material or has_impact)
        score = (has_esg + has_material + has_impact) / 3.0
        det = f"ESG实质性: ESG={has_esg} 实质性={has_material} 估值影响={has_impact}"
        return GateCheckResult("esg_materiality", passed, score, det, severity="warning")

    def _check_evidence_chain(self) -> "GateCheckResult":
        """R60（2026-08-03）：证据链门禁——工具数据必须进正文。

        对齐 FinGround 原子声明验证思路：compute 层产出的工具数据
        （信号链/弹性/护城河/生命周期/并购）必须在正文被引用，
        否则说明工具"白算"（大脑升级、手脚未接）。

        检查：行业/公司报告若含对应 SAC 维度，正文须出现工具关键词
        （如"信号链/先行指标/弹性/护城河/并购整合/生命周期阶段"）。
        """
        import re as _re

        text = self.report_text or ""
        if len(text) < 300:
            return GateCheckResult("evidence_chain", True, 1.0, "text too short, skipped", severity="warning")
        # 工具 → 正文关键词映射（与 compute tool_modules 对应）
        _tool_kw = {
            "signal_chain": r"信号链|先行指标|同步指标|滞后指标",
            "elasticity": r"弹性|收入弹性|价格弹性|需求弹性",
            "moat": r"护城河|竞争壁垒|进入壁垒",
            "life_cycle": r"生命周期|导入期|成长期|成熟期|衰退期",
            "consolidation": r"并购|整合者|行业整合|EV/EBITDA",
        }
        missing = []
        found = 0
        for tool, pat in _tool_kw.items():
            if _re.search(pat, text):
                found += 1
            else:
                # 该工具对应的维度是否存在（需判断报告类型）
                missing.append(tool)
        # 至少覆盖 2/5 工具（核心证据链存在）
        passed = found >= 2
        score = found / len(_tool_kw)
        det = f"证据链: {found}/{len(_tool_kw)} 工具数据进正文" + (
            f" 缺失:{'/'.join(missing)}" if missing else " 全覆盖"
        )
        return GateCheckResult("evidence_chain", passed, score, det, severity="warning")

    def _check_placeholder_charts(self) -> GateCheckResult:
        """Detect placeholder charts (stub images with placeholder text or tiny file size)"""
        import os
        import re

        placeholder_alts = len(
            re.findall(r"!\[(?:数据获取中|待补充|placeholder|图例|图表描述|暂无数据|未生成)\]", self.report_text)
        )
        all_charts = re.findall(r"!\[.*?\]\((.*?)\)", self.report_text)
        small_charts = 0
        for cp in all_charts:
            cp = cp.strip()
            if cp.startswith("http"):
                continue
            try:
                fsize = os.path.getsize(cp)
                if fsize < 30000:
                    small_charts += 1
            except Exception:
                pass
        total_flags = placeholder_alts + small_charts
        # 图表是报告灵魂：非降级模式下 placeholder 一律不通过；
        # L1 视觉降级（FP7b）时 placeholder 为预期内的降级交付，不硬阻断但计分扣减
        if self._allow_placeholder_degradation:
            passed = True
            score = 0.3 if total_flags > 0 else 1.0
            severity = "warning"
        else:
            passed = total_flags == 0
            score = 0.0 if total_flags > 0 else 1.0
            severity = "error"
        det = "Placeholder alts: %d, Small charts: %d" % (placeholder_alts, small_charts)
        if passed and total_flags == 0:
            det = "All charts are real"
        return GateCheckResult(name="placeholder_charts", passed=passed, score=score, details=det, severity=severity)

    def _check_methodology_compliance(self):
        # P1-audit 2026-08-24：从 iron_gate.py 本体迁入 checks mixin——
        # r61 迁移完整性测试只扫 checks/*.py 的 _check_* 定义，
        # 留在 iron_gate 本体会被判为 run_all 执行了未定义方法。
        from pipeline.checks.base import GateCheckResult
        from pipeline.checks.methodology_compliance import check_methodology_compliance

        r = check_methodology_compliance(self.report_text or "", self.report_type or "")
        det = "; ".join(r["issues"][:3]) if r["issues"] else "无"
        return GateCheckResult("methodology_compliance", r["passed"], r["score"], det, severity="warning")

    def _check_inline_citations(self) -> GateCheckResult:
        """P3-B：[E#] 写作期证据标注密度（warning 级引导）。

        配合注入器 ev_str 的《证据编号清单》：数字密集报告应出现
        至少 2 处 [En] 引用。无清单/低密度仅降分告警，不阻断。
        """
        import re

        text = self.report_text or ""
        if len(text) < 1500:
            return GateCheckResult("inline_citations", True, 1.0, "短文跳过", severity="warning")
        tags = len(re.findall(r"\[E\d+\]", text))
        nums = len(re.findall(r"\d+\.?\d*\s*(?:亿|万|%|倍|元)", text))
        need = max(2, nums // 60)
        if tags >= need:
            return GateCheckResult(
                "inline_citations", True, 1.0, f"E标注 {tags} 处 / 数字点 {nums}", severity="warning"
            )
            # unreachable
        return GateCheckResult(
            "inline_citations",
            False,
            max(0.3, 0.6 - (need - tags) * 0.1),
            f"E标注不足: {tags}/{need}（数字点 {nums}）——关键数字请标 [En]",
            severity="warning",
        )

    def _check_style_distance(self) -> GateCheckResult:
        """S2：风格距离门禁（warning 级）。

        目标指纹 data/fingerprints/<style>.json 不存在时直接跳过；
        存在则计算 8 维向量距离，>1.5 告警并列出最差维度。
        红线：只比形式特征（句长/密度/连接词谱），不比对内容词。
        """
        from pipeline.checks.base import GateCheckResult

        text = self.report_text or ""
        if len(text) < 1500:
            return GateCheckResult("style_distance", True, 1.0, "短文跳过", severity="warning")
        try:
            from core.style_fingerprint import distance, extract, load_target

            target = load_target(getattr(self, "style", "") or "")
            if not target:
                return GateCheckResult(
                    "style_distance", True, 1.0, f"无 {self.style} 指纹档案，跳过", severity="warning"
                )
            vec = extract(text)
            d = distance(vec, target)
            if d <= 1.5:
                return GateCheckResult("style_distance", True, 1.0, f"风格距离 {d:.2f}", severity="warning")
            return GateCheckResult(
                "style_distance",
                False,
                max(0.3, 1.0 - (d - 1.5) * 0.2),
                f"风格距离 {d:.2f} > 1.5——检查句长/判断密度/连接词谱偏离",
                severity="warning",
            )
        except Exception as e:
            return GateCheckResult("style_distance", True, 0.8, f"跳过: {str(e)[:50]}", severity="warning")
