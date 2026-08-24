#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观知识库规则式吸收 — 把 data/基线/宏观分析框架，MD/ 的 5 个大 MD
切分并提炼为结构化方法论知识（0 token，纯正则）。

背景（2026-08-03 核查）：
  系统此前的 methodology_frameworks_detailed.json 只提取了原始 PDF 前 8 页
  （每条 ~245 字摘要），且 industry_lifecycle/business_model 连 summary 都没有。
  data/基线/宏观分析框架，MD/ 是 8/3 新增的完整正文（218KB-689KB），含报告要点/
  摘要等浓缩方法论内容——本脚本把这些正文级知识吸收进系统。

输出：data/methodology_macro_absorbed.json
结构：{ topic: [{title, source_file, summary, methods, indicators, points}] }
  - summary: 报告要点/摘要正文（实质性内容，比旧 detailed.json 长得多）
  - methods: 方法关键词（正则匹配）
  - indicators: 关键指标（正则匹配）
  - points: 分条要点（从 ➢/- 列表提取）

用法：
  python scripts/absorb_macro_knowledge.py           # 全量吸收
  python scripts/absorb_macro_knowledge.py --dry-run # 只统计不写
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = Path(os.environ.get("MACRO_MD_DIR", _ROOT / "data" / "基线" / "宏观分析框架，MD"))
OUTPUT = Path(os.environ.get("MACRO_OUT", _ROOT / "data" / "methodology_macro_absorbed.json"))

# 主题检测（按文件名关键词）
_TOPIC_RULES = [
    ("industry_lifecycle", ["产业生命周期"]),
    ("business_model", ["商业模式", "财务框架", "勇者", "能者", "谋者", "智者"]),
    ("macro", ["宏观"]),
    ("strategy", ["策略", "授人以渔", "信号", "噪声", "底部", "大势"]),
]

# 方法关键词（正文级）
_METHOD_KWS = [
    "三因素框架", "分析框架", "测算模型", "高频指标", "预测模型",
    "领先指标", "同步指标", "滞后指标", "敏感性分析", "情景分析",
    "自上而下", "自下而上", "生命周期", "出清", "勾稽", "择股",
    "构建.*指数", "量价", "库存周期", "盈利周期", "估值体系",
    "信号", "噪声", "均值回归", "动量", "反转",
]

# 关键指标
_IND_KWS = [
    "工业增加值", "工业企业利润", "固定资产投资", "社会消费品零售",
    "出口", "CPI", "PPI", "PMI", "M1", "M2", "社融", "信贷",
    "GDP", "失业率", "库存", "产能利用率", "螺纹钢", "沥青",
    "商品房", "浮法玻璃", "BDI", "SCFI", "原油", "粗钢",
    "织机", "开工率", "汇率", "利率", "流动性",
]


def detect_topic(name: str) -> str:
    for topic, kws in _TOPIC_RULES:
        for kw in kws:
            if kw in name:
                return topic
    return "other"


def _clean_line(line: str) -> str:
    """清洗行：去掉页眉页脚/免责声明噪声。"""
    s = line.strip()
    # 去掉信达/长江免责声明
    if "免责声明" in s or "信息披露" in s or "证券研究报告" in s or "执业编号" in s:
        return ""
    # 去掉页脚链接
    if s.startswith("http://") or s.startswith("www."):
        return ""
    # 去掉纯页码
    if re.fullmatch(r"\d+", s):
        return ""
    return s


def split_articles(text: str) -> list[dict]:
    """按 '# ' 顶级标题切分为多篇文章。

    文件结构：# 大标题 = 一篇 PDF。首个 # 可能是聚合标题（如 '03 宏观分析方法论12讲'）。
    返回 [{title, content}]，跳过聚合标题（content 为空或极短）。
    """
    # 匹配 # 开头的行（排除 ###）
    titles = [(m.start(), m.group(1).strip()) for m in re.finditer(r"^# (?!\#)(.+)$", text, re.MULTILINE)]
    articles = []
    for i, (pos, title) in enumerate(titles):
        end = titles[i + 1][0] if i + 1 < len(titles) else len(text)
        content = text[pos:end]
        # 跳过聚合标题（内容里没有页码分隔，说明只是索引）
        if "### 第" not in content and "## " not in content and len(content) < 2000:
            continue
        articles.append({"title": title, "content": content})
    return articles


def _extract_summary(content: str) -> str:
    """提取报告要点/摘要正文。"""
    # 锚点1: '报告要点'
    m = re.search(r"报告要点\s*\n(.*?)(?=\n---|\n## |\n# |\Z)", content, re.DOTALL)
    if m and len(m.group(1).strip()) > 50:
        return _clean_paragraph(m.group(1))
    # 锚点2: '摘要：'
    m = re.search(r"摘要[：:]\s*\n?(.*?)(?=\n### |\n## |\n# |\n目\s*录|\Z)", content, re.DOTALL)
    if m and len(m.group(1).strip()) > 50:
        return _clean_paragraph(m.group(1))
    # 锚点3: 目录前的内容（第1-2页）
    m = re.search(r"(?:报告要点|核心观点|投资要点)\s*\n?(.*?)(?=\n目\s*录|\n### |\Z)", content, re.DOTALL)
    if m and len(m.group(1).strip()) > 50:
        return _clean_paragraph(m.group(1))
    return ""


def _clean_paragraph(text: str) -> str:
    """清洗段落：去页码标记、页眉、空行，压缩空白。"""
    lines = []
    for raw in text.splitlines():
        s = _clean_line(raw)
        if s and not s.startswith("### 第"):
            lines.append(s)
    para = "\n".join(lines)
    # 压缩多余空行
    para = re.sub(r"\n{3,}", "\n\n", para)
    return para.strip()


def _extract_points(content: str) -> list[str]:
    """从摘要中提取分条要点（➢/- 列表）。"""
    # 找摘要区域
    summary = _extract_summary(content)
    if not summary:
        return []
    points = []
    for line in summary.splitlines():
        s = line.strip()
        if s.startswith("➢") or s.startswith("•") or s.startswith("- ") or s.startswith("●"):
            points.append(s.lstrip("➢•-● ").strip()[:150])
    return points[:8]


def _extract_methods(content: str) -> list[str]:
    found = []
    for kw in _METHOD_KWS:
        if re.search(kw, content):
            # 去掉 '构建.*指数' 的 regex 味
            found.append(kw.replace(".*", ""))
    return found[:6]


def _extract_indicators(content: str) -> list[str]:
    found = []
    for ind in _IND_KWS:
        if ind in content:
            found.append(ind)
    return found[:12]


def process_all() -> dict:
    """处理全部宏观 MD → 结构化知识。"""
    if not BASE_DIR.exists():
        return {"error": f"{BASE_DIR} not found"}
    md_files = sorted(BASE_DIR.glob("*.md"))
    if not md_files:
        return {"error": f"no .md in {BASE_DIR}"}

    result = {}
    stats = {}
    for md in md_files:
        if md.name == "INDEX.md":
            continue
        text = md.read_text(encoding="utf-8")
        articles = split_articles(text)
        stats[md.name] = len(articles)
        for art in articles:
            topic = detect_topic(art["title"])
            summary = _extract_summary(art["content"])
            entry = {
                "title": art["title"].replace(".pdf", "").strip()[:80],
                "source_file": md.name,
                "topic": topic,
                "methods": _extract_methods(art["content"]),
                "indicators": _extract_indicators(art["content"]),
            }
            if summary:
                entry["summary"] = summary[:600]
            points = _extract_points(art["content"])
            if points:
                entry["points"] = points
            # 只有有实质内容才收（标题+方法或摘要）
            if summary or entry["methods"]:
                result.setdefault(topic, []).append(entry)

    # 排序 + 汇总
    for topic in result:
        result[topic].sort(key=lambda x: x["title"])
    result["_meta"] = {
        "generated": __import__("datetime").datetime.now().isoformat(),
        "source_dir": str(BASE_DIR),
        "total_articles": sum(len(v) for k, v in result.items() if k != "_meta"),
        "per_file": stats,
        "note": "规则式吸收（0 token）。summary=报告要点/摘要正文；methods/indicators=关键词匹配。",
    }
    return result


def main():
    ap = argparse.ArgumentParser(description="宏观知识库规则式吸收（0 token）")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写")
    args = ap.parse_args()

    result = process_all()
    if "error" in result:
        print(f"[ERR] {result['error']}")
        sys.exit(1)

    topics = {k: v for k, v in result.items() if k != "_meta"}
    print(f"吸收完成: {result['_meta']['total_articles']} 篇文章 → {len(topics)} 个主题")
    for topic, items in topics.items():
        with_summary = sum(1 for i in items if i.get("summary"))
        print(f"  {topic}: {len(items)} 篇 (含摘要 {with_summary})")
    print(f"文件分布: {result['_meta']['per_file']}")

    if args.dry_run:
        print("[DRY-RUN] 未写文件")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入: {OUTPUT}")


if __name__ == "__main__":
    main()
