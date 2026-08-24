# -*- coding: utf-8 -*-
"""golden_flywheel.py — 黄金集飞轮（真实报告 → golden 候选）。

P3-B 落地：让黄金集随真实产出成长（3 → 30+ 的路径）。

用法：
  # 1) 预检：跑确定性指标，看是否够格
  python scripts/golden_flywheel.py --report output/宁德时代_cicc.md

  # 2) 确认入库（人工过目内容后加 --confirm）
  python scripts/golden_flywheel.py --report output/宁德时代_cicc.md --confirm

规则：
  - eval_gate 全部通过才允许入库
  - 文件名 <asset>_<yyyymmdd>.md；重复资产同日覆盖
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

sys.path.insert(0, str(_ROOT / "tests" / "golden"))

from eval_gate import evaluate_report  # noqa: E402

GOLDEN_DIR = _ROOT / "tests" / "golden"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--confirm", action="store_true", help="人工过目后确认入库（缺省仅预检）")
    a = ap.parse_args()

    src = Path(a.report)
    if not src.exists():
        print(f"not found: {src}")
        return 1

    r = evaluate_report(src)
    print(f"metrics: {r['metrics']}")
    if not r["passed"]:
        print("FAIL — 未达 golden 门槛，拒绝入库：")
        for f in r["failures"]:
            print("  -", f)
        return 1

    asset = re.sub(r"[^\w一-鿿]+", "", src.stem.split("_")[0])[:12] or "report"
    dst = GOLDEN_DIR / f"{asset}_{datetime.now():%Y%m%d}.md"
    meta = f"<!-- golden: source={src.name} asset={asset} date={datetime.now():%Y-%m-%d} via=golden_flywheel -->\n\n"

    if a.confirm:
        GOLDEN_DIR.mkdir(exist_ok=True)
        dst.write_text(meta + src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"✓ 入库: {dst.name}（记得 git add 并跑一次 golden 测试）")
        return 0

    print(f"PASS — 够格入库：{dst.name}（人工过目后追加 --confirm）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
