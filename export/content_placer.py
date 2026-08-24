"""content_placer.py — Smart image/content placement in reports."""
import re, logging
from pathlib import Path

logger = logging.getLogger("2hao.content_placer")

class ContentPlacer:
    def __init__(self, report_type="listed_company"):
        self.report_type = report_type
        self.SECTION_CHART_MAP = {
            "revenue": ["revenue_structure", "financial_trends"],
            "营收": ["revenue_structure", "financial_trends"],
            "利润": ["profit_margin", "financial_trends"],
            "毛利率": ["profit_margin"],
            "估值": ["valuation_peers"],
            "竞争": ["market_position", "competitive_landscape"],
            "市场份额": ["market_position"],
            "市场地位": ["market_position"],
            "市场规模": ["market_size"],
            "技术": ["tech_trend"],
            "产业链": ["industry_chain"],
            "政策": ["policy_impact"],
            "增长": ["growth_metrics"],
            "商业模式": ["business_model"],
            "竞争力": ["competitive_edge"],
            "风险": ["catalyst_timeline"],
        }
    
    def place_images(self, md_text, chart_paths):
        if not chart_paths:
            return md_text
        lines = md_text.split('\n')
        placed = set()
        result = []
        for line in lines:
            result.append(line)
            section_match = re.match(r'^#{1,3}\s+(.+)$', line)
            if not section_match:
                continue
            section_title = section_match.group(1)
            matched = []
            for keyword, chart_ids in self.SECTION_CHART_MAP.items():
                if keyword in section_title:
                    for cid in chart_ids:
                        if cid in chart_paths and cid not in placed:
                            matched.append(cid)
            for cid in matched[:2]:
                result.append('')
                result.append('![' + cid + '](' + str(chart_paths[cid]) + ')')
                result.append('')
                placed.add(cid)
        remaining = [cid for cid in chart_paths if cid not in placed]
        if remaining:
            result.append('')
            result.append('---')
            result.append('')
            for cid in remaining:
                result.append('![' + cid + '](' + str(chart_paths[cid]) + ')')
        logger.info("ContentPlacer: placed %d/%d inline, %d at end", len(placed), len(chart_paths), len(remaining))
        return '\n'.join(result)
    
    def extract_chart_refs(self, md_text):
        return re.findall(r'!\[([^\]]*)\]\(([^\)]+)\)', md_text)
