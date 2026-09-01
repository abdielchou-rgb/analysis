"""S3-1/S3-2/S3-3: Evidence chain tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_claim_citation_jsonld_import():
    from core.claim_citation import render_jsonld_ledger

    assert callable(render_jsonld_ledger)


def test_claim_citation_footnote_url_map():
    from core.claim_citation import build_footnote_url_map

    claims = [
        {"refs": ["fig_revenue"], "sources": ["https://example.com"]},
        {"refs": ["fig_profit"], "sources": []},
    ]
    provenance = {
        "sources": [
            {"key": "fig_revenue", "url": "https://example.com/data"},
        ]
    }
    url_map = build_footnote_url_map(claims, provenance)
    assert "1" in url_map
    assert url_map["1"] == "https://example.com/data"


def test_signal_divergence_import():
    from core.signal_divergence import detect_divergence

    assert callable(detect_divergence)


def test_signal_divergence_sentiment_fundamental():
    from core.signal_divergence import detect_divergence

    divergence = detect_divergence(
        fig_sentiment={"score": -0.8, "trend": "negative"},
        fig_revenue={"yoy_growth": 0.15},
        fig_valuation=None,
    )
    assert len(divergence) > 0
    assert divergence[0]["type"] == "sentiment_fundamental"


def test_signal_divergence_no_divergence():
    from core.signal_divergence import detect_divergence

    divergence = detect_divergence(
        fig_sentiment={"score": 0.5, "trend": "positive"},
        fig_revenue={"yoy_growth": 0.20},
        fig_valuation=None,
    )
    assert len(divergence) == 0


def test_falsification_tracker_import():
    from scripts.falsification_tracker import check_falsification

    assert callable(check_falsification)


def test_exporter_hyperlink_import():
    from export.exporter import ReportExporter

    exporter = ReportExporter()
    assert hasattr(exporter, "_add_hyperlink")
    assert hasattr(exporter, "set_footnote_urls")


def test_exporter_footnote_urls():
    from export.exporter import ReportExporter

    exporter = ReportExporter()
    exporter.set_footnote_urls({"1": "https://example.com"})
    assert exporter._footnote_urls == {"1": "https://example.com"}
