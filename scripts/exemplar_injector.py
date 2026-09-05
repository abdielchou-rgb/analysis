#!/usr/bin/env python
"""
Exemplar injection for SAC section_writer.

Generates prompts with diversity-aware exemplars injected,
ready for the section_writer to produce analyst-style output.

Usage:
    from scripts.exemplar_injector import ExemplarInjector
    injector = ExemplarInjector()
    prompt = injector.build_prompt(
        section="利润表分析",
        company_data={...},
        sector="银行",
        target_stock="600036.SS"
    )
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(r"D:\Claude\projects\2hao-analyst\scripts")))
from exemplar_retriever import ExemplarRetriever


class ExemplarSanitizer:
    """Clean external exemplar content before injection."""

    # Sensitive patterns to strip
    SENSITIVE_PATTERNS = [
        r"(?i)(ai\s*生成|ai\s*辅助|ai\s*generated|ai\s*assisted|artificial\s*intelligence|machine\s*learning\s*output)",
        r"(?i)(genuinely|honestly|straightforwardly)",
        r"本次分析由.*模型.*生成",
        r"数据来源：.*互联网.*抓取",
    ]

    # Placeholder patterns (must not appear)
    PLACEHOLDER_PATTERNS = [
        r"\{?\{?tp_primary\}?\}?",
        r"\[?E\d+\]?",
        r"【结论\d+】",
        r"占位符",
    ]

    @classmethod
    def sanitize(cls, text: str, max_length: int = 500) -> str:
        """Clean exemplar text for safe injection."""
        if not text:
            return ""

        # Remove sensitive patterns
        for pattern in cls.SENSITIVE_PATTERNS:
            text = re.sub(pattern, "", text)

        # Remove placeholder patterns
        for pattern in cls.PLACEHOLDER_PATTERNS:
            text = re.sub(pattern, "...", text)

        # Truncate to max_length (accounting for "..." suffix)
        if len(text) > max_length:
            text = text[: max_length - 3] + "..."

        return text.strip()


# SAC section writing prompts (simplified versions)
SECTION_PROMPTS = {
    "利润表分析": """你是一位资深投资银行分析师（高盛风格），正在分析{company}的利润表。

请基于以下财务数据，撰写专业的利润表分析：

{company_data}

要求：
1. 每节开头100字符内必须有判断词（"我们认为""核心判断"）
2. 使用"这意味着""根源在于""导致"等连接词
3. 关键数据点必须有来源标注
4. 每个分析板块末尾给出投资含义（So What链）
5. 语言果断、前瞻，强调宏观因素

{exemplars}""",
    "资产负债表分析": """你是一位资深投资银行分析师（高盛风格），正在分析{company}的资产负债表。

请基于以下财务数据，撰写专业的资产负债表分析：

{company_data}

要求：
1. 分析资产结构、负债水平、偿债能力
2. 关注有息负债率、流动比率、速动比率
3. 识别资产负债表中的风险信号
4. 给出投资含义

{exemplars}""",
    "现金流量表分析": """你是一位资深投资银行分析师（高盛风格），正在分析{company}的现金流量表。

请基于以下财务数据，撰写专业的现金流量表分析：

{company_data}

要求：
1. 分析经营/投资/筹资三大现金流
2. 关注自由现金流（FCF）
3. 识别现金流质量（经营现金流 vs 净利润）
4. 给出投资含义

{exemplars}""",
    "财务综述": """你是一位资深投资银行分析师（高盛风格），正在撰写{company}的财务综述。

请基于以下三表数据，撰写综合财务分析：

{company_data}

要求：
1. 综合利润表、资产负债表、现金流的关键发现
2. 评估财务健康度（盈利能力、偿债能力、运营效率）
3. 识别核心财务风险
4. 给出投资含义

{exemplars}""",
    "投资建议报告": """你是一位资深投资银行分析师（高盛风格），正在撰写{company}的投资建议报告。

请基于以下数据，撰写专业的投资建议：

{company_data}

要求：
1. 给出明确的投资评级（买入/增持/中性/减持/卖出）
2. 给出目标价及估值方法
3. 列出核心催化剂
4. 说明投资逻辑

{exemplars}""",
    "趋势分析": """你是一位资深投资银行分析师（高盛风格），正在分析{company}的股价趋势。

请基于以下数据，撰写趋势分析：

{company_data}

要求：
1. 分析当前股价位置（相对估值、技术面）
2. 识别催化剂和风险
3. 给出未来3-6个月展望
4. 说明与大盘/行业的相对表现

{exemplars}""",
    "风险提示": """你是一位资深投资银行分析师（高盛风格），正在识别{company}的核心风险。

请基于以下数据，撰写风险提示：

{company_data}

要求：
1. 识别3-5个核心风险因素
2. 按影响程度排序
3. 说明每个风险的触发条件和潜在影响
4. 给出风险缓释建议

{exemplars}""",
    "新闻综述": """你是一位资深投资银行分析师（高盛风格），正在分析{company}的近期新闻。

请基于以下新闻数据，撰写新闻综述：

{company_data}

要求：
1. 识别最重要的3-5条新闻
2. 分析每条新闻对公司的潜在影响
3. 判断市场是否已充分反映
4. 给出投资含义

{exemplars}""",
    "新闻分析": """你是一位资深投资银行分析师（高盛风格），正在深度分析{company}的新闻事件。

请基于以下新闻数据，撰写深度分析：

{company_data}

要求：
1. 分析新闻事件的背景和原因
2. 评估对公司的短期和长期影响
3. 识别市场预期差
4. 给出投资含义

{exemplars}""",
}


class ExemplarInjector:
    """Inject exemplars into SAC section_writer prompts."""

    def __init__(self):
        self.retriever = ExemplarRetriever()

    def build_prompt(
        self,
        section: str,
        company_data: str,
        company_name: str = "该公司",
        sector: Optional[str] = None,
        target_stock: Optional[str] = None,
        n_exemplars: int = 3,
        exemplar_tier: str = "mixed",
    ) -> str:
        """Build a prompt with exemplars injected.

        Args:
            section: SAC section name (e.g., "利润表分析")
            company_data: Financial data for the target company
            company_name: Company name for the prompt
            sector: Optional sector filter for exemplars
            target_stock: Stock code to exclude from exemplars
            n_exemplars: Number of exemplars to inject
            exemplar_tier: "top", "mixed", or "random"

        Returns:
            Complete prompt with exemplars injected
        """
        # Get exemplars
        exclude = {target_stock} if target_stock else None
        exemplars = self.retriever.retrieve(
            section=section,
            n=n_exemplars,
            sector=sector,
            exclude_stocks=exclude,
            quality_tier=exemplar_tier,
        )

        # Format exemplars
        exemplar_text = self._format_exemplars(exemplars)

        # Get base prompt
        prompt_template = SECTION_PROMPTS.get(section, SECTION_PROMPTS["财务综述"])

        # Inject values
        prompt = prompt_template.format(
            company=company_name,
            company_data=company_data,
            exemplars=exemplar_text,
        )

        return prompt

    def _format_exemplars(self, exemplars: list) -> str:
        """Format exemplars for prompt injection (with sanitization)."""
        if not exemplars:
            return ""

        lines = ["## 参考示例（资深分析师写作风格，仅供风格参考，数据不可信）", ""]
        for i, ex in enumerate(exemplars):
            lines.append(f"### 示例 {i + 1}（{ex['stock_code']}）")
            lines.append("")

            # Output (sanitized)
            out = ex["output_raw"]
            out = ExemplarSanitizer.sanitize(out, max_length=400)

            try:
                parsed = json.loads(out)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if isinstance(v, str):
                            v = ExemplarSanitizer.sanitize(v, max_length=200)
                            lines.append(f"**{k}**: {v}")
                        elif isinstance(v, list):
                            lines.append(f"**{k}**:")
                            for item in v[:3]:  # Limit to 3 items
                                item_str = str(item)[:100]
                                lines.append(f"- {item_str}")
                        else:
                            lines.append(f"**{k}**: {v}")
                else:
                    lines.append(out)
            except (json.JSONDecodeError, ValueError):
                lines.append(out)

            lines.append("")

        return "\n".join(lines)

    def build_multi_section_prompt(
        self,
        sections: list,
        company_data: str,
        company_name: str = "该公司",
        sector: Optional[str] = None,
        target_stock: Optional[str] = None,
    ) -> dict:
        """Build prompts for multiple sections at once.

        Returns:
            Dict mapping section name to prompt
        """
        prompts = {}
        for section in sections:
            prompts[section] = self.build_prompt(
                section=section,
                company_data=company_data,
                company_name=company_name,
                sector=sector,
                target_stock=target_stock,
            )
        return prompts


# ── CLI interface ─────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Exemplar injection for SAC pipeline")
    parser.add_argument("--section", required=True, help="Section name")
    parser.add_argument("--data", required=True, help="Path to company data JSON")
    parser.add_argument("--company", default="该公司", help="Company name")
    parser.add_argument("--sector", help="Optional sector filter")
    parser.add_argument("--stock", help="Target stock code (to exclude from exemplars)")
    parser.add_argument("--n", type=int, default=3, help="Number of exemplars")
    args = parser.parse_args()

    injector = ExemplarInjector()

    with open(args.data, encoding="utf-8") as f:
        company_data = json.dumps(json.load(f), indent=2, ensure_ascii=False)

    prompt = injector.build_prompt(
        section=args.section,
        company_data=company_data,
        company_name=args.company,
        sector=args.sector,
        target_stock=args.stock,
        n_exemplars=args.n,
    )

    print(prompt)


if __name__ == "__main__":
    main()
