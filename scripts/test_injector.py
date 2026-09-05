#!/usr/bin/env python
"""Test exemplar injector with sample data."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\Claude\projects\2hao-analyst\scripts")))
from exemplar_injector import ExemplarInjector

# Sample company data (simplified)
sample_data = {
    "公司名称": "示例银行",
    "股票代码": "600000.SS",
    "行业": "银行",
    "财务数据": {
        "营业收入": "1000亿元",
        "净利润": "200亿元",
        "同比增长": "5.2%",
        "毛利率": "45.3%",
        "ROE": "12.5%",
        "资产负债率": "92.1%",
        "经营现金流": "300亿元",
    },
}

injector = ExemplarInjector()

# Test single section
print("=" * 60)
print("Test 1: Single section - 利润表分析")
print("=" * 60)
prompt = injector.build_prompt(
    section="利润表分析",
    company_data=json.dumps(sample_data, indent=2, ensure_ascii=False),
    company_name="示例银行",
    target_stock="600000.SS",
    n_exemplars=2,
)
print(prompt[:2000])
print("...")

# Test multi-section
print("\n" + "=" * 60)
print("Test 2: Multi-section prompts")
print("=" * 60)
sections = ["利润表分析", "风险提示", "投资建议报告"]
prompts = injector.build_multi_section_prompt(
    sections=sections,
    company_data=json.dumps(sample_data, indent=2, ensure_ascii=False),
    company_name="示例银行",
    target_stock="600000.SS",
)
for section, prompt in prompts.items():
    print(f"\n{section}: {len(prompt)} chars")
    # Show first 200 chars of exemplar section
    if "参考示例" in prompt:
        idx = prompt.index("参考示例")
        print(f"  Exemplars start at char {idx}")
        print(f"  Preview: {prompt[idx : idx + 200]}...")
