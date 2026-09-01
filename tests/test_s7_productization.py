"""S7-1/S7-2/S7-3/S7-4: Productization tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_cost_panel_import():
    from scripts.cost_panel import main

    assert callable(main)


def test_consolidate_data_import():
    from scripts.consolidate_data import consolidate

    assert callable(consolidate)


def test_consolidate_data_dry_run():
    from scripts.consolidate_data import consolidate

    results = consolidate(dry_run=True)
    assert isinstance(results, list)


def test_run_reports_batch_state():
    from scripts.run_reports import _load_batch_state, _save_batch_state

    _save_batch_state("test_batch", {"results": [], "batch_id": "test_batch"})
    state = _load_batch_state("test_batch")
    assert state is not None
    assert state["batch_id"] == "test_batch"
    # cleanup
    from pathlib import Path

    batch_file = Path(__file__).resolve().parent.parent / "data" / "batches" / "test_batch.json"
    if batch_file.exists():
        batch_file.unlink()


def test_run_reports_import():
    from scripts.run_reports import run_reports

    assert callable(run_reports)


def test_web_app_import():
    """Verify web app has new routes."""
    from web.app import app

    routes = [r.path for r in app.routes]
    assert "/workbench" in routes
    assert "/api/batches" in routes
    assert "/api/review/{job_id}/approve" in routes
    assert "/api/review/{job_id}/reject" in routes
