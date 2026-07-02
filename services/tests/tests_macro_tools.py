"""
Tests for the economic-calendar tool's pure filter (no network).
"""
from datetime import datetime, timezone

from apps.genflows.trading_futures.macro_tools import MacroTools

NOW = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)

SAMPLE = [
    # past USD High -> excluded
    {"title": "CPI m/m", "country": "USD", "date": "2026-06-28T08:00:00+00:00", "impact": "High",
     "forecast": "0.2%", "previous": "0.3%"},
    # upcoming USD High within horizon -> included
    {"title": "FOMC Statement", "country": "USD", "date": "2026-06-29T18:00:00+00:00", "impact": "High",
     "forecast": "", "previous": ""},
    # upcoming USD High sooner -> included, should sort first
    {"title": "Core PCE m/m", "country": "USD", "date": "2026-06-28T20:00:00+00:00", "impact": "High",
     "forecast": "0.1%", "previous": "0.2%"},
    # upcoming USD Medium -> excluded by impact
    {"title": "Consumer Confidence", "country": "USD", "date": "2026-06-29T14:00:00+00:00", "impact": "Medium"},
    # upcoming EUR High -> excluded by country
    {"title": "ECB Rate", "country": "EUR", "date": "2026-06-29T12:00:00+00:00", "impact": "High"},
    # far-future USD High beyond horizon -> excluded
    {"title": "NFP", "country": "USD", "date": "2026-07-05T12:30:00+00:00", "impact": "High"},
]


def test_parse_keeps_only_upcoming_high_impact_usd_sorted():
    out = MacroTools._parse_events(SAMPLE, now=NOW, horizon_hours=48)
    titles = [e["title"] for e in out]
    assert titles == ["Core PCE m/m", "FOMC Statement"]  # sorted by soonest, filtered correctly


def test_parse_excludes_past_events():
    out = MacroTools._parse_events(SAMPLE, now=NOW, horizon_hours=48)
    assert all(e["hours_until"] >= 0 for e in out)
    assert "CPI m/m" not in [e["title"] for e in out]


def test_parse_respects_horizon():
    # 2h horizon keeps only Core PCE (8h away is excluded too -> actually PCE is 8h; use 9h)
    out = MacroTools._parse_events(SAMPLE, now=NOW, horizon_hours=9)
    assert [e["title"] for e in out] == ["Core PCE m/m"]


def test_parse_can_widen_country_and_impact():
    out = MacroTools._parse_events(
        SAMPLE, now=NOW, impacts=("High", "Medium"), countries=("USD", "EUR"), horizon_hours=48
    )
    titles = set(e["title"] for e in out)
    assert {"Core PCE m/m", "FOMC Statement", "Consumer Confidence", "ECB Rate"} <= titles
