"""
2号分析师 统一SAC加载器

单一事实源：所有管线组件从此处加载SAC框架定义，
不再使用硬编码的维度/规则/检查项。

用法：
    from core.sacs import SACLoader
    sac = SACLoader("industry_deep")
    dims = sac.get_dimensions()
    chain = sac.get_logic_chain()
    rhythm = sac.get_writing_rhythm()
    forbidden = sac.get_forbidden_patterns()
    evidence = sac.get_evidence_requirements()
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent

# Report type -> SAC YAML file mapping
_REPORT_TO_SAC = {
    "industry_deep": "sac_industry_deep.yaml",
    "industry": "sac_industry_deep.yaml",
    "listed_company": "sac_listed_company.yaml",
    "unlisted_company": "sac_unlisted_company.yaml",
    "earnings_notes": "sac_earnings_notes.yaml",
    "decision_memo": "sac_decision_memo.yaml",  # R83: 委托方决策备忘录
}

# R83（2026-08-07）：报告用途标签——报告给谁看、用于什么决策
# investor=面向二级市场投资决策（评级/目标价）；board=面向委托方决策者（进/不进/怎么进）
# internal=内部工作文档。用途标签影响模板选择与 Gate 断言（如 board 禁评级目标价）。
_REPORT_PURPOSE = {
    "industry_deep": "investor",
    "industry": "investor",
    "listed_company": "investor",
    "unlisted_company": "investor",
    "earnings_notes": "investor",
    "decision_memo": "board",  # R83: 委托方决策备忘录
}


class SACLoader:
    """Unified SAC framework loader.

    All pipeline components use this loader to get analysis framework definitions.
    If YAML loading fails, returns a basic fallback structure.
    """

    def __init__(self, report_type: str = "industry_deep"):
        self.report_type = report_type
        self._data: dict[str, Any] = {}
        self._loaded = False
        self._load()

    def _load(self) -> None:
        yaml_file = _ROOT / _REPORT_TO_SAC.get(self.report_type, "sac_industry_deep.yaml")
        if not yaml_file.exists():
            self._data = self._fallback()
            self._loaded = False
            return
        try:
            # Try yaml first, then json fallback
            try:
                import yaml

                with open(yaml_file, encoding="utf-8") as f:
                    raw = f.read()
                self._data = yaml.safe_load(raw) or {}
                self._loaded = True
            except ImportError:
                # yaml not available, use built-in parser for simple yaml
                self._data = self._parse_yaml_simple(raw)
                self._loaded = True
        except Exception:
            self._data = self._fallback()
            self._loaded = False

    def _parse_yaml_simple(self, raw: str) -> dict:
        """Simple YAML parser when pyyaml is not available"""
        result = {}
        current_key = None
        current_list = None
        in_list = False
        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" in stripped and not stripped.startswith("-"):
                parts = stripped.split(":", 1)
                key = parts[0].strip()
                value = parts[1].strip()
                current_key = key
                in_list = False
                if value:
                    result[key] = value
                else:
                    result[key] = []
                    current_list = result[key]
            elif stripped.startswith("- "):
                item = stripped[2:].strip()
                if current_key and isinstance(result.get(current_key), list):
                    result[current_key].append(item)
        return result

    def _fallback(self) -> dict:
        return {
            "id": f"sac_{self.report_type}",
            "name": f"{self.report_type} analysis framework",
            "applies_to": [self.report_type],
            "logic_chain": [],
            "required_dimensions": [],
            "writing_rhythm": {"name": "", "description": "", "flow_diagram": "", "principles": []},
            "pre_workflow": [],
            "evidence_requirements": {"min_sources": 3, "primary_source_min": 1, "counter_evidence_required": False},
            "forbidden_patterns": ["AI生成", "AI辅助", "本报告由系统生成"],
        }

    def is_loaded(self) -> bool:
        return self._loaded

    def get_dimensions(self) -> list[dict]:
        return self._data.get("required_dimensions", [])

    def get_dimension_ids(self) -> list[str]:
        return [d["id"] for d in self.get_dimensions() if isinstance(d, dict)]

    def get_dimension(self, dim_id: str) -> dict | None:
        for d in self.get_dimensions():
            if isinstance(d, dict) and d.get("id") == dim_id:
                return d
        return None

    def get_evidence_min(self, dim_id: str) -> int:
        dim = self.get_dimension(dim_id)
        return dim.get("evidence_min", 1) if dim else 1

    def get_logic_chain(self) -> list[dict]:
        return self._data.get("logic_chain", [])

    def get_writing_rhythm(self) -> dict:
        return self._data.get("writing_rhythm", {})

    def get_pre_workflow(self) -> list[dict]:
        return self._data.get("pre_workflow", [])

    def get_evidence_requirements(self) -> dict:
        return self._data.get(
            "evidence_requirements", {"min_sources": 3, "primary_source_min": 1, "counter_evidence_required": False}
        )

    def get_forbidden_patterns(self) -> list[str]:
        return self._data.get("forbidden_patterns", [])

    def get_dimension_keywords(self) -> dict[str, list[str]]:
        """Generate keyword match set for each dimension (for coverage checking)"""
        base_keywords = {
            "bold_call": ["核心判断", "大胆判断", "我们认为", "我们判断", "我们预计"],
            "core_disagreement": ["核心分歧", "市场共识", "分歧", "争议", "我们认为"],
            "industry_boundary": ["行业边界", "产业链", "价值链", "上下游", "覆盖范围"],
            "life_cycle": ["生命周期", "发展阶段", "成长期", "成熟期", "导入期"],
            "policy": ["政策传导", "政策", "环保", "双碳", "监管", "法规"],
            "market_size": ["市场规模", "市场空间", "市场预测", "可及市场"],
            "supply_demand": ["供需", "供给", "需求", "产能", "平衡表"],
            "profit_pool": ["利润池", "利润", "利润率", "盈利", "毛利率", "议价权"],
            "competitive": ["竞争格局", "竞争态势", "市场竞争", "集中度", "进入壁垒"],
            "technology": ["技术路线", "技术演进", "技术趋势", "技术迭代"],
            "capital_market": ["资本市场", "估值", "市盈率", "PE", "PB", "催化剂"],
            "business_model": ["商业模式", "盈利模式", "护城河", "利润驱动"],
            "financial_analysis": ["财务分析", "营收", "利润", "毛利率", "ROE", "财务表现"],
            "competitive_position": ["竞争位置", "份额", "竞争壁垒", "替代风险"],
            "growth_drivers": ["增长驱动", "增长", "量价", "增长可持续"],
            "governance_esg": ["治理", "ESG", "ROIC", "WACC", "关联交易"],
            "valuation_assessment": ["估值", "估值锚", "隐含预期", "反方情景"],
            "falsification": ["证伪", "推翻", "证伪条件", "如果"],
            "catalyst": ["催化剂", "触发", "时间窗口", "事件驱动"],
            "data_declaration": ["数据源声明", "基于", "估计值", "信息缺口"],
            "company_profile": ["公司全称", "注册地", "成立时间", "主营业务"],
            "funding_history": ["融资历程", "股权结构", "实控人", "领投方"],
            "business_kpi": ["业务KPI", "营收规模", "单位经济", "核心用户"],
            "competitive_moat": ["竞争壁垒", "技术壁垒", "品牌", "网络效应", "许可"],
            "valuation_estimate": ["估值", "可比公司", "估值区间", "近期交易"],
            "peer_benchmarking": ["行业对标分析", "同业对比", "同业估值", "可比公司", "同行", "peer"],
            "industry_chain": ["产业链定位", "产业链", "供应链", "价值链", "上下游", "议价权"],
            "exit_cycle_analysis": ["退出窗口", "周期相关", "退出时机", "宏观经济", "IPO窗口", "并购时机"],
            "exit_analysis": ["退出路径", "IPO", "并购", "二级转让"],
            "due_diligence": [
                "尽调清单",
                "待核实",
                "核实方法",
                "优先级",
                "尽调",
                "核实",
                "核查",
                "待核查",
                "核实清单",
            ],
            "headline": ["核心数字", "营收", "利润", "毛利率", "一致预期"],
            "key_surprise": ["超预期", "低于预期", "原因分析", "可持续"],
            "segment_analysis": ["分部分析", "分业务", "分渠道", "分区域"],
            "balance_cashflow": ["资产负债表", "现金流", "应收账款", "存货", "商誉"],
            "outlook_implication": ["管理层指引", "展望", "对估值"],
            "management_quality": ["管理层质量评估", "管理层", "高管", "CEO", "核心团队", "管理团队", "持股"],
            "accounting_penetration": ["会计穿透", "收入确认", "应收账款", "资产减值", "商誉", "审计意见", "资本化"],
            # 2026-08-01 修复：SAC YAML 的 required_dimensions 含以下维度，
            # 但 base_keywords 未映射中文关键词，导致 fallback 成英文 id，
            # 中文报告永远匹配不上 → 必需维度被误判缺失。
            "capital_flow": [
                "资金面",
                "北向",
                "公募持仓",
                "两融",
                "融资融券",
                "股东增减持",
                "主力资金",
                "资金流向",
                "大单净流入",
                "融资",
                "并购",
                "IPO",
                "PIPE",
                "产业资本",
            ],
            "global_peer_comparison": [
                "全球估值",
                "全球可比",
                "国际同业",
                "全球同行",
                "海外可比",
                "全球估值区间",
                "国际估值",
                "全球对标",
            ],
            "overseas_revenue": [
                "海外收入",
                "境外收入",
                "海外营收",
                "境外业务",
                "海外业务",
                "出口占比",
                "海外收入占比",
                "海外区域",
                "汇率变动",
            ],
            "geopolitical_exposure": [
                "地缘",
                "出口管制",
                "实体清单",
                "关税",
                "供应链脱钩",
                "中美科技",
                "制裁",
                "去风险化",
                "跨境风险",
            ],
            "global_market_sizing": [
                "全球市场",
                "分区域",
                "北美市场",
                "欧洲市场",
                "亚太市场",
                "全球规模",
                "全球占比",
                "海外市场",
            ],
            "global_competition": [
                "全球竞争",
                "国际对手",
                "海外竞争者",
                "全球格局",
                "中国vs",
                "国际同行",
                "海外对标",
                "全球排名",
            ],
            "geopolitical_risk": [
                "地缘政治",
                "中美博弈",
                "科技脱钩",
                "贸易壁垒",
                "芯片制裁",
                "出口限制",
                "供应链安全",
                "地缘风险",
            ],
            # R55（2026-08-03）：新增选股传导 + 非上市威胁维度
            "investable_standouts": [
                "选股",
                "受益标的",
                "推荐标的",
                "重点标的",
                "首选",
                "标的排序",
                "买谁",
                "投资评级",
                "目标价",
            ],
            "unlisted_players": [
                "非上市",
                "未上市",
                "非上市玩家",
                "未上市玩家",
                "威胁度",
                "潜在进入者",
                "新进入者威胁",
                "非上市公司",
            ],
            # R57（2026-08-03）：MBB假设驱动 + 并购整合 + ESG实质性
            "core_hypothesis": ["核心假设", "假设", "可证伪", "先行指标", "失效触发", "如果我们是对的", "如果.*错"],
            "industry_consolidation": [
                "并购",
                "整合",
                "整合者",
                "被整合者",
                "行业集中",
                "EV/EBITDA",
                "并购估值",
                "ROIC",
                "WACC",
                "行业终局",
                "寡头",
            ],
            "esg_materiality": [
                "ESG",
                "碳",
                "碳排放",
                "治理风险",
                "实质性",
                "SASB",
                "TCFD",
                "双碳",
                "合规",
                "关联交易",
            ],
            # 2026-08-30 修复：以下 15 个维度关键词不足 5 个，
            # 导致 keyword 匹配失效、SAC 覆盖偏低。补充丰富关键词列表。
            "decision_gate": [
                "决策门",
                "GO",
                "NO-GO",
                "条件性进入",
                "进入",
                "投资决策",
                "建议",
                "判断",
                "结论",
                "值得投资",
                "不予投资",
                "观察",
                "跟踪",
                "暂不推荐",
                "推荐",
                "分析价值",
                "是否值得",
                "进入时机",
                "退出时机",
            ],
            "policy_score": [
                "政策评分",
                "双碳",
                "监管",
                "产业政策",
                "合规",
                "政策支持",
                "政策风险",
                "监管环境",
                "行业政策",
                "政府补贴",
                "税收优惠",
                "环保政策",
                "产业规划",
                "政策确定性",
                "监管不确定性",
            ],
            "founder_team": [
                "创始人",
                "股权激励",
                "高管离职",
                "团队",
                "创始人背景",
                "创始团队",
                "股权结构",
                "管理层",
                "核心团队稳定性",
                "创始人履历",
                "团队完整性",
                "高管激励",
                "人员流动",
                "关键人才",
            ],
            "product_tech": [
                "技术壁垒",
                "IP",
                "专利",
                "壁垒类型",
                "产品",
                "技术领先",
                "产品差异化",
                "研发投入",
                "技术路线",
                "产品竞争力",
                "核心技术",
                "知识产权",
                "产品矩阵",
                "技术护城河",
                "产品优势",
            ],
            "market_traction": [
                "市场验证",
                "客户",
                "合同",
                "收入",
                "商业化",
                "市场接受",
                "客户增长",
                "营收验证",
                "商业化进度",
                "订单",
                "市场反馈",
                "用户增长",
                "收入增速",
                "市场渗透",
            ],
            "capital_efficiency": [
                "资本效率",
                "ROIC",
                "WACC",
                "资金利用率",
                "投入产出",
                "资产周转",
                "资本回报",
                "资金使用效率",
                "IRR",
                "现金转化率",
                "资金消耗",
                "burn rate",
                "单位经济",
                "运营效率",
            ],
            "deal_win_analysis": [
                "deal win",
                "赢单",
                "竞标",
                "客户选择",
                "竞争对手",
                "win rate",
                "pipeline",
                "转化率",
                "成交概率",
                "中标率",
                "客户决策",
                "采购流程",
                "竞争策略",
                "价值主张",
            ],
            "reference_class_forecast": [
                "同类公司",
                "参照公司",
                "对标公司",
                "可比公司",
                "参考估值",
                "peer valuation",
                "benchmark",
                "同业倍数",
                "类比公司",
                "参照历史",
                "行业均值",
                "可比倍数",
                "估值参照",
            ],
            "founder_risk_signals": [
                "创始人风险",
                "股权稀释",
                "质押",
                "关联交易",
                "创始人套现",
                "股权不稳定",
                "控制权风险",
                "关键人风险",
                "团队稳定性",
                "股权争议",
                "创始人离婚",
                "继承人风险",
                "刑事风险",
                "创始人",
                "质押变化",
                "高管离职",
                "股权质押",
            ],
            "milestone_runway_map": [
                "烧钱率",
                "跑道",
                "down round",
                "burn rate",
                "资金消耗",
                "里程碑",
                "下一轮融资",
                "融资时点",
                "估值压力",
                "稀释风险",
                "runway",
                "cash burn",
                "financing round",
                "融资轮次",
                "估值倒挂",
            ],
            "global_benchmark": [
                "全球对标",
                "海外可比",
                "global benchmark",
                "国际对标",
                "跨境对标",
                "跨国比较",
                "全球估值",
                "国际同业",
                "海外标杆",
                "global peer",
                "international benchmark",
                "全球市场份额",
                "海外业务占比",
            ],
            "overseas_expansion": [
                "出海",
                "海外扩张",
                "本地化",
                "国际化",
                "境外业务",
                "海外市场",
                "跨境电商",
                "全球布局",
                "海外收入占比",
                "本土化运营",
                "境外扩张",
                "海外客户",
                "跨国经营",
                "出口",
                "海外渠道",
            ],
            "cross_border_dd": [
                "跨境尽调",
                "海外关联",
                "境外投资",
                "跨国并购",
                "外资审查",
                "境外实体",
                "海外架构",
                "ODI",
                "返程投资",
                "VIE",
                "跨境资金",
                "外汇管制",
                "海外合规",
                "跨境核查",
                "跨境",
                "海外",
                "境外",
                "数据出境",
                "地缘风险",
            ],
            "company_profile": [
                "公司全称",
                "注册资本",
                "成立日期",
                "法定代表人",
                "注册地",
                "主营业务",
                "股东结构",
                "实控人",
                "工商信息",
                "企业性质",
                "公司地址",
                "股权结构图",
                "历史沿革",
                "公司沿革",
                "法人代表",
                "公司",
                "成立",
                "控股",
                "持股比例",
                "创始人",
                "企业性质",
            ],
            "exit_analysis": [
                "退出路径",
                "IPO",
                "并购",
                "二级转让",
                "退出方式",
                "上市预期",
                "IPO可能性",
                "并购机会",
                "股权转让",
                "S基金",
                "退出周期",
                "退出回报",
                "退出时间窗口",
                "IPO窗口",
                "并购估值",
                "退出渠道",
            ],
        }
        result = {}
        for dim in self.get_dimensions():
            if not isinstance(dim, dict):
                continue
            dim_id = dim.get("id", "")
            if not dim_id:
                continue
            keywords = list(base_keywords.get(dim_id, [dim_id]))
            q = dim.get("question", "")
            if q:
                # 2026-08-30 修复：原只取前30字，漏掉问题尾部的关键词；
                # 改为取全问题文本 + sub_questions 列表。
                extra = re.findall(r"[\u4e00-\u9fff]{2,8}", q)
                keywords.extend(extra[:6])
                for sq in dim.get("sub_questions") or []:
                    if isinstance(sq, str):
                        sq_kw = re.findall(r"[\u4e00-\u9fff]{2,8}", sq)
                        keywords.extend(sq_kw[:4])
            result[dim_id] = list(set(keywords))
        return result

    # 权威基线（唯一事实源）——docs/STANDARDS.md
    # 2026-08-01 修复：合并此前双常量（_STANDARDS_MIN/_AUTHORITATIVE_MIN）
    # 为单一权威源，消除外部覆盖残留与自检修复的复杂度。
    _AUTHORITATIVE_MIN = {
        "industry_deep": {"min_charts": 12, "min_tables": 4},
        "listed_company": {"min_charts": 12, "min_tables": 4},
        "unlisted_company": {"min_charts": 3, "min_tables": 2},
        "earnings_notes": {"min_charts": 4, "min_tables": 2},
        "decision_memo": {"min_charts": 4, "min_tables": 3},  # R83: 决策备忘录轻量图
    }

    def _get_authoritative_base(self) -> dict:
        """返回权威基线（docs/STANDARDS.md 12/12/8/4）。

        2026-08-01 修复：合并双常量后，此为唯一标准源。
        外部进程若直接覆盖本类常量，get_chart_config 仍以本内联值兜底。
        """
        return self._AUTHORITATIVE_MIN.get(self.report_type, {})

    def get_chart_config(self) -> dict:
        """Get chart configuration for current report type.

        优先读取 SAC YAML 中的 chart_config；YAML 无配置时**抛错**（fail-fast）。

        2026-08-01 修复 + 加固：
        - 内置硬编码回退改为抛错，配置缺失显性暴露。
        - 标准基线强制层：YAML 中 min_charts/min_tables 若低于权威基线
          （docs/STANDARDS.md: 12/12/8/4），用基线值覆盖。
        - 权威基线 _AUTHORITATIVE_MIN 为唯一事实源，外部覆盖类常量不生效。
        """
        yaml_cc = (self._data or {}).get("chart_config")
        if not (yaml_cc and isinstance(yaml_cc, dict) and yaml_cc.get("charts")):
            raise ValueError(
                f"SAC [{self.report_type}] 缺少 chart_config 配置。"
                f"请先在 core/sacs/sac_{self.report_type}.yaml 补齐 chart_config 段"
                f"（含 min_charts/min_tables/charts），参照 docs/STANDARDS.md 基线。"
                f"禁止依赖硬编码回退（会导致图表标准降级）。"
            )
        # 标准基线强制层：YAML 值低于权威基线 → 用基线值
        base = self._get_authoritative_base()
        if base:
            if int(yaml_cc.get("min_charts", 0)) < base["min_charts"]:
                yaml_cc["min_charts"] = base["min_charts"]
            if int(yaml_cc.get("min_tables", 0)) < base["min_tables"]:
                yaml_cc["min_tables"] = base["min_tables"]
        # 图-维度映射补全（P3 2026-08-01）：listed_company 历史配置缺 maps_to，
        # 在代码层补全，防止图脱离论证链。unlisted/industry/earnings 已在 YAML 标注。
        if self.report_type == "listed_company":
            _maps = {
                "decision_gate": "decision_gate",
                "consensus_vs_deviation": "core_disagreement",
                "revenue_structure": "business_model",
                "business_segments": "business_model",
                "financial_trends": "financial_analysis",
                "profit_margin": "financial_analysis",
                "cash_flow": "financial_analysis",
                "balance_sheet": "financial_analysis",
                "competitive_landscape": "competitive_position",
                "market_position": "competitive_position",
                "moat_analysis": "competitive_position",
                "valuation_peers": "valuation_assessment",
                "peer_comparison": "peer_benchmarking",
                "growth_drivers": "growth_drivers",
                "industry_chain": "business_model",
                "governance_esg": "governance_esg",
                "management_quality": "management_quality",
                "valuation_history": "valuation_assessment",
                "dcf_sensitivity": "valuation_assessment",
                "capital_flow": "capital_flow",
                "catalyst_timeline": "catalyst",
            }
            for _c in yaml_cc.get("charts", []):
                if isinstance(_c, dict) and not _c.get("maps_to"):
                    _c["maps_to"] = _maps.get(_c.get("id"), "")
        return yaml_cc

    def get_section_structure(self) -> str:
        structures = {
            "industry_deep": "## 核心判断\n## 核心分歧\n## 供需分析\n## 利润池与产业链\n## 竞争格局\n## 技术路线\n## 市场空间\n## 政策传导\n## 资本市场映射与投资建议",
            "listed_company": "## 公司概况\n## 财务分析\n## 估值分析\n## 竞争壁垒\n## 管理层评估\n## 风险因素\n## 盈利预测与估值",
            "unlisted_company": "## 公司概况\n## 商业模式\n## 行业定位\n## 竞争分析\n## 增长驱动因素\n## 资本需求与融资路径\n## 退出分析",
            "earnings_notes": "## 核心数字\n## 超预期归因\n## 分部分析\n## 现金流与隐含信号\n## 展望与影响",
            "decision_memo": "## 执行摘要\n## 行业真相\n## 禀赋匹配度\n## 路径决策\n## 财务测算\n## 最坏损失\n## 执行路线图",  # R83
        }
        return structures.get(self.report_type, structures["industry_deep"])

    def get_report_purpose(self) -> str:
        """R83：报告用途标签——investor/board/internal。

        用途决定模板选择与 Gate 断言：
          investor → 面向二级市场，允许评级/目标价
          board    → 面向委托方决策者，禁评级/目标价，强制执行摘要/决策建议/最坏损失/路线图
        """
        return _REPORT_PURPOSE.get(self.report_type, "investor")

    def get_all_config(self) -> dict:
        return {
            "report_type": self.report_type,
            "sac_id": self._data.get("id", ""),
            "is_loaded": self._loaded,
            "logic_chain": self.get_logic_chain(),
            "dimensions": self.get_dimensions(),
            "dimension_ids": self.get_dimension_ids(),
            "writing_rhythm": self.get_writing_rhythm(),
            "pre_workflow": self.get_pre_workflow(),
            "evidence_requirements": self.get_evidence_requirements(),
            "forbidden_patterns": self.get_forbidden_patterns(),
            "dimension_keywords": self.get_dimension_keywords(),
            "chart_config": self.get_chart_config(),
            "section_structure": self.get_section_structure(),
        }


def load_sac(report_type: str = "industry_deep") -> SACLoader:
    return SACLoader(report_type)


def get_dimensions(report_type: str) -> list[dict]:
    return SACLoader(report_type).get_dimensions()


def check_all_sac_files() -> dict[str, bool]:
    results = {}
    for rt, fname in _REPORT_TO_SAC.items():
        fp = _ROOT / fname
        results[rt] = fp.exists()
    return results
