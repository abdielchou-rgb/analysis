# -*- coding: utf-8 -*-
"""pre-commit 钩子：PIPELINE_FACTS 同步门。

重新生成 docs/PIPELINE_FACTS.md；若与暂存/工作区版本出现差异 → exit 1，
提示开发者 `git add docs/PIPELINE_FACTS.md`（事实变更必须随代码入库）。
"""

import subprocess
import sys

_ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
sys.path.insert(0, _ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from harness.generate_docs import write_pipeline_facts  # noqa: E402


def main() -> int:
    write_pipeline_facts()
    r = subprocess.run(["git", "diff", "--exit-code", "--", "docs/PIPELINE_FACTS.md"])
    if r.returncode != 0:
        print("docs/PIPELINE_FACTS.md 与代码不同步——已重新生成，请 git add 该文件后重试提交")
        return 1
    print("PIPELINE_FACTS in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
