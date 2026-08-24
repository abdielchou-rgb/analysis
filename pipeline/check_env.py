"""2号分析师 — 环境自检脚本

在运行 scheduler.py 之前必须执行此脚本，或确认所有项通过。

用法：
    python pipeline/check_env.py
"""

import importlib
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def check(name: str, passed: bool, detail: str = ""):
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name}  {detail}")
    return passed


def main():
    print(f"\n{'=' * 50}")
    print("  2号分析师 环境自检")
    print(f"{'=' * 50}\n")

    all_pass = True

    # 1. Python 版本
    pv = sys.version_info
    all_pass &= check("Python >= 3.10", pv.major >= 3 and pv.minor >= 10, f"({pv.major}.{pv.minor}.{pv.micro})")

    # 2. DeepSeek API Key
    dk = os.environ.get("DEEPSEEK_API_KEY", "")
    key_ok = bool(dk) and dk.startswith("sk-")
    all_pass &= check("DEEPSEEK_API_KEY", key_ok, f"({'已设置' if dk else '未设置'})")
    if not key_ok:
        print("     ⚠ 设置方法：export DEEPSEEK_API_KEY='sk-xxxxx'")
        print("     或将密钥写入 .env 文件，然后 source .env")

    # 3. 核心模块
    for mod_name in [
        "core.deepseek_client",
        "core.sacs",
        "core.data_credibility",
        "pipeline.iron_gate",
        "pipeline.section_writer",
        "pipeline.write_revise_loop",
        "pipeline.scheduler",
        "pipeline.data_collector",
    ]:
        try:
            importlib.import_module(mod_name)
            all_pass &= check(mod_name, True)
        except Exception as e:
            all_pass &= check(mod_name, False, str(e)[:60])

    # 4. SAC 文件
    sac_dir = _ROOT / "core" / "sacs"
    for yaml_file in [
        "sac_industry_deep.yaml",
        "sac_listed_company.yaml",
        "sac_unlisted_company.yaml",
        "sac_earnings_notes.yaml",
        "sac_decision_memo.yaml",
    ]:  # R83
        ok = (sac_dir / yaml_file).exists()
        all_pass &= check(f"SAC: {yaml_file}", ok)

    # 5. 输出目录可写
    output_dir = _ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    all_pass &= check("输出目录可写", output_dir.is_dir())

    # 6. CLAUDE.md 是否存在
    claude_md = _ROOT / "CLAUDE.md"
    all_pass &= check("CLAUDE.md 行为约束", claude_md.exists())

    print(f"\n{'=' * 50}")
    if all_pass:
        print("  结果: ✅ 全部通过，可以运行 scheduler.py")
    else:
        print("  结果: ⚠️ 部分检查未通过，请修复后再运行")
    print(f"{'=' * 50}\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
