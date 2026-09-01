"""S6-4: 敏感信息检测

发布前扫描：
- 未公开财报数据 / 内幕信号 / 未公告并购
- 关键词表 + 数据源交叉（是否来自公开渠道）
- 命中 → 标注"需人工复核"
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sensitive_info_scan")

# 敏感关键词表
SENSITIVE_PATTERNS = {
    "unreleased_financials": [
        r"未披露.*(?:收入|利润|业绩)",
        r"(?:内部|非公开).*(?:数据|信息|财务)",
        r"提前(?:知道|获知|泄露)",
        r"保密.*(?:信息|数据)",
    ],
    "insider_signals": [
        r"知情.*(?:人士|人士透露)",
        r"(?:高管|董事|监事).*(?:透露|告知|暗示)",
        r"内部.*(?:消息|信息|人士)",
        r"即将.*(?:公布|披露|发布).*(?:重大|利好|利空)",
    ],
    "unannounced_ma": [
        r"即将.*(?:收购|合并|重组|并购)",
        r"(?:秘密|私下).*谈判",
        r"未公告.*(?:重大事项|资产重组)",
        r"筹划.*(?:重大|资产).*(?:重组|收购)",
    ],
    "material_info": [
        r"重大.*(?:未公开|未披露).*(?:信息|事项)",
        r"(?:定增|配股|增发).*未公告",
        r"利润.*(?:大幅|重大).*(?:增长|下降|变动)",
    ],
}

# 公开数据源关键词（表明数据可能来自公开渠道）
PUBLIC_SOURCES = [
    "公告", "披露", "年报", "季报", "半年报", "交易所",
    "证监会", "研报", "公开数据", "wind", "同花顺",
    "东方财富", "choice", "akshare", "baostock",
]


def scan_text(text: str, filename: str = "") -> list[dict]:
    """扫描文本中的敏感信息。

    Returns:
        [{"category": str, "matched": str, "context": str, "severity": str}]
    """
    findings = []

    for category, patterns in SENSITIVE_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                # 获取上下文
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].replace("\n", " ")

                # 判断是否有公开来源背书
                has_public_source = any(
                    src in context for src in PUBLIC_SOURCES
                )

                severity = "high" if not has_public_source else "medium"

                findings.append({
                    "category": category,
                    "matched": match.group(0),
                    "context": context,
                    "severity": severity,
                    "file": filename,
                    "recommendation": "需人工复核" if severity == "high" else "建议核实来源",
                })

    return findings


def scan_file(filepath: str | Path) -> list[dict]:
    """扫描单个文件。"""
    fp = Path(filepath)
    if not fp.exists():
        return []

    try:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        return scan_text(text, filename=str(fp.name))
    except Exception as e:
        logger.warning("读取 %s 失败: %s", fp, e)
        return []


def scan_directory(dirpath: str | Path, extensions: tuple = (".md", ".txt", ".py")) -> list[dict]:
    """扫描目录下所有匹配文件。"""
    dp = Path(dirpath)
    all_findings = []

    if not dp.exists():
        return []

    for fp in dp.rglob("*"):
        if fp.suffix.lower() in extensions:
            findings = scan_file(fp)
            all_findings.extend(findings)

    return all_findings


def generate_scan_report(findings: list[dict]) -> str:
    """生成扫描报告。"""
    from datetime import datetime
    lines = [
        f"# 敏感信息扫描报告 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"扫描结果: {len(findings)} 条发现",
        "",
    ]

    if not findings:
        lines.append("✅ 未发现敏感信息")
        return "\n".join(lines)

    high = [f for f in findings if f["severity"] == "high"]
    medium = [f for f in findings if f["severity"] == "medium"]

    if high:
        lines.append(f"## ⚠️ 高风险 ({len(high)} 条)")
        for f in high:
            lines.append(f"- **{f['category']}** [{f['file']}]: {f['matched']}")
            lines.append(f"  上下文: {f['context']}")
            lines.append(f"  建议: {f['recommendation']}")
        lines.append("")

    if medium:
        lines.append(f"## ⚡ 中风险 ({len(medium)} 条)")
        for f in medium:
            lines.append(f"- **{f['category']}** [{f['file']}]: {f['matched']}")
            lines.append(f"  上下文: {f['context']}")
        lines.append("")

    return "\n".join(lines)


def main():
    """扫描 output/ 目录。"""
    import argparse
    parser = argparse.ArgumentParser(description="敏感信息扫描")
    parser.add_argument("--dir", default=str(_ROOT / "output"), help="扫描目录")
    args = parser.parse_args()

    logger.info("=== 敏感信息扫描 ===")
    findings = scan_directory(args.dir)
    logger.info("发现 %d 条", len(findings))

    report = generate_scan_report(findings)
    print(report)


if __name__ == "__main__":
    main()
