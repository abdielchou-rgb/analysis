"""S4-1/S4-2/S4-3: Framework self-adaptation tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_framework_effectiveness_import():
    from scripts.framework_effectiveness import main

    assert callable(main)


def test_framework_ranking_import():
    from core.method_reflection import get_framework_ranking

    assert callable(get_framework_ranking)


def test_framework_ranking_returns_list():
    from core.method_reflection import get_framework_ranking

    ranking = get_framework_ranking()
    assert isinstance(ranking, list)


def test_framework_ranking_structure():
    from core.method_reflection import get_framework_ranking

    ranking = get_framework_ranking()
    if ranking:
        item = ranking[0]
        assert "framework" in item
        assert "avg_gate" in item
        assert "pass_rate" in item
        assert "count" in item
        assert "score" in item


def test_framework_rationale_import():
    from core.framework_injector import inject_framework_rationale

    assert callable(inject_framework_rationale)


def test_framework_rationale_returns_string():
    from core.framework_injector import inject_framework_rationale

    result = inject_framework_rationale()
    assert isinstance(result, str)


def test_framework_injector_uses_ranking():
    """Verify inject_framework_prompt calls get_framework_ranking."""
    import inspect

    from core.framework_injector import inject_framework_prompt

    source = inspect.getsource(inject_framework_prompt)
    assert "get_framework_ranking" in source
