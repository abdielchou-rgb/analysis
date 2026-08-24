#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库全量吸收 — 把 data/知识库/ 各板块规则式提炼为结构化方法论知识。

覆盖板块：
  01-宏观分析框架（已吸收，跳过）
  02-行业与公司研究（行业分析/企业估值/ifind研报/深度报告）
  03-估值与测算（估值模型/Excel测算）
  04-回测基线库（1阶段/金牌分篇）

输出：data/methodology_knowledge_base.json
结构：{ topic: [{title, source_file, topic, summary, methods, indicators, points, judgment_signals}] }

方法：
  - 按 '# ' 顶级标题切分文章
  - 提取报告要点/摘要正文（摘要/核心观点/投资要点）
  - 方法关键词匹配（行业/估值/财务）
  - 判断信号提取（评级/目标价/增速/风险）
  纯规则式（0 token），为后续子代理深度洞察提供全量索引。

用法：
  python scripts/absorb_knowledge_base.py
  python scripts/absorb_knowledge_base.py --dry-run
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = Path(os.environ.get("KB_DIR", _ROOT / "data" / "知识库"))
OUTPUT = Path(os.environ.get("KB_OUT", _ROOT / "data" / "methodology_knowledge_base.json"))

# 板块 → 主题映射
_SECTOR_TOPICS = {
    "02-行业与公司研究": {
        "行业分析方法和框架.md": "industry_research",
        "企业估值.md": "valuation_methods",
        "ifind研报.md": "research_reports",
        "深度研究报告原始文档.md": "deep_reports",
    },
    "03-估值与测算": {
        "估值模型_part1.md": "valuation_models",
        "估值模型_part2.md": "valuation_models",
        "excel知识和测算模型.md": "excel_models",
    },
    "04-回测基线库": {
        "回测基线库_1阶段.md": "backtest_baseline",
        "回测基线库_金牌_part01.md": "backtest_gold",
        "回测基线库_金牌_part02.md": "backtest_gold",
        "回测基线库_金牌_part03.md": "backtest_gold",
        "回测基线库_金牌_part04.md": "backtest_gold",
        "回测基线库_金牌_part05.md": "backtest_gold",
        "回测基线库_金牌_part06.md": "backtest_gold",
        "回测基线库_金牌_part07.md": "backtest_gold",
        "回测基线库_金牌_part08.md": "backtest_gold",
        "回测基线库_金牌_part09.md": "backtest_gold",
        "回测基线库_金牌_part10.md": "backtest_gold",
    },
}

# R58 新增板块：四大审计方法论 / 国际投行方法论（板块内全部 .md 吸收）
_ALL_SECTORS = {
    "08-四大审计方法论": "valuation_methods",
    "09-国际投行方法论": "valuation_methods",
}

# 方法关键词（行业/估值/财务域）
_METHOD_KWS = [
    # 行业分析
    "波特五力", "价值链", "生命周期", "供需", "竞争格局", "集中度",
    "壁垒", "渗透率", "TAM", "SAM", "SOM", "市场规模", "增速",
    "产业链", "利润池", "商业模式", "护城河", "景气", "拐点",
    "国产替代", "全球格局", "出口", "出海",
    # 估值
    "DCF", "贴现", "自由现金流", "FCFF", "FCFE", "WACC", "永续增长",
    "PE", "PB", "PS", "EV/EBITDA", "PEG", "可比公司", "相对估值",
    "绝对估值", "敏感性", "情景分析", "三表", "勾稽", "ROE", "ROIC",
    "毛利率", "净利率", "资产负债率", "周转率",
    # 财务
    "营收", "净利", "现金流", "资产负债表", "利润表", "现金流量表",
    "研发", "资本开支", "折旧", "摊销", "有息负债", "存货", "应收",
    "EPS", "BVPS", "每股",
    # 判断
    "评级", "目标价", "买入", "增持", "中性", "减持", "风险",
    "催化剂", "超预期", "低于预期", "推荐",
]

# 判断信号（报告分析质量基准）
_JUDGMENT_SIGNALS = [
    "评级", "目标价", "推荐", "增持", "买入",
    "风险提示", "催化剂", "敏感性", "情景",
    "超预期", "低于预期", "预期差", "估值锚",
    "护城河", "壁垒", "证伪", "反方",
]


def _clean_line(line: str) -> str:
    s = line.strip()
    for noise in ("免责声明", "信息披露", "证券研究报告", "执业编号",
                  "本报告由", "仅供内部", "分析师声明"):
        if noise in s:
            return ""
    if s.startswith("http://") or s.startswith("www."):
        return ""
    if re.fullmatch(r"\d+", s):
        return ""
    return s


def split_articles(text: str) -> list[dict]:
    """按 '# ' 顶级标题切分文章。返回 [{title, content}]。"""
    titles = [(m.start(), m.group(1).strip()) for m in re.finditer(r"^# (?!\#)(.+)$", text, re.MULTILINE)]
    articles = []
    for i, (pos, title) in enumerate(titles):
        end = titles[i + 1][0] if i + 1 < len(titles) else len(text)
        content = text[pos:end]
        # 跳过聚合标题（无页码分隔说明只是索引）
        if "### 第" not in content and "## " not in content and len(content) < 2000:
            continue
        articles.append({"title": title, "content": content})
    return articles


def _extract_summary(content: str) -> str:
    """提取报告要点/摘要正文。"""
    for anchor in (r"报告要点", r"核心观点", r"投资要点", r"摘要[：:]"):
        m = re.search(anchor + r"\s*\n?(.*?)(?=\n### |\n## |\n# |\n目\s*录|\Z)", content, re.DOTALL)
        if m and len(m.group(1).strip()) > 50:
            return _clean_paragraph(m.group(1))
    return ""


def _clean_paragraph(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        s = _clean_line(raw)
        if s and not s.startswith("### 第"):
            lines.append(s)
    para = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", para).strip()


def _extract_points(content: str) -> list[str]:
    """提取要点列表。"""
    summary = _extract_summary(content)
    if not summary:
        return []
    points = []
    for line in summary.splitlines():
        s = line.strip()
        if s.startswith(("➢", "•", "●")) or s.startswith("- "):
            points.append(s.lstrip("➢•-● ").strip()[:150])
    return points[:8]


def _extract_methods(content: str) -> list[str]:
    found = []
    for kw in _METHOD_KWS:
        if re.search(kw, content):
            found.append(kw)
    return found[:8]


def _extract_judgment_signals(content: str) -> list[str]:
    found = []
    for sig in _JUDGMENT_SIGNALS:
        if sig in content:
            found.append(sig)
    return found[:10]


def process_file(filepath: Path, topic: str) -> list[dict]:
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return [{"title": f"[READ_ERROR] {filepath.name}", "topic": topic,
                 "source_file": filepath.name, "summary": str(e)[:80]}]
    articles = split_articles(text)
    entries = []
    for art in articles:
        summary = _extract_summary(art["content"])
        entry = {
            "title": art["title"].replace(".pdf", "").strip()[:100],
            "source_file": filepath.name,
            "topic": topic,
            "methods": _extract_methods(art["content"]),
            "judgment_signals": _extract_judgment_signals(art["content"]),
        }
        if summary:
            entry["summary"] = summary[:500]
        points = _extract_points(art["content"])
        if points:
            entry["points"] = points
        if summary or entry["methods"]:
            entries.append(entry)
    return entries


def process_all() -> dict:
    if not KB_DIR.exists():
        return {"error": f"{KB_DIR} not found"}
    result = {}
    stats = {}
    total = 0
    for sector, file_topics in _SECTOR_TOPICS.items():
        sector_dir = KB_DIR / sector
        if not sector_dir.exists():
            continue
        for fname, topic in file_topics.items():
            if topic == "__all__":
                continue  # 由 _ALL_SECTORS 统一处理
            fp = sector_dir / fname
            if not fp.exists():
                continue
            entries = process_file(fp, topic)
            result.setdefault(topic, []).extend(entries)
            stats[f"{sector}/{fname}"] = len(entries)
            total += len(entries)
    # R58：板块级全量吸收
    for sector, topic in _ALL_SECTORS.items():
        sector_dir = KB_DIR / sector
        if not sector_dir.exists():
            continue
        for fp in sorted(sector_dir.glob("*.md")):
            entries = process_file(fp, topic)
            result.setdefault(topic, []).extend(entries)
            stats[f"{sector}/{fp.name}"] = len(entries)
            total += len(entries)
    for topic in result:
        result[topic].sort(key=lambda x: x["title"])
    result["_meta"] = {
        "generated": __import__("datetime").datetime.now().isoformat(),
        "source_dir": str(KB_DIR),
        "total_articles": total,
        "per_file": stats,
        "note": "规则式吸收（0 token）。summary=报告要点/摘要；methods/indicators=关键词匹配。",
    }
    return result


def main():
    ap = argparse.ArgumentParser(description="知识库规则式吸收（0 token）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    result = process_all()
    if "error" in result:
        print(f"[ERR] {result['error']}")
        sys.exit(1)
    topics = {k: v for k, v in result.items() if k != "_meta"}
    print(f"吸收完成: {result['_meta']['total_articles']} 篇 → {len(topics)} 主题")
    for topic, items in topics.items():
        with_summary = sum(1 for i in items if i.get("summary"))
        print(f"  {topic}: {len(items)} 篇 (含摘要 {with_summary})")
    if args.dry_run:
        print("[DRY-RUN] 未写文件")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
