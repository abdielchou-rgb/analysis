"""V51 Regression test: compare output quality against V22 benchmark.

Four metrics (no LLM required — pure statistical):
  1. word_count: total Chinese characters
  2. citation_count: number of cited sources
  3. counter_argument_sections: number of risk/counter/falsification paragraphs
  4. sharp_judgment_density: percentage of chapters with contrarian judgment keywords

Baseline: V22 gas sensor report (~15,000 chars, 18 citations, 11 risk paragraphs)
Threshold: outputs below 40% of baseline trigger FAIL
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

V50 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V50))

n_pass, n_fail = 0, 0

BASELINE = {
    "word_count": 15000,  # V22 ~15,000 Chinese chars
    "citation_count": 18,  # V22 18 citation sources
    "counter_paragraphs": 11,  # V22 Chapter 11: 6 risks + 5 falsifications
    "sharp_judgment_pct": 80,  # V22 ~80% of chapters have contrarian judgment
}

THRESHOLD = 0.40  # Fail if <40% of baseline


def t(name, ok, detail=""):
    global n_pass, n_fail
    if ok:
        n_pass += 1
    else:
        n_fail += 1
        print(f"  FAIL: {name} {detail}")


def check_output(filepath: str) -> dict:
    """Analyze a report markdown file against V22 benchmark criteria."""
    path = Path(filepath)
    if not path.exists():
        return {"error": f"not found: {filepath}"}

    text = path.read_text(encoding="utf-8")

    # 1. Word count (Chinese chars + punctuation)
    chinese_chars = len(re.findall(r"[一-鿿]", text))

    # 2. Citation count (look for cited sources patterns)
    citations = set()
    citation_patterns = [
        r"（[一-鿿\d，,\s]+，\d{4}）",
        r"来源[：:][一-鿿/\s]+",
        r"[一-鿿]{2,}，\d{4}",
        r"数据来源[：:].+",
    ]
    for pat in citation_patterns:
        for m in re.findall(pat, text):
            if len(m) > 4:
                citations.add(m.strip())
    citation_count = max(len(citations), text.count("来源") + text.count("数据来源"))

    # 3. Counter-argument sections
    counter_keywords = ["风险", "证伪", "反方", "不及预期", "不利", "谨慎", "免责"]
    counter_sections = []
    lines = text.split("\n")
    in_section = False
    for line in lines:
        if line.startswith("##") or line.startswith("#"):
            in_section = line
        if in_section and any(k in line for k in counter_keywords):
            counter_sections.append(in_section)

    # 4. Sharp judgment count (every chapter should have ONE contrarian judgment)
    judgment_keywords = [
        "而非",
        "不同于市场",
        "与市场分歧",
        "我们认为",
        "超预期",
        "低于预期",
        "颠覆",
        "突破",
        "拐点",
        "结构性变化",
        "误读",
    ]
    chapters = re.split(r"\n#+\s", text)
    sharp_chapters = 0
    total_chapters = max(len(chapters) - 1, 1)  # subtract preamble
    for ch in chapters:
        if len(ch) < 50:
            total_chapters -= 1
            continue
        if any(k in ch for k in judgment_keywords):
            sharp_chapters += 1
    sharp_pct = (sharp_chapters / max(total_chapters, 1)) * 100

    # 5. AI contamination check
    ai_indicators = ["AIGC", "ContentProducer", "AI生成", "由AI", "AI辅助"]

    return {
        "word_count": chinese_chars,
        "citation_count": citation_count,
        "counter_paragraphs": len([s for s in counter_sections if s]),
        "sharp_judgment_pct": sharp_pct,
        "ai_contamination": any(i in text for i in ai_indicators),
    }


# Run tests on existing outputs
# 2026-08-03 修复：报告已迁移至 output/（单数），旧 outputs/ 目录仅剩 7 月底废稿
output_dir = V50 / "output"
report_files = sorted(output_dir.glob("*.md")) if output_dir.exists() else []
# 过滤内部产物（_开头/gate/train 草稿），只保留正式报告
report_files = [
    f for f in report_files if not f.name.startswith("_") and "gate" not in f.name and "train" not in f.name
]

if not report_files:
    # 回退旧目录（兼容历史环境）
    output_dir = V50 / "outputs"
    report_files = sorted(output_dir.glob("*.md")) if output_dir.exists() else []

if not report_files:
    print("No output files found — skipping word-count tests")
    t("regression: outputs exist", False, "no .md files in outputs/")
else:
    # 选择最新一份正式报告做回归验证
    test_file = report_files[-1]

    result = check_output(str(test_file))
    if "error" in result:
        t("regression: file readable", False, result["error"])
    else:
        # Word count ≥ 40% of baseline
        wc_ok = result["word_count"] >= BASELINE["word_count"] * THRESHOLD
        t(f"regression: word_count ({result['word_count']} >= {BASELINE['word_count'] * THRESHOLD})", wc_ok)

        # Citation count ≥ 40% of baseline
        cc_ok = result["citation_count"] >= max(BASELINE["citation_count"] * THRESHOLD, 3)
        t(
            f"regression: citations ({result['citation_count']} >= {max(int(BASELINE['citation_count'] * THRESHOLD), 3)})",
            cc_ok,
        )

        # Counter-argument paragraphs
        cp_ok = result["counter_paragraphs"] >= max(BASELINE["counter_paragraphs"] * THRESHOLD, 2)
        t(
            f"regression: counter_sections ({result['counter_paragraphs']} >= {max(int(BASELINE['counter_paragraphs'] * THRESHOLD), 2)})",
            cp_ok,
        )

        # Sharp judgment density
        sj_ok = result["sharp_judgment_pct"] >= BASELINE["sharp_judgment_pct"] * THRESHOLD
        t(
            f"regression: sharp_judgment ({result['sharp_judgment_pct']:.0f}% >= {BASELINE['sharp_judgment_pct'] * THRESHOLD:.0f}%)",
            sj_ok,
        )

        # AI contamination — must be ZERO
        t("regression: no AI contamination", not result["ai_contamination"], "found AIGC/metadata in report")

        print(f"\n  Report: {test_file.name}")
        for k, v in result.items():
            print(f"    {k}: {v}")

# ── Compile / syntax check ───────────────────────────────────────────────
# 2026-09-14 审计修复（收集期 >202s → ~3s，快 ~39x）：
# 原实现在**模块作用域**直接 rglob("*.py") 全仓 py_compile，三个问题：
#   1) 过滤器只排除 __pycache__ / V30_，未排除 .venv —— 实测仓内 10375 个 .py
#      里 9382 个来自 .venv（90%），等于每次 pytest **收集**都在重编译整个虚拟环境。
#   2) py_compile 会写 .pyc（磁盘 I/O），而本检查只关心语法，用 ast.parse 即可。
#   3) 结果只 print、从不参与断言 —— 纯装饰性开销，且真错误被吞掉：
#      实测它就藏着一个 SyntaxError（scripts/last30days/lib/render.py:3450）。
# 现拆为 _compile_sweep()：排除 vendor 目录、改用 ast.parse、并真正断言。
_VENDOR_DIRS = frozenset(
    {".venv", "venv", ".git", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", "site-packages"}
)


def _compile_sweep() -> tuple[int, int, list[tuple[str, str]]]:
    """语法检查仓内**自有** .py（排除 vendor）。返回 (ok, fail, [(相对路径, 错误)])。"""
    root = Path(__file__).resolve().parent.parent
    ok = 0
    failures: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in _VENDOR_DIRS for part in rel.parts):
            continue
        if "V30_" in str(path):
            continue
        try:
            # utf-8-sig：容忍 BOM（Python 词法器会剥 BOM，ast.parse 不会）
            ast.parse(path.read_text(encoding="utf-8-sig"))
            ok += 1
        except SyntaxError as e:
            failures.append((str(rel), f"line {e.lineno}: {e.msg}"))
        except (UnicodeDecodeError, OSError) as e:
            failures.append((str(rel), f"{type(e).__name__}: {str(e)[:80]}"))
    return ok, len(failures), failures


if __name__ == "__main__":
    print("\n--- Syntax check ---")
    _ok, _fail, _bad = _compile_sweep()
    print(f"  syntax: {_ok} ok, {_fail} fail")
    for _rel, _msg in _bad:
        print(f"    FAIL {_rel} — {_msg}")
    print(f"\n=== {n_pass} passed, {n_fail} failed ===")
    sys.exit(1 if n_fail > 0 else 0)


# ── P1-audit 2026-08-24 收编：模块级 t() 只 print 不 raise，pytest 看不见 ──
def test_orphan_suite():
    assert n_fail == 0, f"{n_fail} 个断言失败 / 共 {n_pass + n_fail} 条"


def test_all_project_modules_parse():
    """仓内自有模块必须全部通过语法解析（排除 .venv 等 vendor 目录）。"""
    ok, fail, bad = _compile_sweep()
    assert fail == 0, f"{fail} 个模块语法错误（共检查 {ok + fail} 个）：" + "; ".join(f"{r} — {m}" for r, m in bad[:10])
