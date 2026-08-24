"""R82 — 行业键精确匹配/防串标回归测试。"""
import os, sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_oil_level_correct():
    """油位传感器应归油位键。"""
    from pipeline.universe_build import UniverseBuilder
    b = UniverseBuilder()
    key = b._infer_industry_key("油位传感器", {"chart_data": {"company_intro": "x"}})
    assert key == "油位传感器", f"油位应归油位键: {key}"


def test_liquid_level_not_oil():
    """液位传感器不得归油位键（串标根治）。"""
    from pipeline.universe_build import UniverseBuilder
    b = UniverseBuilder()
    key = b._infer_industry_key("液位传感器", {"chart_data": {"company_intro": "x"}})
    assert key == "液位仪表", f"液位应归液位仪表: {key}"


def test_material_level_correct():
    """物位传感器应归物位。"""
    from pipeline.universe_build import UniverseBuilder
    b = UniverseBuilder()
    key = b._infer_industry_key("物位传感器", {"chart_data": {"company_intro": "x"}})
    assert key == "物位", f"物位应归物位: {key}"


def test_short_name_via_alias():
    """裸词'油位'/'液位'经别名表归位。"""
    from pipeline.universe_build import UniverseBuilder
    b = UniverseBuilder()
    assert b._infer_industry_key("油位", {}) == "油位传感器"
    assert b._infer_industry_key("液位", {}) == "液位仪表"


def test_force_sensor_not_oil():
    """力传感器应归传感器，不串油位。"""
    from pipeline.universe_build import UniverseBuilder
    b = UniverseBuilder()
    key = b._infer_industry_key("力传感器", {})
    assert key == "传感器", f"力传感应归传感器: {key}"


if __name__ == "__main__":
    import traceback
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  OK {name}"); passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed")
