#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预测 CSV 导入 — 把 Marvis 手写的 forward_picks.csv 导入 ForwardPicksDB。

R60（2026-08-03）：Marvis R55 快照写入了 12 条预测，但 CSV 列名
（asset/code/target_price/horizon/as_of/basis）与 ForwardPick 字段
（asset_code/base_target/created_at/core_thesis）不匹配 → DB 为空 → 验证闭环空转。

本脚本做列映射适配 + 质量门槛校验后入库。

用法：
  python scripts/import_forward_picks.py            # 导入 CSV → DB
  python scripts/import_forward_picks.py --dry-run  # 预览
"""

import argparse
import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main():
    ap = argparse.ArgumentParser(description="预测 CSV 导入")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from core.forward_picks import ForwardPick, ForwardPicksDB

    csv_path = _ROOT / "data" / "forward_picks" / "forward_picks.csv"
    if not csv_path.exists():
        print(f"[ERR] {csv_path} 不存在")
        return 1

    db = ForwardPicksDB()
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    print(f"CSV 读取 {len(rows)} 条")

    # 去重（2026-08-04 预测闭环审计）：重复导入会让同一标的出现多行 pending，
    # 到期验证时重复计分。以 (asset_code, direction, created_at) 为唯一键，
    # 已存在则跳过。
    existing_keys = set()
    for p in db.load_all():
        if p.asset_code:
            existing_keys.add((p.asset_code, p.direction, (p.created_at or "")[:10]))

    imported = 0
    skipped = []
    for r in rows:
        # 列映射（Marvis 列 → ForwardPick 字段）
        created_at = str(r.get("as_of", "")).strip()
        # R64（2026-08-04 审计修复 P0-008）：不再把 qlib 净值/复权价塞进 current_price。
        # current_price 保留"真实股价(元)"语义，需 akshare 等真实源（沙箱/离线不可得）。
        # 验证锚点改存 anchor_nav = qlib close 收益率指数净值（投入1元的净值），
        # 验证用 latest_nav/anchor_nav-1 算收益，口径自洽。
        anchor_nav = 0.0
        if r.get("code"):
            try:
                from core.data_backends import _query_local_qlib_price

                q = _query_local_qlib_price(str(r["code"]).strip())
                if q and q.get("prices") and q.get("dates"):
                    target = (created_at or "9999-99")[:7]
                    _nav = q["prices"][0]
                    for _d, _p in zip(q["dates"], q["prices"]):
                        if _d <= target:
                            _nav = _p
                    anchor_nav = float(_nav)
            except Exception:
                anchor_nav = 0.0
        direction = str(r.get("direction", "bull")).strip().lower()
        base_target = float(r["target_price"]) if r.get("target_price") else 0.0
        # R64（审计修复 P1-008）：不再造 bull_target=base_target 复制值。
        # 单目标价预测不伪造独立三情景；bull/bear_target 留 0 = 未提供（FP2 诚实边界）。
        bull_target = 0.0
        bear_target = 0.0
        pick = ForwardPick(
            asset_code=str(r.get("code", "")).strip(),
            asset_name=str(r.get("asset", "")).strip(),
            direction=direction,
            base_target=base_target,
            bull_target=bull_target,
            bear_target=bear_target,
            conviction=str(r.get("conviction", "medium")).strip().lower(),
            core_thesis=str(r.get("basis", ""))[:200],
            created_at=created_at,
            anchor_nav=anchor_nav,
            report_type="listed_company",
        )
        # 去重键检查
        key = (pick.asset_code, pick.direction, (pick.created_at or "")[:10])
        if pick.asset_code and key in existing_keys:
            skipped.append(f"{pick.asset_name} 重复(已存在)")
            continue

        # 质量门槛校验
        ok = db.append(pick)
        if ok:
            existing_keys.add(key)
            imported += 1
        else:
            skipped.append(f"{pick.asset_name}({pick.direction}/{pick.base_target})")

    print(f"导入成功: {imported} 条")
    if skipped:
        print(f"跳过(未过质量门槛): {len(skipped)} 条")
        for s in skipped[:10]:
            print(f"  - {s}")

    if args.dry_run:
        print("[DRY-RUN] 未写入 DB")
        return 0

    # 验证
    if not args.dry_run:
        from core.forward_picks import ScoreTracker

        tracker = ScoreTracker()
        print("\n=== 导入后评分卡 ===")
        print(tracker.report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
