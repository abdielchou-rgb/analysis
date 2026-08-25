# -*- coding: utf-8 -*-
"""framework_scoreboard.py — 框架胜率榜（M5 报表）。

读 data/predictions.json，按 statement 中 [fw:x] 标记聚合：
  框架 | 已验证 | ±10%命中 | 平均偏差
无标记的预测归入 (untagged)。
用法：python scripts/framework_scoreboard.py [--json out.json]
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DB = _ROOT / "data" / "predictions.json"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> int:
    try:
        d = json.loads(_DB.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ledger unreadable: {e}")
        return 1
    preds = d.get("predictions", [])
    rows = [p for p in preds if p.get("verified") and p.get("deviation_pct") is not None]

    agg: dict[str, list[float]] = defaultdict(list)
    for p in rows:
        m = p.get("statement", "")
        tag = "untagged"
        if "[fw:" in m:
            tag = m.split("[fw:", 1)[1].split("]", 1)[0] or "untagged"
        agg[tag].append(float(p["deviation_pct"]))

    print(f"{'框架':<22}{'已验证':>6}{'命中(±10%)':>10}{'平均偏差':>10}")
    out = {}
    for tag, devs in sorted(agg.items(), key=lambda x: -len(x[1])):
        hits = sum(1 for v in devs if abs(v) <= 10)
        rate = hits / len(devs)
        avg = statistics.mean(abs(v) for v in devs)
        print(f"{tag:<22}{len(devs):>6}{rate:>9.0%}{avg:>9.1f}%")
        out[tag] = {"verified": len(devs), "hit_rate": round(rate, 2), "avg_abs_dev": round(avg, 2)}
    print(f"\n共 {len(rows)} 条已验证预测。样本 <3 的框架仅供参考。")

    args = sys.argv[1:]
    if "--json" in args:
        outp = Path(args[args.index("--json") + 1])
        outp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
