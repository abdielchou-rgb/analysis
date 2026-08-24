# -*- coding: utf-8 -*-
"""redteam_check.py — 确定性红队回放（零 LLM、离线、CI 可跑）。

用法：
    python scripts/redteam_check.py                # 回放 redteam/attacks.yaml
    python scripts/redteam_check.py --json out.json

对每条攻击用例按 expect 断言：
  spotlight_escaped : 经 spotlight_untrusted 后无裸尖括号/含安全声明
  no_raw_close_tag  : 攻击者伪造的闭合标记必须失效
  vague_or_tiered   : 伪造来源应被 source_tier 判为非高置信
  gate_filter       : Gate 反馈污染句式须被口径检查过滤逻辑跳过
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from core.source_tier import score_source  # noqa: E402
from core.untrusted_wrapper import spotlight_untrusted  # noqa: E402


def _check(case: dict) -> tuple[bool, str]:
    payload = case["payload"]
    expect = case.get("expect", "spotlight_escaped")
    wrapped = spotlight_untrusted(payload, source_label="redteam")

    if expect == "spotlight_escaped":
        if "[SECURITY]" not in wrapped:
            return False, "缺少安全声明"
        if "<" in payload and ("<" in wrapped.split("\n", 2)[2] if "\n" in wrapped else False):
            return False, "尖括号未转义"
        return True, "wrapped"

    if expect == "no_raw_close_tag":
        # 合法闭合恰 1 次（wrapper 自身）；攻击载荷中的伪造闭合必须已转义
        if wrapped.count("</UNTRUSTED_") != 1:
            return False, f"闭合标记数量异常: {wrapped.count('</UNTRUSTED_')}"
        return True, "escape holds"

    if expect == "vague_or_tiered":
        tier, w = score_source(payload)
        if tier == "official":
            return False, "伪造来源被判为 official（应不可信）"
        return True, f"tier={tier}"

    if expect == "gate_filter":
        from core.data_caliber import check_report_units  # noqa: F401
        from pipeline.checks.analysis_mixin import AnalysisChecksMixin

        # 直接复用 market_size 检查中的自引用过滤：构造含污染句的文本，
        # 若该句进入冲突判定即视为未过滤。
        from pipeline.iron_gate import IronGate

        g = IronGate.__new__(IronGate)
        g.report_text = "中国市场规模2025年约172亿元。" + payload
        g.report_type = "listed_company"
        g.asset = ""  # 无 asset → 不加载外部锚点，仅测文内污染过滤
        r = AnalysisChecksMixin._check_market_size_consistency(g)
        # 污染句被过滤 → 单一来源文本应 PASS；泄漏则 Gate 会报多口径冲突
        return r.passed, "filtered" if r.passed else f"pollution leaked: {r.details[:60]}"

    return True, "unknown expectation (pass-through)"


def main() -> int:
    args = sys.argv[1:]
    corpus_path = _ROOT / "redteam" / "attacks.yaml"
    cases = yaml.safe_load(corpus_path.read_text(encoding="utf-8"))
    all_ok = True
    results = []
    for c in cases:
        ok, note = _check(c)
        all_ok &= ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {c['id']} ({c['category']}) — {note}")
        results.append({"id": c["id"], "ok": ok})
    if "--json" in args:
        out = Path(args[args.index("--json") + 1])
        out.write_text(str(results).replace("'", '"'), encoding="utf-8")
    print(f"\n=== redteam: {'PASS' if all_ok else 'FAIL'} ({len(cases)} cases) ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
