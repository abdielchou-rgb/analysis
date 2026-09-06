"""
eval/report_quality.py — 确定性报告质量回归集（2026-09-06，对标 DeepEval pytest-style）。

与 rubric（LLM 全篇评分，贵、有噪声）互补：本模块用**确定性断言**扫评测集报告，
专抓"机械回归"——正是上轮手工发现的那类污染（57 处注解复读、评级表被插注、
附录缺失）能在秒级被断言拦截。断言全部 0 LLM 成本，可进 CI / pytest。

检查清单（每项 = 可解释的布尔断言）：
    Q1 无黑名单注解复读（template_blacklist.ANNOTATION_REPEAT 命中=0）
    Q2 证据附录存在（数据键 / [注 标记出现）
    Q3 认知边界附录存在（诚实留白）
    Q4 无工作过程语言（补采/校验通过/2hao 等 AI 工具痕迹）
    Q5 评级定义段不被污染（表行不含注解）
    Q6 数值区间未被拆烂（正则：%后的"-"区间内无括注插入）
    Q7 报告无残留 {{ }} 占位符

用法：
    python -m eval.report_quality                 # 全评测集
    python -m eval.report_quality --report 茅台    # 单份（asset 子串）
退出码：全过 0，任一 fail 1。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))


def _checks_for(text: str) -> list[dict]:
    out = []

    def _add(name, passed, detail):
        out.append({"check": name, "passed": bool(passed), "detail": str(detail)[:120]})

    # Q1 注解复读
    from core.template_blacklist import ANNOTATION_REPEAT, scan

    r = scan(text)
    _add("Q1_no_annotation_repeat", r["total_exact"] == 0, f"template hits={r['exact_hits']}")
    # Q2 证据附录（数据键 / [注 标记）
    has_ledger = ("数据键" in text) or (text.count("[注") >= 5)
    _add("Q2_evidence_ledger", has_ledger, f"[注] count={text.count('[注')}")
    # Q3 认知边界
    _add("Q3_cognitive_boundary", "认知边界" in text, "found" if "认知边界" in text else "missing")
    # Q4 工作过程语言（排除路径中的仓库名；排除认知边界附录的"数据补采"——那是
    # Phase E 诚实留白的标准措辞，非 AI 工具痕迹）
    from core.template_blacklist import scan_work_process

    wp = scan_work_process(text)
    q4_hits = []
    for h in wp["exact_hits"]:
        _term = h["term"]
        if _term == "2hao":
            in_path = len(re.findall(r"[\w]:/2hao-analyst|/2hao-analyst/", text))
            if h["count"] <= in_path:
                continue  # 全部是路径引用 → 不算污染
            q4_hits.append({**h, "count": h["count"] - in_path})
        elif _term == "补采":
            # 认知边界附录句式"后续数据补采后验证"是诚实留白，不算工具痕迹
            _clean = len(re.findall(r"后续数据补采后验证", text))
            if h["count"] <= _clean:
                continue
            q4_hits.append({**h, "count": h["count"] - _clean})
        else:
            q4_hits.append(h)
    q4_total = sum(h["count"] for h in q4_hits) + wp["line_separators"]
    _add("Q4_no_work_process", q4_total == 0, f"work-process hits={q4_hits}, seps={wp['line_separators']}")
    # Q5 评级定义表行不被注解污染（| 行内出现黑名单注解短语）
    polluted_rows = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("|") and any(a in ln for a in ANNOTATION_REPEAT):
            polluted_rows.append(ln.strip()[:60])
    _add("Q5_rating_table_clean", not polluted_rows, polluted_rows[:2])
    # Q6 区间未被拆烂：数字% + 括注 + - + 数字% 形态（注解插入区间中间）
    broken = re.findall(r"\d+\.?\d*%[（(][^）)]{2,40}[）)]\s*-\s*\d+\.?\d*%", text)
    _add("Q6_ranges_intact", not broken, broken[:2])
    # Q7 无残留占位符。硬错误只有 {{ }} 模板占位 / TODO / FIXME；"心智占位"是品牌
    # 术语、"待补充/数据缺口"是 Phase E 认知边界机制的正常措辞，均不算占位。
    _tmpl = re.findall(r"\{\{.*?\}\}", text)
    _todo = [t for t in ["TODO", "FIXME"] if t in text]
    ph = _tmpl + _todo
    _add("Q7_no_placeholders", not ph, ph[:3])
    return out


def run_quality(report_filter: str | None = None) -> dict:
    evalset = json.loads((_ANALYST_ROOT / "eval" / "evalset.json").read_text(encoding="utf-8")).get("reports", [])
    if report_filter:
        evalset = [r for r in evalset if report_filter in r.get("file", "") or report_filter in r.get("asset", "")]
    per_asset = {}
    all_pass = True
    for r in evalset:
        fp = _ANALYST_ROOT / r["file"]
        if not fp.exists():
            per_asset[r["asset"]] = {"error": "file missing"}
            all_pass = False
            continue
        text = fp.read_text(encoding="utf-8")
        checks = _checks_for(text)
        asset_pass = all(c["passed"] for c in checks)
        all_pass = all_pass and asset_pass
        per_asset[r["asset"]] = {"passed": asset_pass, "checks": checks}
    return {"passed": all_pass, "per_asset": per_asset, "n_assets": len(per_asset)}


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=None)
    args = parser.parse_args()
    result = run_quality(args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    run_cli()
