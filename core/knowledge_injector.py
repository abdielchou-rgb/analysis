#!/usr/bin/env python3
"""知识集成器 — 将吸收的知识注入到管线执行中"""
import json, logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("2hao.knowledge_injector")

class KnowledgeInjector:
    """知识注入器：加载知识文件并提供给管线使用"""
    
    _cache = {}
    
    @classmethod
    def get_valuation_baseline(cls, industry=None):
        """获取估值参数基线
        Args:
            industry: 行业英文标识(semiconductor/pharma/consumer等)，None时返回全部
        Returns:
            dict: 行业参数或全部参数
        """
        data = cls._load('valuation_baselines.json')
        if industry:
            return data.get(industry, {})
        return data
    
    @classmethod
    def get_style_profile(cls, style_id):
        """获取机构风格指纹
        Args:
            style_id: 风格标识(goldman_sachs/mckinsey/cicc等)
        Returns:
            dict: 风格配置或None
        """
        data = cls._load('enhanced_profiles.json')
        return data.get(style_id)
    
    @classmethod
    def get_default_wacc(cls, industry):
        """获取行业默认WACC"""
        bl = cls.get_valuation_baseline(industry)
        if bl:
            return bl.get('wacc', {}).get('default', 9.0)
        return 9.0
    
    @classmethod
    def get_industry_by_company(cls, company_name):
        """根据公司名推断行业"""
        industry_keywords = {
            'semiconductor': ['中芯国际','紫光','华虹','长电','北方华创','中微'],
            'pharma': ['恒瑞','华兰','爱尔','片仔癀','智飞','药明','康龙'],
            'consumer': ['伊利','海天','格力','美的','老板电器','茅台','五粮液'],
            'financial': ['中信证券','招商银行','中国平安','工商银行','建设银行'],
            'auto': ['比亚迪','宁德时代','上汽','长城','吉利','理想','小鹏'],
            'real_estate': ['万科','保利','碧桂园','华润置地','龙湖'],
            'resources': ['紫金矿业','中国神华','江西铜业','中国铝业','洛阳钼业'],
            'tech': ['海康威视','用友','科大讯飞','立讯精密','韦尔','金山'],
        }
        for ind, kws in industry_keywords.items():
            if any(kw in company_name for kw in kws):
                return ind
        return None
    
    @classmethod
    def enrich_writing_prompt(cls, prompt, style_override):
        """用风格指纹增强写作提示"""
        profile = cls.get_style_profile(style_override)
        if not profile:
            return prompt
        
        style_section = "\n[STYLE PROFILE - 必须遵循的写作风格]\n"
        markers = profile.get('markers', [])
        if markers:
            style_section += "语言标记(至少使用3个): " + "、".join(markers) + "\n"
        
        depth = profile.get('so_what_depth', 3)
        style_section += f"So What链深度: 至少{depth}层(数据→分析→判断→建议)\n"
        
        density = profile.get('data_density', 'high')
        style_section += f"数据密度: {density}(每段至少1个具体数据)\n"
        
        pre_b = profile.get('pre_burttal', 0.7)
        style_section += f"反方论证率: 至少{int(pre_b*100)}%的判断需要有反方论证\n"
        
        sections = profile.get('sections', [])
        if sections:
            style_section += "推荐章节结构: " + " → ".join(sections) + "\n"
        
        style_section += "[END STYLE PROFILE]\n"
        
        # Inject after the first paragraph of the prompt
        lines = prompt.split('\n')
        if len(lines) > 3:
            lines.insert(3, style_section)
        else:
            lines.append(style_section)
        
        return '\n'.join(lines)
    
    @classmethod
    def _load(cls, filename):
        """加载知识文件(缓存)"""
        if filename in cls._cache:
            return cls._cache[filename]
        
        paths = {
            'valuation_baselines.json': _ROOT / 'core' / 'knowledge' / filename,
            'enhanced_profiles.json': _ROOT / 'core' / 'styles' / filename,
        }
        fp = paths.get(filename)
        if not fp or not fp.exists():
            logger.warning(f"Knowledge file not found: {filename}")
            return {}
        
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cls._cache[filename] = data
            return data
        except Exception as e:
            logger.warning(f"Failed to load {filename}: {e}")
            return {}


def inject_knowledge(prompt, style_override=""):
    """便利函数：知识注入"""
    ki = KnowledgeInjector()
    return ki.enrich_writing_prompt(prompt, style_override)
