"""R54 (2026-08-03) 回归测试 — format_sheriff 表格行尾粘连正文修复。

问题：LLM 编辑合并时把分析文字接到表格行尾（『|。这一趋势若延续...』或
      『|（数据来源：...）』），破坏 markdown 表格结构。completeness_scan
      检出气体报告 37 项此类问题。
修复：format_sheriff._fix_table_trailing_prose 把粘连内容拆成独立段落。
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _fix(text):
    from pipeline.format_sheriff import FormatSheriff

    fs = FormatSheriff()
    fixed = fs._fix_table_trailing_prose(text)
    return fixed, fs


def test_prose_after_table_row_split():
    """表格行尾粘连正文应拆分成独立段落。"""
    text = (
        "| 1 | 霍尼韦尔 | 美国 | ~22%（E） | 工业安全 | 电化学 |\n"
        "| 5 | 汉威科技 | 中国 | ~5%（E） | 工业安全 | 催化燃烧 |。这一趋势若延续，"
        "我们对竞争格局演变的判断将更加坚定。（数据来源：公司公告及行业公开资料）\n"
    )
    fixed, fs = _fix(text)
    assert len(fs.fixes_applied) >= 1, f"应修复粘连: {fs.fixes_applied}"
    lines = fixed.split("\n")
    # 表格行应以 | 结尾
    assert lines[1].rstrip().endswith("|"), f"表格行应恢复|结尾: {lines[1]}"
    # 正文应独立成段
    assert "这一趋势若延续" in lines[2], f"正文应独立成段: {lines[2]}"


def test_source_note_after_table_row_split():
    """表格行尾粘连来源标注（|（数据来源）应拆分成独立段落。"""
    text = "| 1 | 霍尼韦尔 | 22% |\n| 2 | Sensirion | 10% |（数据来源：公司公告及行业公开资料）\n"
    fixed, fs = _fix(text)
    assert len(fs.fixes_applied) >= 1
    lines = fixed.split("\n")
    assert lines[1].rstrip().endswith("|"), f"表格行应恢复|结尾: {lines[1]}"
    assert "数据来源" in lines[2], f"来源标注应独立成段: {lines[2]}"


def test_normal_table_unchanged():
    """正常表格（以|开头且以|结尾）不应被修改。"""
    text = "| 公司 | 市占率 |\n|------|--------|\n| 霍尼韦尔 | 22% |\n| Sensirion | 10% |\n"
    fixed, fs = _fix(text)
    assert fixed == text, f"正常表格不应被改: {fs.fixes_applied}"
    assert len(fs.fixes_applied) == 0


def test_patrol_includes_fixer():
    """patrol 主流程应调用表格尾随正文修复器。"""
    src = (Path(__file__).parent.parent / "pipeline" / "format_sheriff.py").read_text(encoding="utf-8")
    assert "patrol" in src and "_fix_table_trailing_prose" in src
    # 确认 patrol 里调用了
    patrol_start = src.index("def patrol")
    patrol_end = src.index("def report", patrol_start)
    patrol_body = src[patrol_start:patrol_end]
    assert "_fix_table_trailing_prose" in patrol_body, "patrol 应调用表格修复器"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
