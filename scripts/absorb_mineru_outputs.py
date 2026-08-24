#!/usr/bin/env python3
"""MinerU 解析产物 → 方法论规则库接入脚本

把 Marvis/Claude 用 MinerU 解析出的估值方法论/行业框架 PDF 全文（data/基线/解析产物/*.md）
提炼成"可执行判断规则"（methodology_rules.json），供 section_writer 写报告时注入。

背景：
- MinerU 产物是"全文提取"，信息量远超旧 pdfplumber 的"文件+摘要"级。
- 估值方法论（DCF/PE/PS/实物期权）+ 行业框架（汽车/半导体/技术价值）是
  methodology_frameworks_detailed.json 缺失的素材。
- 本脚本把全文提炼为规则（阈值+逻辑+结论指向），写入 methodology_rules.json，
  让 LLM 真正按投行方法做判断（而非只看文件名）。

用法：
  python scripts/absorb_mineru_outputs.py [--dir 解析产物目录] [--dry-run]

产出：
  data/methodology_rules.json 追加规则条目（按 topic: valuation_* / industry_*）
"""

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
PARSED_DIR = _ROOT / "data" / "基线" / "解析产物"

# 让脚本能 import core（scripts/ 下运行时 core 不在 sys.path）
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── 主题识别：从文件名/首段判断方法论主题 ──
def detect_topic(name: str, head_text: str) -> str:
    """从文件名 + 开头文本判断主题，返回 methodology_rules 的 topic 键。"""
    n = name
    t = head_text[:200]
    # 估值方法论
    if any(k in n for k in ("估值", "价值评估", "DCF", "DCF估值")):
        return "valuation"
    if "估值" in t or "DCF" in t or "折现" in t or "市盈率" in t:
        return "valuation"
    if any(k in n for k in ("实物期权", "期权")):
        return "real_option"
    if "实物期权" in t:
        return "real_option"
    # 行业框架
    if any(k in n for k in ("汽车", "半导体", "行业", "产业", "培训")):
        return "industry_framework"
    # 通用技术/方法论
    if "技术" in n or "方法" in n:
        return "methodology_generic"
    return "other"


# ── 从全文提炼判断规则 ──
def extract_rules(topic: str, title: str, text: str) -> list:
    """从 MinerU 全文提取规则条目（估值阈值/判断逻辑/方法对比）。"""
    rules = []

    if topic == "valuation":
        rules = _extract_valuation_rules(title, text)
    elif topic == "real_option":
        rules = _extract_real_option_rules(title, text)
    elif topic == "industry_framework":
        rules = _extract_industry_framework_rules(title, text)
    else:
        # 通用：提取方法对比（表1/表2 中的方法体系）
        rules = _extract_method_comparison_rules(title, text)

    return rules


def _extract_valuation_rules(title: str, text: str) -> list:
    """估值方法论规则：DCF/PE/PS/收益法/市场法的判断逻辑。"""
    rules = []
    # 方法体系：成本法/市场法/收益法
    if any(k in text for k in ("成本法", "重置成本", "收益法", "市场法")):
        method_parts = []
        if "成本法" in text:
            method_parts.append("成本法：以重置成本为基础，适合无市场参照的专有技术")
        if "收益法" in text:
            method_parts.append("收益法：以未来收益折现为基础，公认最佳但依赖假设")
        if "市场法" in text:
            method_parts.append("市场法：以可比交易为基础，直接反映供需但弱可比性受限")
        rules.append({
            "rule_id": "valuation_method_comparison",
            "name": "估值方法三法对比（成本/收益/市场）",
            "source": f"MinerU解析-{title}",
            "inputs": ["资产属性", "数据可得性", "可比性"],
            "rules": [
                {"condition": "无市场参照+专有技术", "stage": "成本法", "implication": method_parts[0] if method_parts else "成本法"},
                {"condition": "未来收益可预测", "stage": "收益法", "implication": "折现估值，公认最佳但假设敏感"},
                {"condition": "可比交易充分", "stage": "市场法", "implication": "直接反映供需，弱可比性受限"},
            ],
            "decision_hints": "估值方法选择取决于资产属性与数据可得性；多方法交叉验证",
        })
    # 收益法/DCF 细节
    if "折现" in text or "DCF" in text.upper() or "净现值" in text:
        rules.append({
            "rule_id": "valuation_dcf_principle",
            "name": "收益现值法核心逻辑",
            "source": f"MinerU解析-{title}",
            "inputs": ["未来现金流", "折现率", "期限"],
            "rules": [
                {"condition": "未来收益可量化", "stage": "收益现值法", "implication": "价值=Σ未来收益折现，需合理折现率"},
                {"condition": "不确定性高", "stage": "实物期权补充", "implication": "NPV低估灵活性价值，期权法修正"},
            ],
            "decision_hints": "收益法对折现率敏感，需做敏感性分析",
        })
    return rules


def _extract_real_option_rules(title: str, text: str) -> list:
    """实物期权规则：识别期权特征资产。"""
    rules = []
    if "实物期权" in text:
        rules.append({
            "rule_id": "real_option_principle",
            "name": "实物期权评估原则",
            "source": f"MinerU解析-{title}",
            "inputs": ["决策灵活性", "不确定性", "投资可分阶段"],
            "rules": [
                {"condition": "投资可分阶段+不确定性高", "stage": "实物期权适用",
                 "implication": "NPV法低估灵活性价值，用期权定价修正"},
                {"condition": "一次性决策+收益确定", "stage": "传统NPV", "implication": "期权法不必要"},
            ],
            "decision_hints": "技术研发/专利类资产天然含期权属性",
        })
    return rules


def _extract_industry_framework_rules(title: str, text: str) -> list:
    """行业框架规则：汽车/半导体等行业分析方法。"""
    rules = []
    if "汽车" in title or "汽车" in text[:500]:
        rules.append({
            "rule_id": "industry_auto_framework",
            "name": "汽车行业分析框架",
            "source": f"MinerU解析-{title}",
            "inputs": ["产销量", "区域结构", "渗透率"],
            "rules": [
                {"condition": "全球销量CAGR稳定", "stage": "成熟市场", "implication": "看格局与成本，非总量"},
                {"condition": "区域渗透率提升", "stage": "成长市场", "implication": "看渗透率天花板"},
            ],
            "decision_hints": "汽车分析先分区域看渗透率阶段",
        })
    return rules


def _extract_method_comparison_rules(title: str, text: str) -> list:
    """通用方法对比规则（表1/表2 中的方法体系提炼）。"""
    rules = []
    # 提取"方法体系"段落
    m = re.search(r'方法(?:体系|比较)[^。\n]{0,200}', text)
    if m:
        rules.append({
            "rule_id": f"method_comparison_{title[:10]}",
            "name": f"{title[:20]}方法体系",
            "source": f"MinerU解析-{title}",
            "inputs": ["方法", "适用场景"],
            "rules": [{"condition": "需方法体系判断", "stage": "方法选择",
                       "implication": m.group(0)[:120]}],
            "decision_hints": "多方法交叉验证",
        })
    return rules


def absorb(parsed_dir: Path, dry_run: bool = False) -> dict:
    """扫描解析产物目录，提炼规则并写入 methodology_rules.json。"""
    from core.methodology_rules import save_external_rules

    md_files = list(parsed_dir.rglob("*.md"))
    # 排除中间分段（如 _p1-20.md 是分段，用完整版）
    md_files = [f for f in md_files if not re.search(r'_p\d+-\d+\.md$', f.name)]
    results = {"scanned": len(md_files), "parsed": 0, "rules_added": 0, "by_topic": {}}

    for f in md_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if len(text.strip()) < 200:
            continue
        topic = detect_topic(f.name, text)
        title = f.stem[:50]
        rules = extract_rules(topic, title, text)
        if not rules:
            continue
        results["parsed"] += 1
        results["rules_added"] += len(rules)
        results["by_topic"].setdefault(topic, 0)
        results["by_topic"][topic] += len(rules)
        if not dry_run:
            try:
                save_external_rules(topic, rules)
            except Exception as e:
                print(f"  [ERR] {f.name}: {e}")
        else:
            print(f"  [DRY] {topic:20s} +{len(rules)} 规则 | {title}")

    if dry_run:
        print(f"\n[dry-run] 扫描 {results['scanned']} 份，可提炼 {results['parsed']} 份，"
              f"{results['rules_added']} 条规则")
    else:
        print(f"[DONE] 扫描 {results['scanned']} 份，提炼 {results['parsed']} 份，"
              f"写入 {results['rules_added']} 条规则")
    for t, n in results["by_topic"].items():
        print(f"  {t}: +{n} 条")
    return results


def main():
    ap = argparse.ArgumentParser(description="MinerU 产物接入方法论规则库")
    ap.add_argument("--dir", default=str(PARSED_DIR), help="解析产物目录")
    ap.add_argument("--dry-run", action="store_true", help="只预览不写入")
    args = ap.parse_args()
    parsed_dir = Path(args.dir)
    if not parsed_dir.exists():
        print(f"目录不存在: {parsed_dir}")
        sys.exit(1)
    absorb(parsed_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
