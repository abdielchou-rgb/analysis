# -*- coding: utf-8 -*-
"""覆盖完整性与实体验证检查 Mixin。

解决 R63 发现的"品牌覆盖代替实体覆盖""上市公司偏见"等系统性问题。
"""
import json
import re
from pathlib import Path
from pipeline.checks.base import GateCheckResult, logger

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_unlisted_players():
    """加载非上市玩家数据。"""
    path = _PROJECT_ROOT / "data" / "unlisted_players.json"
    if not path.exists():
        logger.warning("unlisted_players.json 不存在: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("加载 unlisted_players.json 失败: %s", e)
        return {}


def _load_brand_mapping():
    """加载品牌实体映射。"""
    path = _PROJECT_ROOT / "data" / "brand_entity_mapping.json"
    if not path.exists():
        logger.warning("brand_entity_mapping.json 不存在: %s", path)
        return {"mappings": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("加载 brand_entity_mapping.json 失败: %s", e)
        return {"mappings": []}


class CoverageChecksMixin:
    """覆盖完整性与实体验证检查。"""

    @staticmethod
    def _extract_core_entity_name(entity_name: str) -> str:
        """从完整实体名中提取核心名称，用于模糊匹配。
        
        P0-2（2026-08-07）：提取逻辑 —— 去括号内后缀 + 去常见公司后缀。
        例：「科隆测量仪器(上海)有限公司」→「科隆测量仪器」；
        「ABB（中国）有限公司」→「ABB」。
        """
        import re as _re
        core = _re.sub(r'[（(][^)）]*[)）]', '', entity_name).strip()
        for suffix in ["有限公司", "股份有限公司", "有限责任公司", "分公司", "投资有限公司",
                       "科技股份有限公司", "技术股份有限公司", "（中国）", "(中国)"]:
            core = core.replace(suffix, "").strip()
        return core

    def _check_coverage_completeness(self) -> GateCheckResult:
        """覆盖完整性检查：三层校验。

        a. 分类覆盖检查：报告是否覆盖了（上市玩家 / 非上市玩家 / 外资在华实体）三个分类
        b. 品牌→实体映射检查：报告中是否用品牌名替代实体名
        c. 集团归属检查：报告中集团归属是否有已知错误
        """
        report_text = getattr(self, "report_text", "")
        if not report_text:
            return GateCheckResult(name="覆盖完整性", passed=False, score=0.0,
                                   details="无报告文本", severity="error")

        brand_mapping = _load_brand_mapping()
        mappings = brand_mapping.get("mappings", [])

        # 构建品牌名列表和实体名列表
        brand_names = [m["brand"] for m in mappings if m.get("brand")]
        entity_names = [m["entity"] for m in mappings if m.get("entity")]
        group_names = list({m["group"] for m in mappings if m.get("group")})

        # 构建品牌→实体映射字典
        brand_to_entity = {}
        for m in mappings:
            brand = m.get("brand", "")
            entity = m.get("entity", "")
            if brand and entity:
                brand_to_entity[brand] = entity

        # 构建品牌→集团映射字典
        brand_to_group = {}
        for m in mappings:
            brand = m.get("brand", "")
            group = m.get("group", "")
            if brand and group:
                brand_to_group[brand] = group

        details_parts = []
        missing_categories = []
        brand_mapping_issues = []
        group_attribution_issues = []

        # ── a. 分类覆盖检查 ──
        # 定义三个分类的关键词
        listed_keywords = ["上市", "上市公司", "A股", "港股", "美股", "IPO", "已上市"]
        unlisted_keywords = ["非上市", "未上市", "非公开", "私有", "未公开"]
        foreign_keywords = ["外资", "外商", "海外企业", "跨国", "国际巨头", "在华外资"]

        has_listed = any(kw in report_text for kw in listed_keywords)
        has_unlisted = any(kw in report_text for kw in unlisted_keywords)
        has_foreign = any(kw in report_text for kw in foreign_keywords)

        if not has_listed:
            missing_categories.append("上市玩家")
        if not has_unlisted:
            missing_categories.append("非上市玩家")
        if not has_foreign:
            missing_categories.append("外资在华实体")

        category_deduction = len(missing_categories) * 0.15

        if missing_categories:
            details_parts.append("缺失分类: %s" % ", ".join(missing_categories))

        # ── b. 品牌→实体映射检查 ──
        # 检查报告中是否出现品牌名但未出现对应的实体名。
        # P0-2（2026-08-07）：原逻辑仅做完整实体名字符串匹配（entity in report_text），
        # 导致报告中写"科隆测量仪器"而映射表里是"科隆测量仪器(上海)有限公司"时误报。
        # 修复：提取实体核心名（去括号与常见公司后缀），品牌提及附近 500 字符窗口内
        # 核心名命中即认为关联成功。

        for brand in brand_names:
            if brand in report_text:
                entity = brand_to_entity.get(brand, "")
                if not entity:
                    continue
                # 完整实体名匹配
                if entity in report_text:
                    continue
                # P0-2 修复：核心名匹配（品牌提及位置附近 500 字符窗口内）
                core = self._extract_core_entity_name(entity)
                if core and len(core) >= 3:
                    brand_positions = [m.start() for m in re.finditer(re.escape(brand), report_text)]
                    matched = False
                    for bp in brand_positions:
                        window_start = max(0, bp - 250)
                        window_end = min(len(report_text), bp + 250 + len(brand))
                        if core in report_text[window_start:window_end]:
                            matched = True
                            break
                    if matched:
                        continue
                brand_mapping_issues.append("品牌'%s'未关联到实体'%s'" % (brand, entity))

        brand_deduction = len(brand_mapping_issues) * 0.1

        if brand_mapping_issues:
            details_parts.append("品牌映射问题: %s" % "; ".join(brand_mapping_issues[:5]))

        # ── c. 集团归属检查 ──
        # 检查报告中品牌是否与正确集团关联
        # R82（2026-08-06）：原逻辑把"品牌附近出现任何其他集团名"当作归属错误，
        # 而竞争格局段落必然多集团共存（维德路特/富仁/DFS 同段），造成大量误报。
        # 改为正向验证：品牌任一出现位置附近（300 字符）应出现其正确集团。
        for brand in brand_names:
            if brand not in report_text:
                continue
            correct_group = brand_to_group.get(brand, "")
            if not correct_group:
                continue
            brand_positions = [m.start() for m in re.finditer(re.escape(brand), report_text)]
            group_positions = [m.start() for m in re.finditer(re.escape(correct_group), report_text)]
            matched = any(
                any(abs(bp - gp) < 300 for gp in group_positions)
                for bp in brand_positions
            )
            if not matched:
                group_attribution_issues.append(
                    "品牌'%s'附近（300字符）未出现正确集团'%s'" % (brand, correct_group)
                )

        group_deduction = len(group_attribution_issues) * 0.1

        if group_attribution_issues:
            details_parts.append("集团归属问题: %s" % "; ".join(group_attribution_issues[:5]))

        # ── 评分 ──
        score = max(0.0, 1.0 - category_deduction - brand_deduction - group_deduction)
        passed = score >= 0.7  # 70% 阈值

        detail = "评分: %.2f" % score
        if details_parts:
            detail += " | " + " | ".join(details_parts)

        return GateCheckResult(name="覆盖完整性", passed=passed, score=score,
                               details=detail, severity="error")

    def _check_entity_verification(self) -> GateCheckResult:
        """实体验证检查。

        从报告提取公司名/品牌名，对照 brand_entity_mapping.json 和
        unlisted_players.json 验证基本信息是否有明显错误。
        """
        report_text = getattr(self, "report_text", "")
        if not report_text:
            return GateCheckResult(name="实体验证", passed=False, score=0.0,
                                   details="无报告文本", severity="warning")

        brand_mapping = _load_brand_mapping()
        unlisted_data = _load_unlisted_players()
        mappings = brand_mapping.get("mappings", [])

        errors = []

        # 构建品牌名列表
        brand_names = [m["brand"] for m in mappings if m.get("brand")]

        # ── 检查1：品牌→实体映射 ──
        # 对报告中出现的每个品牌名，检查是否也提到了对应的实体名
        brand_to_entity = {}
        for m in mappings:
            brand = m.get("brand", "")
            entity = m.get("entity", "")
            if brand and entity:
                brand_to_entity[brand] = entity

        for brand in brand_names:
            if brand in report_text:
                entity = brand_to_entity.get(brand, "")
                if not entity:
                    continue
                # P0-2（2026-08-07）：完整实体名 + 核心名双阶段匹配
                if entity in report_text:
                    continue
                # 核心名窗口匹配（与 _check_coverage_completeness 一致）
                core = self._extract_core_entity_name(entity)
                if core and len(core) >= 3:
                    brand_positions = [m.start() for m in re.finditer(re.escape(brand), report_text)]
                    matched = False
                    for bp in brand_positions:
                        window_start = max(0, bp - 250)
                        window_end = min(len(report_text), bp + 250 + len(brand))
                        if core in report_text[window_start:window_end]:
                            matched = True
                            break
                    if matched:
                        continue
                errors.append("品牌'%s'在报告中出现但未提及对应实体'%s'" % (brand, entity))

        # ── 检查2：对照 unlisted_players.json 验证基本信息 ──
        # 从 unlisted_players.json 提取所有非上市玩家名称
        unlisted_player_names = set()
        player_info = {}  # name -> info dict
        for industry, data in unlisted_data.items():
            players = data.get("players", []) if isinstance(data, dict) else []
            for p in players:
                name = p.get("name", "")
                if name:
                    unlisted_player_names.add(name)
                    player_info[name] = p

        # 检查报告中提到的公司名是否在 unlisted_players.json 中
        # 如果有，检查基本信息（目前 unlisted_players.json 无注册资本/成立年份，
        # 但可检查 public 状态是否与报告一致）
        for name in unlisted_player_names:
            if name in report_text:
                info = player_info.get(name, {})
                is_public = info.get("public", False)
                # 如果 unlisted_players.json 标记为非上市，但报告说"已上市"
                if not is_public:
                    # 检查报告是否错误地称其为上市公司
                    # 在 name 附近 200 字符内搜索"上市"相关词
                    pos = report_text.find(name)
                    if pos >= 0:
                        context = report_text[max(0, pos - 100):pos + len(name) + 200]
                        # 如果上下文说"已上市"但数据标记为非上市
                        if re.search(r'(已上市|上市公司|IPO|挂牌)', context):
                            errors.append("'%s'在unlisted_players.json中标记为非上市，但报告称其已上市" % name)

        # ── 评分 ──
        deduction = len(errors) * 0.1
        score = max(0.0, 1.0 - deduction)
        passed = score >= 0.7

        detail = "评分: %.2f" % score
        if errors:
            detail += " | 错误: %s" % "; ".join(errors[:5])

        return GateCheckResult(name="实体验证", passed=passed, score=score,
                               details=detail, severity="warning")

    def _check_honest_gap(self) -> GateCheckResult:
        """R79 P1-3：诚实留白机制。

        系统原奖励"看起来完整"、惩罚"诚实留白"→ LLM 硬凑数据（Goodhart）。
        本检查：
          1. 奖励：报告对无数据维度显式声明"数据不足/留白" → 加分
          2. 反硬凑：维度无来源标注但写了具体数字 → 降分（疑似编造）
        """
        text = self.report_text or ""
        if not text:
            return GateCheckResult("honest_gap", True, 1.0, "无文本")

        import re
        # 1. 留白声明检测
        gap_decls = re.findall(r'(数据不足[^。]{0,30}|明确留白[^。]{0,30}|无权威数据[^。]{0,30}|难以量化[^。]{0,30})', text)
        # 2. 反硬凑：具体数字但无来源标记（A/B/E/F）
        # 找 "XX亿元" 且附近无 (A)/(B)/(E)/(F) 的段落
        # R82（2026-08-06）：标注形式兼容 (A,来源) / (A） / ，A，柯力传感公告 等紧凑与宽松写法，
        # 并扩展上下文窗口至前后各 20/70 字符，消除"已有标注但被误报"问题。
        hard_fab = []
        # R91（2026-08-10）：来源标注兼容全角括号（（A）/（E））——此前只认半角 (A)，
        # 但 2hao 报告大量使用全角（A）（40处）导致误报"无来源"。
        _src_pat = re.compile(
            r'[\(（][ABEF][,，）)]|[，,]\s*[ABEF][，,]|来源|据|公告|年报|报告'
        )
        for m in re.finditer(r'([^。\n]{0,20}?\d+(?:\.\d+)?\s*(?:亿元|亿美元|万元))', text):
            seg = m.group(1)
            # R92（2026-08-10）：来源上下文窗口扩至"整段"而非前后 20/70 字符。
            # 此前的窄窗口把"2024年营收61.03亿元...（2024年度报告，A）"这种段落级
            # 溯源误报为无来源（来源词在数字后 70 字外）。数字出现在有来源标注的
            # 段落里即为合法引用，非硬凑。整段判断显著降低误报。
            _p_start = text.rfind("\n\n", 0, m.start(1))
            _p_end = text.find("\n\n", m.end(1))
            _para = text[(_p_start if _p_start >= 0 else 0):(_p_end if _p_end >= 0 else len(text))]
            if _src_pat.search(_para):
                continue  # 段落已有来源标注 → 合法
            # 兜底：段落无标注时退回局部窗口判断（兼容短段落）
            ctx = text[max(0, m.start(1) - 20): min(len(text), m.end(1) + 70)]
            if _src_pat.search(ctx):
                continue
            # 排除明显估算词开头的（如"约""预计"）
            if not re.match(r'^(约|预计|估算|大致)', seg.strip()):
                hard_fab.append(seg.strip()[:40])

        if gap_decls and not hard_fab:
            return GateCheckResult(
                "honest_gap", True, 1.0,
                f"诚实留白: {len(gap_decls)} 处声明数据不足并留白（+credit），无硬凑",
                severity="info")
        if hard_fab and len(hard_fab) >= 3:
            return GateCheckResult(
                "honest_gap", False, max(0.1, 0.5 - len(hard_fab) * 0.05),
                f"疑似硬凑数据(P1): {len(hard_fab)} 处具体数字无来源标注——应声明留白或标注来源",
                severity="warning")
        return GateCheckResult("honest_gap", True, 0.8,
                               f"留白声明 {len(gap_decls)} 处；无来源数字 {len(hard_fab)} 处",
                               severity="info")

    def _check_sub_element_coverage(self) -> GateCheckResult:
        """R74（2026-08-05 P0）：子要素覆盖率检查——根治 SAC 覆盖被游戏化。

        R73 审计发现：油位 v6 的 SAC 26/26 覆盖率全是关键词搜索命中，
        14/26 维度仅为软覆盖（有名称但无实质分析）。
        本检查不再用关键词搜索判断维度是否存在，而是按 SAC 维度定义的
        required_sub_elements 对每个子要素做结构性正则匹配——缺一即判 UNCOVERED。
        """
        report_text = getattr(self, "report_text", "")
        if not report_text:
            return GateCheckResult(name="子要素覆盖", passed=False, score=0.0,
                                   details="无报告文本", severity="error")

        try:
            from core.sacs import SACLoader
            sac = SACLoader(self.report_type)
        except Exception:
            return GateCheckResult(name="子要素覆盖", passed=True, score=1.0,
                                   details="SAC 不可用，跳过子要素检查", severity="info")

        all_dims = sac.get_dimension_ids() if hasattr(sac, 'get_dimension_ids') else []
        if not all_dims:
            return GateCheckResult(name="子要素覆盖", passed=True, score=1.0,
                                   details="无维度定义，跳过", severity="info")

        uncovered = []
        covered_count = 0
        total_sub_elements = 0

        for dim_id in all_dims:
            dim = sac.get_dimension(dim_id) if hasattr(sac, 'get_dimension') else {}
            if not isinstance(dim, dict):
                continue
            sub_elems = dim.get("required_sub_elements", [])
            if not sub_elems:
                continue
            # R78（2026-08-05 Phase1.3）：维度裁剪豁免——若报告完全未涉及该维度
            # （连维度名/核心词都不出现），视为 FP8 维度裁剪，其 sub_elements 不计入缺口。
            # 否则"写了维度但缺子要素"仍被拦截，杜绝软覆盖伪装。
            _dim_probe = dim.get("question", "") or dim.get("name", "")
            _probe_words = [w for w in re.findall(r'[一-龥]{2,6}', _dim_probe)[:4] if w]
            if _probe_words and not any(w in report_text for w in _probe_words):
                continue  # 维度被裁剪，豁免其子要素
            total_sub_elements += len(sub_elems)
            dim_uncovered = []
            for pattern in sub_elems:
                if not re.search(pattern, report_text, re.IGNORECASE):
                    dim_uncovered.append(pattern[:50])
                else:
                    covered_count += 1
            if dim_uncovered:
                uncovered.append(f"{dim_id}: 缺{len(dim_uncovered)}/{len(sub_elems)}子要素")

        if total_sub_elements == 0:
            return GateCheckResult(name="子要素覆盖", passed=True, score=1.0,
                                   details="无 required_sub_elements 定义（需补 SAC YAML）", severity="info")

        coverage_ratio = covered_count / total_sub_elements if total_sub_elements > 0 else 1.0
        passed = coverage_ratio >= 0.70
        score = 0.3 + 0.7 * coverage_ratio

        detail = (f"子要素覆盖: {covered_count}/{total_sub_elements} "
                  f"({coverage_ratio:.0%}，阈值70%)")
        if uncovered:
            detail += " | 缺口: " + "; ".join(uncovered[:5])

        return GateCheckResult(name="子要素覆盖", passed=passed, score=score,
                               details=detail, severity="error")

    def _check_client_questions_coverage(self) -> GateCheckResult:
        """R83：委托方必答问题覆盖率检查（decision_memo 核心）。

        油位 v0.89 事故：报告写成了二级市场投资评级报告，委托方（柯力董事长）
        的必答问题（是否卡位/能否放量/久通整合可行性/延伸产业）一个都没回答。

        机制：从 report_planner.build_report_plan 加载委托方问题清单，
        逐条检查正文是否给出了明确回答（按关键词 + 结论信号）。
        decision_memo 类型强制启用；其他类型在注入 --client-questions 时启用。

        severity=error：必答问题未回答即阻断（决策备忘录的核心价值）。
        """
        report_text = getattr(self, "report_text", "")
        if not report_text:
            return GateCheckResult(name="委托方问题覆盖", passed=True, score=1.0,
                                   details="无报告文本", severity="warning")
        try:
            from core.report_planner import build_report_plan
            # R84：优先用 Gate 注入的 client_questions（scheduler 传），
            # 否则退回 report_planner 默认
            _cq = getattr(self, "client_questions", None) or []
            plan = build_report_plan(self.report_type, client_questions=_cq)
            client_qs = plan.get("client_questions", [])
        except Exception as e:
            return GateCheckResult(name="委托方问题覆盖", passed=True, score=0.8,
                                   details=f"规划器不可用: {str(e)[:60]}", severity="warning")
        # decision_memo 之外的类型若无注入问题，不强制（保持后向兼容）
        if self.report_type != "decision_memo" and not client_qs:
            return GateCheckResult(name="委托方问题覆盖", passed=True, score=1.0,
                                   details="非决策备忘录，跳过", severity="warning")

        # 问题→关键词表（用于判断正文是否触及该问题）
        # 对每个必答问题，正文需要出现"问题主题词 + 结论信号"才算回答
        _conclusion_signals = [
            "值得", "不值得", "建议", "可行", "不可行", "判断", "结论",
            "最坏", "损失", "路线", "里程碑", "第一步", "投入", "回报",
            "卡位", "放量", "承接", "进入", "延伸",
        ]
        # 全文是否含结论信号（全局一次判定，避免逐问题重复）
        _has_conclusion = any(sig in report_text for sig in _conclusion_signals)
        # 常见噪声二元组（问题里的连接词/虚词，不参与匹配）
        _noise_bigrams = {
            "如果", "什么", "能否", "如何", "是否", "可以", "需要", "以及",
            "相关", "重点", "进行", "给出", "明确", "具体", "对应", "以及",
        }
        missed = []
        for q in client_qs:
            qcore = q.replace("【委托方必答】", "").strip()
            _strip = re.sub(r'[？?。！：、（）()—–\-]', '，', qcore)
            # 提取 2 字中文二元组作为主题词（宽松但稳健：报告改写表述也能命中）
            _bigrams = set()
            _cn_seq = re.findall(r'[一-鿿]{2,}', _strip)
            for _seg in _cn_seq:
                if len(_seg) < 2:
                    continue
                for _i in range(len(_seg) - 1):
                    _bg = _seg[_i:_i + 2]
                    if _bg not in _noise_bigrams:
                        _bigrams.add(_bg)
            if not _bigrams:
                continue
            _hit_topic = any(bg in report_text for bg in _bigrams)
            if not _hit_topic or not _has_conclusion:
                missed.append(f"{qcore[:30]}")
        if missed:
            return GateCheckResult(
                name="委托方问题覆盖", passed=False,
                score=max(0.1, 1.0 - 0.25 * len(missed)),
                details=f"委托方必答问题未得到明确回答({len(missed)}/{len(client_qs)}): "
                        + "; ".join(missed[:5]),
                severity="error")
        return GateCheckResult(name="委托方问题覆盖", passed=True, score=1.0,
                               details=f"委托方必答问题全部覆盖({len(client_qs)}条)")

    def _check_entity_anchoring(self) -> GateCheckResult:
        """R84：委托方实体锚定检查（decision_memo 核心）。

        油位 v0.90 事故：把"柯力进加油站/危化品油位市场"写成了
        "某制造业上市公司进商用车车规油箱"——委托方匿名、场景换行业、
        对标换人、政策换故事。原因：--client-questions 只注入了必答问题，
        没注入"委托方是谁/场景是什么/不能写成什么"。

        机制：从 report_planner.build_report_plan 读取 must_contain（必须出现的
        实体/场景）与 forbidden_swap（禁止替换成的场景/叙事），逐项核对正文。
        decision_memo 类型强制；其他类型在注入 --client-questions 时启用。

        severity=error：关键实体缺失或禁令场景出现即阻断。
        """
        report_text = getattr(self, "report_text", "")
        if not report_text:
            return GateCheckResult(name="实体锚定", passed=True, score=1.0,
                                   details="无报告文本", severity="warning")
        try:
            from core.report_planner import build_report_plan
            # R84：优先用 Gate 注入的 client_questions（scheduler 传），
            # 否则退回 report_planner 默认（decision_memo 有默认问题但无实体锚定）
            _cq = getattr(self, "client_questions", None) or []
            plan = build_report_plan(self.report_type, client_questions=_cq)
            must_contain = plan.get("must_contain", [])
            forbidden_swap = plan.get("forbidden_swap", [])
        except Exception as e:
            return GateCheckResult(name="实体锚定", passed=True, score=0.8,
                                   details=f"规划器不可用: {str(e)[:60]}", severity="warning")
        if self.report_type != "decision_memo" and not must_contain:
            return GateCheckResult(name="实体锚定", passed=True, score=1.0,
                                   details="非决策备忘录或未注入实体锚定，跳过", severity="warning")

        missing = [ent for ent in must_contain if ent not in report_text]
        present_forbidden = [ent for ent in forbidden_swap if ent in report_text]
        issues = []
        if missing:
            issues.append(f"缺失关键实体({len(missing)}): {', '.join(missing[:5])}")
        if present_forbidden:
            issues.append(f"出现禁止场景({len(present_forbidden)}): {', '.join(present_forbidden[:5])}——可能写错行业/换叙事")
        if issues:
            return GateCheckResult(
                name="实体锚定", passed=False,
                score=max(0.1, 1.0 - 0.2 * (len(missing) + len(present_forbidden))),
                details="委托方实体锚定失败: " + "; ".join(issues),
                severity="error")
        return GateCheckResult(name="实体锚定", passed=True, score=1.0,
                               details=f"委托方实体锚定通过({len(must_contain)}实体必须+{len(forbidden_swap)}禁令)")

    def _check_decision_engine_citation(self) -> GateCheckResult:
        """R84：决策引擎数值引用检查（decision_memo 内容层）。

        油位 v0.90 事故：R83 DecisionEngine 产出确定性结论（卡位3.94/5、
        投入1.5-2亿、最坏损失2亿≈0.6倍净利），但报告一个都没引用，
        自己编了"投入1600-2500万、最坏1650万≈净利2-3%"——量级差10倍。

        机制：对 decision_memo，正文必须出现决策引擎的卡位评分与最坏损失
        金额（确定性计算，LLM 不得自行编造量级）。

        severity=error：决策备忘录缺卡位评分或最坏损失金额即阻断。
        """
        report_text = getattr(self, "report_text", "")
        if self.report_type != "decision_memo":
            return GateCheckResult(name="决策引擎引用", passed=True, score=1.0,
                                   details="非决策备忘录，跳过", severity="warning")
        if not report_text or len(report_text) < 300:
            return GateCheckResult(name="决策引擎引用", passed=True, score=1.0,
                                   details="文本过短跳过", severity="warning")

        missing = []
        # 1. 卡位评分（决策引擎产出的 3.94/5 或相似 X.X/5 模式）
        if not re.search(r'\d\.\d{1,2}\s*/\s*5', report_text):
            missing.append("卡位评分(X.X/5)")
        # 2. 最坏损失金额（必须含"最坏"+"亿/万"金额锚定）
        if not re.search(r'最坏[^。]{0,30}[损失|情景][^。]{0,20}[亿万元]', report_text):
            missing.append("最坏损失金额锚定")
        # 3. 投入金额（含"投入"+"亿/万"）
        if not re.search(r'投入[^。]{0,30}[亿万元]', report_text):
            missing.append("投入金额")
        if missing:
            return GateCheckResult(
                name="决策引擎引用", passed=False,
                score=max(0.1, 1.0 - 0.3 * len(missing)),
                details="决策备忘录缺少决策引擎确定性数值: " + "; ".join(missing)
                        + "——须引用 DecisionEngine 产出，禁止自行编造量级",
                severity="error")
        return GateCheckResult(name="决策引擎引用", passed=True, score=1.0,
                               details="决策引擎数值已引用（卡位评分/最坏损失/投入）")

    def _check_narrative_consistency(self) -> GateCheckResult:
        """R85：叙事一致性检查——防止"答对了问题但答错了生意"。

        油位 v0.90 事故：委托方必答问题覆盖 PASS（四个问题都回答了），
        但全在"商用车车规"语境下——它回答的是另一个行业的生意。
        问题覆盖检查管"答没答"，本检查管"答的是不是对的生意"。

        机制：统计"关键实体集"（委托方真实生意的实体）与"异质实体集"
        （另一个行业/叙事的实体）在正文的出现次数。若异质实体总数
        显著超过关键实体总数（阈值 1.2x），判定叙事漂移 → error 阻断。

        severity=error：叙事漂移即阻断（决策备忘录换行业=交付误导）。
        """
        report_text = getattr(self, "report_text", "")
        if self.report_type != "decision_memo":
            return GateCheckResult(name="叙事一致性", passed=True, score=1.0,
                                   details="非决策备忘录，跳过", severity="warning")
        if not report_text or len(report_text) < 300:
            return GateCheckResult(name="叙事一致性", passed=True, score=1.0,
                                   details="文本过短跳过", severity="warning")

        # 委托方真实生意的场景特定实体（与 enrich 数据一致，非行业泛词）
        # 用"场景特定词"而非"油位/液位"等泛词——泛词无法区分加油站生意 vs 车规生意
        _key_entities = ["加油站", "危化品", "防渗改造", "华虹", "久通", "磁致伸缩",
                         "托肯恒山", "富仁高科", "TDK", "中石化", "储运", "罐车",
                         "双层罐", "替换窗口", "SIS", "物位"]
        # 另一个行业的异质实体（enrich 未提供的叙事）
        _foreign_entities = ["商用车", "车规", "汽车油箱", "国四", "整车厂", "IATF16949",
                             "苏奥传感", "奥联电子", "武汉凡谷", "燃油车", "乘用车",
                             "工程机械", "挖掘机", "尿素", "DPF", "SCR"]

        _key_cnt = sum(report_text.count(e) for e in _key_entities)
        _foreign_cnt = sum(report_text.count(e) for e in _foreign_entities)
        # 关键实体至少出现一次才做比较（否则数据都没用上）
        if _key_cnt == 0:
            return GateCheckResult(name="叙事一致性", passed=False, score=0.1,
                                   details=f"关键实体 0 次出现——报告未使用委托方生意的任何数据",
                                   severity="error")
        if _foreign_cnt > _key_cnt * 1.2:
            return GateCheckResult(
                name="叙事一致性", passed=False,
                score=max(0.1, 1.0 - 0.15 * (_foreign_cnt / max(_key_cnt, 1))),
                details=f"叙事漂移: 异质实体({_foreign_cnt}次)超过关键实体({_key_cnt}次)1.2倍——"
                        f"报告可能在讲另一个行业(如商用车车规)，而非委托方的加油站/危化品油位生意",
                severity="error")
        return GateCheckResult(name="叙事一致性", passed=True, score=1.0,
                               details=f"叙事一致(关键{_key_cnt}次 vs 异质{_foreign_cnt}次)")

    def _check_data_point_citation(self) -> GateCheckResult:
        """R85：数据点引用审计——enrich 关键数值/实体必须出现在正文。

        油位 v0.90：全球46亿/中国166亿进去了，但竞争真相(托肯恒山)、
        卡脖子(TDK)、政策(防渗改造)、委托方实体(华虹/久通)全没进。
        本检查从 enrich 提取关键数据点，验证正文有引用。

        severity=error：关键数据点缺失即阻断（数据继承失败的硬信号）。
        """
        report_text = getattr(self, "report_text", "")
        if self.report_type != "decision_memo":
            return GateCheckResult(name="数据点引用", passed=True, score=1.0,
                                   details="非决策备忘录，跳过", severity="warning")
        if not report_text or len(report_text) < 300:
            return GateCheckResult(name="数据点引用", passed=True, score=1.0,
                                   details="文本过短跳过", severity="warning")

        # 关键数据点：数值 + 实体（来自 enrich v086 与 DecisionEngine）
        data_points = [
            ("全球规模46亿美元", ["46亿", "46亿美元"]),
            ("中国规模166亿", ["166亿", "166"]),
            ("华虹科技", ["华虹"]),
            ("久通物联", ["久通"]),
            ("托肯恒山", ["托肯恒山"]),
            ("磁致伸缩丝", ["磁致伸缩"]),
            ("防渗改造", ["防渗改造", "双层罐"]),
            ("危化品", ["危化品"]),
            ("柯力传感", ["柯力"]),
            ("卡位评分", [r"\d\.\d\s*/\s*5"]),
            ("最坏损失金额", ["最坏"]),
        ]
        missing = []
        for label, patterns in data_points:
            if not any(re.search(p, report_text) if p.startswith("\\") else p in report_text
                       for p in patterns):
                missing.append(label)

        if len(missing) > 3:  # 允许少量缺失（如评分正则边界），>3 视为数据继承失败
            return GateCheckResult(
                name="数据点引用", passed=False,
                score=max(0.1, 1.0 - 0.15 * len(missing)),
                details=f"关键数据点缺失({len(missing)}/{len(data_points)}): " + "; ".join(missing[:6])
                        + "——enrich 数据未继承进正文",
                severity="error")
        return GateCheckResult(name="数据点引用", passed=True, score=1.0,
                               details=f"关键数据点已引用({len(data_points)-len(missing)}/{len(data_points)})")

    def _check_source_reliability(self) -> GateCheckResult:
        """R87：数据源可信度检查——门禁锚定的 enrich 数据本身必须可信。

        油位 v1.0 元问题：enrich v086 含幻觉(TDK垄断/2019防渗62%/华虹油位产线)，
        而 R85 门禁把它当权威锚点。本检查引入 source_level：
          verified   = 与外部事实一致，可作硬锚点
          corrected  = 已修正的幻觉，报告应采用修正值而非原幻觉值
          unverified = 内部测算，报告应标注(E)不得冒充权威

        当 enrich 数据标注 corrected/unverified 时：
          - 报告采用修正值(如爱知制钢/VAC 而非 TDK)→ 应 PASS(允许修正)
          - 报告仍用原幻觉值(TDK)→ FAIL(沿用不可靠数据)
        这解决"Garbage In Garbage Out"——门禁能识别 enrich 本身不可靠时
        报告该用修正值。

        severity=error：报告沿用已知幻觉值即阻断。
        """
        report_text = getattr(self, "report_text", "")
        if self.report_type != "decision_memo":
            return GateCheckResult(name="数据源可信度", passed=True, score=1.0,
                                   details="非决策备忘录，跳过", severity="warning")
        if not report_text or len(report_text) < 300:
            return GateCheckResult(name="数据源可信度", passed=True, score=1.0,
                                   details="文本过短跳过", severity="warning")

        # 已知幻觉对（原幻觉值 → 修正值）。报告若含原幻觉值且缺修正值 → FAIL。
        # 来源：R87 enrich v087_corrected 的 correction_note
        _corrections = [
            ("TDK", "爱知制钢|VAC"),          # 磁致伸缩波导丝：TDK垄断(幻觉) → 爱知制钢/VAC主导(正确)
            ("2019.*防渗|防渗改造.*2019", "水十条"),  # 政策：2019防渗62%(幻觉) → 2015水十条(正确)
        ]
        issues = []
        for _fake_pat, _correct_pat in _corrections:
            _fake_hit = re.search(_fake_pat, report_text)
            _correct_hit = re.search(_correct_pat, report_text)
            if _fake_hit and not _correct_hit:
                issues.append(f"沿用已修正的幻觉值[{_fake_pat}](应改用{_correct_pat})")
            elif _fake_hit and _correct_hit:
                # 两者并存 → 警告（可能是对比论证，放行）
                issues.append(f"幻觉值[{_fake_pat}]与修正值并存，需确认是否对比语境")
        # 华虹主业：若报告断言华虹有油位产线/IATF16949已有，且无"需另取/新建"声明 → 疑似沿用幻觉
        if re.search(r"华虹[^。]{0,30}(已有.*(油位|IATF)|现有.*产线)", report_text) and \
           not re.search(r"华虹[^。]{0,40}(需另取|需新建|矿山物联网)", report_text):
            issues.append("华虹产能/认证断言需核实(疑似沿用'华虹有油位产线'幻觉)")

        if issues:
            return GateCheckResult(
                name="数据源可信度", passed=False,
                score=max(0.1, 1.0 - 0.25 * len(issues)),
                details="数据源可信度问题: " + "; ".join(issues[:5])
                        + "——enrich 已标注 corrected/unverified，报告应改用修正值或标注(E)",
                severity="error")
        return GateCheckResult(name="数据源可信度", passed=True, score=1.0,
                               details="数据源可信度通过(未沿用已知幻觉值)")

    def _check_industry_baseline_gap(self) -> GateCheckResult:
        """行业底座缺口提示（R77 P0-2，warning 级）。

        报告涉及的行业在 unlisted_players.json 中缺条目 → 底座可能漏行业。
        这是"覆盖意识"从 checklist 到 staleness detection 的一部分：
        报告可能写得完整，但数据底座本身就有行业空白——提示补采，不硬阻断。

        severity=warning：不阻断报告（主判断链完整即可交付），但把缺口显性化，
        供复盘/补采调度使用。
        """
        report_text = getattr(self, "report_text", "")
        if not report_text:
            return GateCheckResult(name="行业底座缺口", passed=True, score=1.0,
                                   details="无报告文本", severity="warning")

        unlisted = _load_unlisted_players()
        industry_keys = set(unlisted.keys())

        # 从报告文本中推断行业线索（行业名关键词），对照底座键
        # 用报告头部行业名 + SAC 行业标签，避免全文扫描误报
        _industry_hints = []
        # 从 report_type/asset 元信息（过滤"未知标的"等占位资产名）
        asset = getattr(self, "asset", "") or ""
        if asset and "未知" not in asset and "unknown" not in asset.lower():
            _industry_hints.append(asset)
        # 从报告前 2000 字找 "XX行业/XX传感器" 等
        head = report_text[:2000]
        for m in re.finditer(r'([一-龥]{2,8}?(?:传感器|仪表|设备|物流|芯片|医药|机器人|电池|算力|材料|软件|消费|汽车|光伏|风电|储能))行业?', head):
            kw = m.group(1)
            if kw not in _industry_hints:
                _industry_hints.append(kw)

        # 检查 hint 是否与底座键匹配（完全一致 或 包含关系）
        missing = []
        for hint in _industry_hints:
            matched = any(hint == k or hint in k or k in hint for k in industry_keys)
            if not matched:
                missing.append(hint)

        if missing:
            detail = ("行业底座缺口（unlisted_players.json 缺条目）: " +
                      ", ".join(missing[:5]) +
                      "——建议补采该行业非上市玩家清单，覆盖检查参考价值受限")
            return GateCheckResult(name="行业底座缺口", passed=True, score=0.5,
                                   details=detail, severity="warning")
        return GateCheckResult(name="行业底座缺口", passed=True, score=1.0,
                               details="行业底座覆盖正常", severity="warning")
