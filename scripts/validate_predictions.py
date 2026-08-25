#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预测验证 CLI — R30 模块1：验证 forward_picks.csv 中到期的预测

用法：
  python scripts/validate_predictions.py          # 验证所有到期预测
  python scripts/validate_predictions.py --stats  # 查看评分卡
  python scripts/validate_predictions.py --purge  # 清理低质量记录
"""

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def main():
    parser = argparse.ArgumentParser(description="2hao 预测验证 CLI")
    parser.add_argument("--horizon", type=int, default=365, help="到期天数（默认 365 天）")
    parser.add_argument("--stats", action="store_true", help="查看评分卡")
    parser.add_argument("--purge", action="store_true", help="清理低质量记录")
    args = parser.parse_args()

    from core.forward_picks import ForwardPicksDB, ScoreTracker
    from core.prediction_validator import validate_forward_picks_csv

    db = ForwardPicksDB()

    if args.purge:
        n = db.purge_low_quality()
        print(f"清理低质量记录: {n} 条")
        return 0

    if args.stats:
        tracker = ScoreTracker()
        print(tracker.report())
        return 0

    # 验证
    r = validate_forward_picks_csv(horizon_days=args.horizon)
    print("预测验证结果:")
    print(f"  总数: {r['total']}")
    print(f"  已到期: {r['expired']}")
    print(f"  已验证: {r['validated']}")
    print(f"  命中: {r['hit']} / 未命中: {r['miss']}")
    print(f"  跳过(无价): {r['skipped']}")
    print(f"  待验证: {r['pending_after']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
