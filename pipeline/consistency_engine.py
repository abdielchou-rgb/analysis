# -*- coding: utf-8 -*-
"""consistency_engine.py — 跨段数值一致性检查引擎（2026-07-31 P0-B 修复 + R2 误报治理）

Iron Gate 之前的 22 项检查全部是"表面特征扫描"，没有一项覆盖
"跨段数值一致性"——同一指标（市场规模/单台成本/目标价/评级/决策门）
在不同章节出现多套数字时，Gate 无法感知，导致 7 处 P0 数据矛盾全部漏检。

本引擎从报告文本中提取数值并做语义聚类，检测同簇冲突。

R2 误报治理（2026-07-31 Marvis 审计）：
  1. 币种/单位归一化：比较前统一换算（亿美元×7→亿元），不同单位不误比
  2. 负向断言改句子语义：市场规模_全球 只看"全球/国际"主语句子，
     前 40 字含"中国/国内"的句子归入中国簇
  3. 占比精确分组：完整指标名分簇，不同指标不混比
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# ── 币种/单位归一化 ────────────────────────────────────────
# 统一换算到"亿元"
UNIT_TO_YI = {
    "亿元": 1.0,
    "亿美元": 7.0,   # 假设汇率 1:7
    "万元": 1e-4,
    "亿美元": 7.0,
    "万亿": 1e4,
    "元": 1e-8,
}


def normalize_to_yi(num: float, unit: str) -> float:
    """按单位换算为亿元。未知单位返回原值（不强换算）。

    R6（2026-07-31 Marvis 二轮审计）：未知单位的数据点不应静默裸比，
    需标记以便调用方感知。返回换算后的值，单位未知时用 None 标记。
    """
    factor = UNIT_TO_YI.get(unit, None)
    if factor is None:
        return num  # 未知单位不强换算
    return num * factor


@dataclass
class ValueCluster:
    """一个语义簇：同一指标在全文出现的所有数值"""
    label: str
    values: List[Tuple[str, str, str, str]] = field(default_factory=list)  # [(value_str, unit, year, context)]
    threshold_ratio: float = 0.3  # 偏差超过 30% 判定冲突

    def conflicts(self) -> List[str]:
        """检测簇内数值冲突（币种归一化 + 年份感知后比较）。

        年份规则：同簇内两个数值若都有明确的不同年份标注（如 2025A vs 2026E），
        视为不同时期的合理差异，不判冲突。只有"同一时期口径下数值打架"才算矛盾。
        返回冲突描述列表。
        """
        if len(self.values) < 2:
            return []
        # 解析数值 + 单位 + 年份，归一化到亿元
        nums = []
        for v_str, unit, year, ctx in self.values:
            try:
                m = re.search(r'(\d+\.?\d*)', v_str)
                if m:
                    raw = float(m.group(1))
                    # R6：未知单位（如 PS 倍数、无单位数据）→ 不参与跨单位归一化比较，
                    # 直接按原始数值比较（同簇内单位应一致）
                    factor = UNIT_TO_YI.get(unit, None)
                    if factor is None:
                        # 未知单位：按原始值比较，标记未归一化
                        nums.append((raw, raw, unit, year, v_str, ctx, True))
                    else:
                        nums.append((raw * factor, raw, unit, year, v_str, ctx, False))
            except (ValueError, TypeError):
                continue
        if len(nums) < 2:
            return []
        # 基准 = 最大值
        base = max(nums, key=lambda x: x[0])
        conflicts = []
        for n in nums:
            if n[0] == base[0]:
                continue
            # 年份感知：若两者都有明确不同年份 → 跨年合理差异，跳过
            if n[3] and base[3] and n[3] != base[3]:
                continue
            # R6：未知单位数据点（PS倍数/无单位）直接按原值比较，与同簇已知单位不裸比
            # （PS 8.0x vs PS 9.5x 都是无单位，unit 均为空 → 正常比较）
            if n[6] != base[6] and (n[2] or base[2]):
                # 一个已知单位一个未知单位 → 无法可靠比较，跳过并记录
                continue
            ratio = abs(n[0] - base[0]) / max(base[0], 1e-9)
            if ratio > self.threshold_ratio:
                conflicts.append(
                    f"'{self.label}' 数值冲突: {n[4]}{n[2]}({n[5][:28]}) "
                    f"vs {base[4]}{base[2]}({base[5][:28]}) 偏差 {ratio:.0%}")
        return conflicts


class ConsistencyEngine:
    """跨段数值一致性检查引擎"""

    # 语义簇定义：label → (正则pattern, 单位捕获组号, 阈值)
    # threshold: 偏差超过该比例判定冲突。
    # 单位捕获组：正则中第 2 组捕获单位（如 亿美元/亿元）
    # R45（2026-08-02 P0-1）：连接词正则从 (?:约|达|为)? 升级为支持双字——
    # 真实报告高频用"约为/达到/约达/预计达"，单字正则全部漏检 → 勾稽检测失明。
    # 用 (?:约|达|为|约为|达到|约达|预计|预计达|预计为|将达|已达)? 覆盖常见表达。
    _CONN = r'(?:约|达|为|约为|达到|约达|预计|预计达|预计为|将达|已达)?'
    CLUSTERS = [
        # 市场规模（区域前缀组=1 用于分流；派生口径排除；阈值 60%）
        # 格式: (label, pattern, unit_group, threshold, region_group)
        ("市场规模", r'(全球|中国|国内)?(?:具身智能|机器人|AI|市场)规模' + _CONN + r'[：:]?\s*(\d+\.?\d*)\s*(亿美元|亿元|万亿)', 3, 0.6, 1),
        # 单台成本
        ("单台成本", r'(?:单台|单位)(?:成本|售价|价值)' + _CONN + r'[：:]?\s*(\d+\.?\d*)\s*(万元|元)', 2, 0.3),
        # 目标价/评级（多样表达：PS倍数 + 涨幅/提升/下调）
        # R6（2026-07-31 Marvis 二轮审计）：估值倍数/涨幅类同口径强约束，
        # 阈值收紧到 10-15%（PS 8.0x vs 9.5x 偏差 18.75% 必须命中）
        # 修复（2026-08-01 IronGate 第 2 轮）：PS 簇原 pattern 无语境约束，
        # 会把"可比公司倍数（云知声 PS 5x、科大讯飞 PS 8x）"与"目标/估值倍数
        # （对应 PS 8x）"混入同一簇，跨主体误报冲突（思必驰报告
        # "PS 6.5-10x 区间 vs 云知声 PS 5x" 被判冲突）。收紧为仅匹配
        # 目标/估值语境（目标价/给予/估值/对应），可比公司列举不再入簇；
        # R6 目标场景（"目标价 PS 8.0x vs 9.5x"）仍命中。
        ("目标价_PS倍数", r'(?:目标价|目标PS|目标倍数|给予|估值中枢|对应|基于)\s*(?:20\d\d年?|2026E|2027E|2028E)?\s*PS\s*([0-9.]+)\s*[xX倍]', None, 0.10),
        ("目标价_涨幅", r'(?:目标涨幅|目标价.*?(?:涨幅|提升|下调)|隐含市值|较当前提升|对应.*?(?:涨幅|提升)|(?:涨幅|提升)' + _CONN + r')[：:]?\s*([0-9.]+)\s*%', None, 0.10),
        # 目标价金额（元/股）——柯力案发现场："12个月目标价51.60元" vs
        # "综合DCF+PE，12个月目标价48元"。同一报告出现两个目标价金额且
        # 差异>6% 即冲突（投行报告同一综合目标价不应自相矛盾）。
        # 匹配"目标价X元"且"目标价"后紧随金额的强语境，避免把敏感性矩阵
        # （| 8.5% | 40.9 | ... |）或可比公司列举混入。
        # 设计要点：1) "目标价"与数字间仅允许少量修饰词；2) 数字必须紧跟"元"；
        # 3) 阈值 0.06：51.6 vs 48 偏差 7% 命中，但 51.60 vs 51.60 不误报。
        ("目标价金额", r'(?:目标价|目标价位|给予.{0,4}目标价)[^\d]{0,10}(\d{2,3}(?:\.\d+)?)\s*元', None, 0.06),
        # 出货量（区域前缀组=1；与市场规模对称）
        ("出货量", r'(全球|中国|国内)?(?:具身智能|机器人|人形机器人|AI)?(?:出货量|交付量|销量)(?:预计|预|将)?(?:约|达|为|至)?[：:]?\s*(\d+\.?\d*)\s*(万台|台|万部|部)', 3, 0.6, 1),
    ]

    # 占比类：完整指标名分簇
    # R45（2026-08-02 P0-1）：连接词也支持双字（约为/达到/预计达），与 CLUSTERS 的 _CONN 一致
    # R53审计（2026-08-03 P0-2）：加"市占率"——执行者把"市场份额"改成"市占率"即绕过
    #   （RATIO_PATTERN 原只匹配 渗透率|占比|份额，"市占率"不命中）。
    RATIO_PATTERN = r'([一-龥A-Za-z0-9]{1,16}?(?:渗透率|市占率|占比|份额|市场占有率))[：:]?(?:约|达|为|约为|达到|约达|预计|预计达|预计为|将达)?\s*(\d+\.?\d*)\s*%'
    # 同义词簇归一化：不同措辞（市占率/市场份额/市场占有率/份额）归一到同一 canonical 词，
    # 防止"市占率45%"与"市场份额42%"因措辞不同被拆到不同簇而漏检矛盾。
    RATIO_SYNONYM_MAP = [
        (r'市占率', '市占率'),
        (r'市场占有率', '市占率'),
        (r'市场份额', '市占率'),
        (r'份额', '市占率'),
    ]

    def __init__(self, threshold_ratio: float = 0.3):
        self.threshold_ratio = threshold_ratio

    def _split_market_by_sentence(self, text: str, m: re.Match) -> str:
        """按句子语义判断市场规模是"全球"还是"中国"。

        取匹配位置**所在完整句子**（最近句号→下一句号）作为语义窗口，
        避免'中国'出现在更早句子时误分类。
          - 完整句子内含"中国/国内" → 中国簇
          - 否则 → 全球簇
        """
        sent_start = max(0, text.rfind('。', 0, m.start()) + 1,
                         text.rfind('\n', 0, m.start()) + 1)
        sent_end = text.find('。', m.end())
        if sent_end == -1:
            sent_end = min(len(text), m.end() + 120)
        window = text[sent_start:sent_end]
        if re.search(r'中国|国内', window):
            return "市场规模_中国"
        return "市场规模_全球"

    def _split_volume_by_sentence(self, text: str, m: re.Match) -> str:
        """按句子语义判断出货量是"全球"还是"中国"。

        与市场规模对称：取匹配位置所在句，含"中国/国内" → 中国簇。
        """
        start = max(0, text.rfind('。', 0, m.start()) + 1, text.rfind('\n', 0, m.start()) + 1)
        window = text[start:m.start()]
        if re.search(r'中国|国内', window):
            return "出货量_中国"
        return "出货量_全球"

    def check(self, report_text: str) -> Dict:
        """对报告文本执行跨段一致性检查。

        Returns:
            {"passed": bool, "conflicts": [str], "clusters": {label: n_values}}
        """
        if not report_text:
            return {"passed": True, "conflicts": [], "clusters": {}}

        # 1. 按语义簇提取数值
        cluster_map: Dict[str, ValueCluster] = {}
        for item in self.CLUSTERS:
            label, pattern = item[0], item[1]
            unit_group = item[2]
            threshold = item[3] if len(item) > 3 else self.threshold_ratio
            region_group = item[4] if len(item) > 4 else None

            for m in re.finditer(pattern, report_text):
                # 组结构：区域前缀可能在第1组（有区域组时），数字/单位在后
                if region_group is not None:
                    # 有区域捕获组：(区域)(数字)(单位)
                    val_str = m.group(region_group + 1)
                    unit = m.group(region_group + 2)
                    region = m.group(region_group)
                else:
                    val_str = m.group(1)
                    unit = m.group(unit_group) if unit_group and unit_group <= m.re.groups else ""
                    region = ""
                actual_label = label
                # 市场规模按区域分流
                if label == "市场规模":
                    # 派生口径排除：前 15 字含"对应/约合/隐含" → 派生值，跳过
                    before_15 = report_text[max(0, m.start() - 15):m.start()]
                    if re.search(r'对应|约合|隐含|折合', before_15):
                        continue
                    # R84（2026-08-06）：句内过滤强化——排除"若按X%增速建模/预计/预测"的
                    # 未来预测值入当前口径簇（如"若按15%增速建模，2030年中国市场规模将达
                    # 40亿元"是预测值，与当前口径 14.5 亿元不构成矛盾），并排除 SAM/区间
                    # 上界等派生值。
                    if re.search(r'若按|预计|预测|将达|2030|2031|2032', before_15):
                        continue
                    if region:
                        actual_label = f"市场规模_{'中国' if region in ('中国','国内') else '全球'}"
                    else:
                        actual_label = self._split_market_by_sentence(report_text, m)
                elif label == "出货量":
                    # R8：出货量按区域分流，与市场规模对称
                    if region:
                        actual_label = f"出货量_{'中国' if region in ('中国','国内') else '全球'}"
                    else:
                        actual_label = self._split_volume_by_sentence(report_text, m)
                # R9（2026-08-02）：目标价金额按情景前缀分流
                # "基准目标价52元" vs "悲观目标价38元" 属不同情景，非冲突。
                # 在目标价前10字窗口扫描情景限定词，命中则追加 _情景名 后缀。
                elif label == "目标价金额":
                    before_10 = report_text[max(0, m.start() - 10):m.start()]
                    # R88c（2026-08-06）：情景窗口从 10 字扩展至 40 字，
                    # 覆盖"悲观情景（PE压缩至20x）对应目标价27元"——情景词
                    # "悲观情景"位于目标价前 18 字符，"对应"等修饰词夹在中间，
                    # 原 10 字窗口漏检导致双情景披露被判冲突。
                    _scen_win = report_text[max(0, m.start() - 40):m.start()] + m.group(0)
                    scenario = re.search(r'(基准|悲观|乐观|中性|保守|激进|核心|下修|上调|下调|回撤|情景)', _scen_win)
                    if scenario:
                        actual_label = f"目标价金额_{scenario.group(1)}"
                start = max(0, m.start() - 20)
                end = min(len(report_text), m.end() + 20)
                ctx = report_text[start:end].replace('\n', ' ')
                # 年份捕获：匹配前 30 字找最近的 20XX（不是第一个）
                before = report_text[max(0, m.start() - 30):m.start()]
                years = list(re.finditer(r'(20\d{2})', before))
                year = years[-1].group(1) if years else ""
                if actual_label not in cluster_map:
                    cluster_map[actual_label] = ValueCluster(
                        label=actual_label, threshold_ratio=threshold)
                cluster_map[actual_label].values.append((val_str, unit, year, ctx))

        # 2. 占比类：完整指标名分簇
        # R45（2026-08-02 P1-3）：分簇过细——"海外收入占比"vs"柯力传感海外收入占比"
        # 因前缀不同被拆到不同簇，同指标矛盾数值无法互检。
        # 修复：归一化指标名——去掉公司名/主体前缀，只保留核心指标词（如"海外收入占比"）。
        # R53审计（2026-08-03 P0-2）：同义词归一化——市占率/市场份额/市场占有率/份额
        # 归一到"市占率"，防止措辞规避（"市场份额"→"市占率"）绕过检测。
        for m in re.finditer(self.RATIO_PATTERN, report_text):
            metric = m.group(1)
            # 归一化指标名：去掉公司名/主体前缀，只保留核心指标词
            # 核心指标词 = 以"占比/份额/渗透率"结尾的核心短语
            # 剥离逻辑：若含公司名特征（非核心指标词的连续汉字前缀），
            # 只保留"占比/份额/渗透率"前 4-6 字的指标核心。
            core = metric
            # 查找核心指标词（占比/份额/渗透率）前 6 字作为核心
            core_idx = None
            for kw in ("渗透率", "市占率", "占比", "份额", "市场占有率"):
                i = core.find(kw)
                if i > 0:
                    core_idx = i
                    break
            if core_idx is not None:
                core = core[max(0, core_idx - 4):]  # 保留指标词前最多4字
            metric_norm = core
            # 同义词归一化：市占率/市场份额/市场占有率 → 市占率
            for _syn_pat, _canon in self.RATIO_SYNONYM_MAP:
                if re.search(_syn_pat, metric_norm):
                    metric_norm = re.sub(_syn_pat, _canon, metric_norm)
                    break
            val_str = m.group(2)
            start = max(0, m.start() - 20)
            end = min(len(report_text), m.end() + 20)
            ctx = report_text[start:end].replace('\n', ' ')
            before = report_text[max(0, m.start() - 30):m.start()]
            years = list(re.finditer(r'(20\d{2})', before))
            year = years[-1].group(1) if years else ""
            # R81（2026-08-06）：占比类按区域主体分簇——"德国当前智能化渗透率80%"与
            # "中国当前智能化渗透率40%"是不同主体，值不可比，不应判为同一指标冲突。
            # 区域判定取匹配所在句窗口（对标市场规模分流语义）：含海外主体词→_海外簇，
            # 含中国/国内→_中国簇；无区域主体词的保持原簇（现有矛盾检测不降级）。
            _wstart = max(0, report_text.rfind('。', 0, m.start()) + 1,
                          report_text.rfind('\n', 0, m.start()) + 1)
            _window = report_text[_wstart:m.start()]
            _region_suffix = ""
            if re.search(r'德国|美国|日本|欧洲|海外|全球|韩国|英国|法国|意大利', _window):
                _region_suffix = "_海外"
            elif re.search(r'中国|国内', _window):
                _region_suffix = "_中国"
            key = f"占比_{metric_norm}{_region_suffix}"
            if key not in cluster_map:
                cluster_map[key] = ValueCluster(label=key,
                                                threshold_ratio=self.threshold_ratio)
            cluster_map[key].values.append((val_str, "%", year, ctx))

        # 3. 检测每簇冲突
        all_conflicts = []
        for vc in cluster_map.values():
            all_conflicts.extend(vc.conflicts())

        return {
            "passed": len(all_conflicts) == 0,
            "conflicts": all_conflicts,
            "clusters": {label: len(vc.values) for label, vc in cluster_map.items()},
        }


# 便捷入口
def check_consistency(report_text: str) -> Dict:
    """检查报告跨段数值一致性。返回 {"passed", "conflicts", "clusters"}"""
    return ConsistencyEngine().check(report_text)


if __name__ == "__main__":
    import sys
    # 从文件读取报告测试
    if len(sys.argv) > 1:
        text = open(sys.argv[1], encoding='utf-8').read()
        result = ConsistencyEngine().check(text)
        print(f"passed={result['passed']}")
        print(f"clusters: {result['clusters']}")
        for c in result['conflicts']:
            print(f"  [冲突] {c}")
        sys.exit(0 if result['passed'] else 1)
    print("用法: python consistency_engine.py <report.md>")
