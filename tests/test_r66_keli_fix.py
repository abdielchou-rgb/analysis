# -*- coding: utf-8 -*-
"""R66 (2026-08-04) 回归测试 — 柯力传感写作失败四重根因修复

覆盖：
1. score 读取 bug：e2e 用 overall_score 而非 score（柯力 score=[0,0,0]）
2. charts 失败不再短路全量重写 → 全段局部重写
3. best-so-far 稿保留（失败时用最高分稿）
4. _serialize_data 注入 fig_* 数值（enrich 数据进正文）
"""
import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_score_reads_overall_score():
    """e2e 应读 gate.get('overall_score') 而非恒 0 的 'score'。"""
    src = _src("pipeline/e2e_orchestrator.py")
    assert 'gate.get("overall_score"' in src, "应读 overall_score"
    # 不应再有裸 gate.get("score", 0) 用于分数
    assert 'ig_score = gate.get("overall_score"' in src
    assert 'gate.get("overall_score", gate.get("score", 0))' in src or 'gate.get("overall_score"' in src


def test_charts_failure_no_full_rewrite():
    """charts 失败应返回全段局部重写，不短路 return None 全量重写。

    R78（2026-08-05 Phase3.1）：定位逻辑抽到 pipeline/fail_segment_locator.py，
    e2e 转发。断言改为检查新模块。
    """
    src = _src("pipeline/fail_segment_locator.py")
    assert "全段局部重写补图引用" in src, "charts 失败应改为局部重写"
    # 旧逻辑"return None 全量重写"不应再是 charts 分支默认
    old_branch = '图表类失败 → 全量重写（嵌入是全局的）'
    assert old_branch not in src, "charts 不应再触发全量重写"
    # 主文件应转发
    e2e_src = _src("pipeline/e2e_orchestrator.py")
    assert "fail_segment_locator" in e2e_src, "e2e 应转发到 fail_segment_locator"


def test_best_so_far_preserved():
    """e2e 应保留 best-so-far 稿并在失败时回滚。"""
    src = _src("pipeline/e2e_orchestrator.py")
    assert "_best_so_far" in src, "应有 best-so-far 记录"
    assert "保留最佳稿" in src, "失败时应保留最佳稿"


def test_serialize_injects_fig_values():
    """_serialize_data 应注入 fig_* 数值，而非只列键名。

    R78（2026-08-05 Phase3.1）：序列化逻辑抽到 pipeline/sw_serialize.py，
    section_writer 转发。断言改为检查新模块。
    """
    src = _src("pipeline/sw_serialize.py")
    assert "fig_keys" in src
    # 修复后应有注入 fig 值逻辑
    assert "图表数据键" in src
    # R66(2026-08-04) 修复时把截断长度从 600 调到 900（保证注入正文的数据更完整）
    assert "str(fv)[:900]" in src or "fv[:900]" in src, "应注入 fig 值（截断900）"
    # 主文件应转发（兼容外部调用）
    sw_src = _src("pipeline/section_writer.py")
    assert "sw_serialize" in sw_src, "section_writer 应转发到 sw_serialize"


def test_e2e_syntax_valid():
    """e2e_orchestrator.py 语法合法。"""
    ast.parse(_src("pipeline/e2e_orchestrator.py"))


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
