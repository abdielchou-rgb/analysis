"""S5-2: 数据层整合

将零散数据文件迁移到统一目录结构：
- data/tracking/ — 跟踪记录（method_reflection_log, forward_picks）
- data/reference/ — 参考数据（industry_baselines, framework_registry）
- data/output/ — 运行产出（computed results, outputs）
- data/cache/ — 临时缓存
- data/checkpoints/ — 节点级 checkpoint
- data/batches/ — 批次状态
- data/reviews/ — 人工审核记录

旧平台代码归档：
- core/data_caliber.py → legacy/data_platform/
- core/data_predict.py → legacy/data_platform/

幂等操作：已迁移的文件不重复移动。
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("data_layer_consolidate")

# 迁移规则：(源文件名, 目标子目录)
MIGRATIONS = [
    ("method_reflection_log.json", "tracking"),
    ("forward_picks.json", "tracking"),
    ("verified_predictions.json", "tracking"),
    ("learned_patterns.json", "tracking"),
    ("framework_registry.json", "reference"),
    ("falsification_tracker.json", "tracking"),
    ("target_prices.json", "tracking"),
    ("ratings_history.json", "tracking"),
    ("company_events.db", "reference"),
]

# 旧平台代码归档规则：(源路径相对项目根, 目标相对路径)
LEGACY_MIGRATIONS = [
    ("core/data_caliber.py", "legacy/data_platform/"),
    ("core/data_predict.py", "legacy/data_platform/"),
    ("core/data_caliber_pure.py", "legacy/data_platform/"),
]

DATA_DIR = _ROOT / "data"


def consolidate(dry_run: bool = False) -> list[dict]:
    """执行数据迁移。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 确保新目录存在
    for subdir in ["checkpoints", "batches", "reviews", "tracking", "reference", "output", "cache"]:
        (DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)

    results = []

    for filename, subdir in MIGRATIONS:
        src = DATA_DIR / filename
        dst_dir = DATA_DIR / subdir
        dst = dst_dir / filename

        if not src.exists():
            results.append({"file": filename, "status": "not_found"})
            continue

        if dst.exists():
            results.append({"file": filename, "status": "already_migrated"})
            continue

        if dry_run:
            results.append({"file": filename, "status": "would_migrate", "from": str(src), "to": str(dst)})
        else:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            results.append({"file": filename, "status": "migrated", "from": str(src), "to": str(dst)})
            logger.info("  %s → %s", filename, dst)

    # 旧平台代码归档
    legacy_dst = _ROOT / "legacy" / "data_platform"
    for src_rel, dst_rel in LEGACY_MIGRATIONS:
        src = _ROOT / src_rel
        dst = _ROOT / dst_rel / Path(src_rel).name

        if not src.exists():
            results.append({"file": src_rel, "status": "not_found"})
            continue

        if dst.exists():
            results.append({"file": src_rel, "status": "already_archived"})
            continue

        if dry_run:
            results.append({"file": src_rel, "status": "would_archive", "from": str(src), "to": str(dst)})
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            results.append({"file": src_rel, "status": "archived", "from": str(src), "to": str(dst)})
            logger.info("  %s → %s", src_rel, dst)

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="数据层整合")
    parser.add_argument("--dry-run", action="store_true", help="预览迁移而不实际移动")
    args = parser.parse_args()

    logger.info("=== 数据层整合 ===")
    results = consolidate(dry_run=args.dry_run)
    for r in results:
        logger.info("  %s: %s", r["file"], r["status"])
    logger.info("完成。")


if __name__ == "__main__":
    main()
