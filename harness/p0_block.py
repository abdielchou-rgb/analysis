"""pre-commit 钩子：P0 检查阻断（存在任一 P0 失败即 exit 1）。

从 .pre-commit-config.yaml 的内联 python 提取为模块——内联脚本里的
`key: value` 形态字符串会破坏 YAML 解析（休眠地雷，2026-08-24 排除）。
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:  # Windows GBK 控制台
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from harness.validator import run_all  # noqa: E402


def main() -> int:
    report = run_all()
    p0_fail = [c for c in report.checks if not c.passed and c.severity == "P0"]
    print(f"Harness: {len(p0_fail)} P0 failures")
    return 1 if p0_fail else 0


if __name__ == "__main__":
    sys.exit(main())
