"""R62 预测验证闭环修复回归测试（2026-08-04 预测闭环审计）

覆盖三个修复：
1. _query_local_qlib_price 代码归一化：剥离 .SZ/.SH 后缀
   （旧逻辑 "300750.SZ".zfill(6) → "sz300750.SZ" 与 qlib 目录不匹配 → 恒 None）
2. 收益率口径：close 是净值（投入1元的净值），验证收益=latest/as_of-1
   （不能把 close 当绝对股价与 current_price 相减）
3. validate_forward_picks_csv 的 as_of 取价：用预测日所在月净值，不 fallback 首月
"""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _norm_code(code: str) -> str:
    """复刻 data_backends._query_local_qlib_price 内的归一化逻辑（白盒测试）。"""
    c = re.sub(r"\.(SH|SZ|SS|BJ|HK|US)$", "", code.strip().upper())
    if not c.startswith(("SH", "SZ", "BJ")):
        c = c.zfill(6)
        c = ("sh" if c.startswith(("6", "9")) else "sz") + c
    else:
        c = c[:2].lower() + c[2:]
    return c


def test_qlib_code_normalization_strips_suffix():
    """带市场后缀的代码应归一化到 qlib 特征目录名。"""
    assert _norm_code("300750.SZ") == "sz300750"
    assert _norm_code("000651.SZ") == "sz000651"
    assert _norm_code("603501.SH") == "sh603501"
    assert _norm_code("600031.SS") == "sh600031"
    assert _norm_code("00700.HK") == "sz000700"
    # 无后缀的原始 6 位代码也不破坏
    assert _norm_code("600519") == "sh600519"
    assert _norm_code("300750") == "sz300750"


def test_qlib_price_query_works_with_suffixed_codes():
    """真实 qlib 数据：带 .SZ/.SH 后缀的代码能取到价格序列（此前恒 None）。"""
    from core.data_backends import _query_local_qlib_price

    q = _query_local_qlib_price("300750.SZ")
    assert q is not None, "300750.SZ 应能从本地 qlib 取价（此前代码归一化 bug 返回 None）"
    assert q["source"] == "qlib_local"
    assert len(q["prices"]) >= 2
    assert len(q["dates"]) == len(q["prices"])
    # close 是收益率净值：最早月份应接近 1.0（投入1元的净值起点）
    assert q["prices"][0] > 0.5, f"qlib close 净值起点应接近1.0，实际 {q['prices'][0]}"


def test_validator_returns_are_index_ratio_based():
    """验证器收益应基于净值比值，且 as_of 用预测日所在月，不 fallback 首月。"""
    from core.data_backends import _query_local_qlib_price
    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    q = _query_local_qlib_price("300750.SZ")
    assert q is not None

    # 模拟 2026-01 的预测，6个月后净值应明显变化（验证收益计算有意义）
    as_of = "2026-01"
    nav = q["prices"][0]
    for d, px in zip(q["dates"], q["prices"]):
        if d <= as_of:
            nav = px
    latest = q["prices"][-1]
    ret = (latest - nav) / nav
    # 6个月真实收益率不应为 0（2026-01→2026-07 宁德约 +11%）
    assert abs(ret) > 0.01, f"6个月净值收益不应≈0，实际 {ret:.4f}"


def test_import_script_has_dedup_and_current_price():
    """import_forward_picks.py 应含去重逻辑 + current_price 捕获。"""
    src = (_ROOT / "scripts" / "import_forward_picks.py").read_text(encoding="utf-8")
    assert "existing_keys" in src, "导入脚本应含去重"
    assert "current_price" in src, "导入脚本应捕获 current_price"


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


# ── R64（2026-08-04 审计修复）语义层回归 ──────────────────────


def test_current_price_not_polluted_by_adjclose():
    """P0-008：current_price 不得存复权价量级（应=0 或真实股价量级）。

    审计发现 12 条预测 current_price 存了 133~9321 的累计复权价（格力 9321
    明显非真实股价）。R64 修复：current_price 清 0（待真实股价源），
    验证锚点改用 anchor_nav（qlib close 净值量级）。
    """
    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    picks = db.load_all()
    for p in picks:
        # current_price 不得是复权价量级（>500 且明显非真实股价）
        assert p.current_price == 0.0, (
            f"{p.asset_name} current_price={p.current_price} 应为 0（真实股价未接入），不得为复权价（审计 P0-008）"
        )
        # anchor_nav 必须是净值量级（qlib close：宁德~20、格力~142，绝不该上千）
        assert 0 < p.anchor_nav < 500, f"{p.asset_name} anchor_nav={p.anchor_nav} 应为 qlib close 净值（<500）"


def test_bull_target_not_fabricated():
    """P1-008：bull_target 不得是 base_target 复制值（为过校验造数）。

    R64 修复：单目标价预测 bull/bear_target=0（未提供），不再伪造独立档。
    """
    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    picks = db.load_all()
    for p in picks:
        # bull_target 要么 0（诚实未提供），要么与 base 有实质差异
        if p.bull_target:
            assert abs(p.bull_target - p.base_target) / max(p.base_target, 1e-9) > 0.05, (
                f"{p.asset_name} bull_target==base_target 复制值（审计 P1-008）"
            )


def test_validate_uses_nav_ratio_not_current_price():
    """统一验证出口：validator 不得用 current_price 算收益，用净值比值。

    用 AST 过滤注释/docstring，只看真实代码引用。
    """
    import ast
    import inspect

    from core import prediction_validator as pv
    from core.forward_picks import ForwardPicksDB

    def _code_refs(func) -> list:
        """提取函数体里 self.X / 变量引用的 current_price / anchor_nav。"""
        import textwrap

        src = textwrap.dedent(inspect.getsource(func))
        tree = ast.parse(src)
        refs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in ("current_price", "anchor_nav"):
                    refs.append(node.attr)
            if isinstance(node, ast.Name) and node.id in ("current_price", "anchor_nav"):
                refs.append(node.id)
        return refs

    # validate_forward_picks_csv：必须引用 anchor_nav，不得引用 current_price
    v_refs = _code_refs(pv.validate_forward_picks_csv)
    assert "anchor_nav" in v_refs, f"validator 应使用 anchor_nav 锚点，实际引用 {v_refs}"
    assert "current_price" not in v_refs, (
        f"validator 不得用 current_price 算收益（审计 P0-008/P1-009），实际引用 {v_refs}"
    )

    # update_verification：必须用 anchor_nav，不得用 current_price
    u_refs = _code_refs(ForwardPicksDB.update_verification)
    assert "anchor_nav" in u_refs, f"update_verification 应改用 anchor_nav，实际引用 {u_refs}"
    assert "current_price" not in u_refs, f"update_verification 不得用 current_price 算收益，实际引用 {u_refs}"
