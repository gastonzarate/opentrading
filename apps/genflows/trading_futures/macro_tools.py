"""
Macro tools for the trading agent: a free, no-API-key economic calendar.

The highest-value, most *scheduled* market-moving events for crypto (via its
correlation to USD macro) are Fed decisions, CPI, NFP, etc. This exposes the
upcoming high-impact events so the agent can avoid opening right before a known
catalyst and can size/behave accordingly. Source: ForexFactory's public weekly
calendar feed (faireconomy.media), which needs no key.
"""
from datetime import datetime, timezone

import httpx
from llama_index.core.tools import FunctionTool

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


class MacroTools:
    """Exposes an economic-calendar tool as a LlamaIndex FunctionTool."""

    def list_tools(self) -> list[FunctionTool]:
        return [
            FunctionTool.from_defaults(
                fn=self._economic_calendar,
                name="economic_calendar",
                description=(
                    "Returns UPCOMING high-impact macro events (economic calendar) for the next "
                    "N hours, e.g. FOMC/Fed decisions, CPI, NFP. Crypto is strongly correlated to "
                    "USD macro, so these are the most reliable *scheduled* catalysts.\n\n"
                    "Use it to AVOID opening a new position right before a high-impact release "
                    "(volatility spike / liquidation risk) and to plan around known events. "
                    "Each event has: title, time (UTC), country, impact, forecast, previous.\n\n"
                    "PARAMS: hours_ahead (default 48). Defaults to USD High-impact events."
                ),
            )
        ]

    # ------------------------------------------------------------------
    def _economic_calendar(self, hours_ahead: int = 48) -> dict:
        """Fetch and filter the economic calendar to upcoming high-impact USD events."""
        try:
            resp = httpx.get(CALENDAR_URL, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            events = resp.json()
        except Exception as e:  # network / parse errors are non-fatal for the agent
            return {"error": f"Could not fetch economic calendar: {e}", "events": []}

        upcoming = self._parse_events(events, now=datetime.now(timezone.utc), horizon_hours=hours_ahead)
        return {
            "source": "ForexFactory / faireconomy (this week)",
            "count": len(upcoming),
            "events": upcoming,
            "note": "USD High-impact only. Avoid opening right before these; expect volatility.",
        }

    @staticmethod
    def _parse_events(
        events: list,
        now: datetime,
        impacts: tuple = ("High",),
        countries: tuple = ("USD",),
        horizon_hours: int = 48,
    ) -> list:
        """
        Pure filter: keep events that are in the future, within the horizon, and
        match the requested impact/country. Returned sorted by time ascending.
        """
        out = []
        for ev in events or []:
            if ev.get("impact") not in impacts:
                continue
            if ev.get("country") not in countries:
                continue
            raw = ev.get("date")
            if not raw:
                continue
            try:
                when = datetime.fromisoformat(raw)
            except (ValueError, TypeError):
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            delta_hours = (when - now).total_seconds() / 3600
            if delta_hours < 0 or delta_hours > horizon_hours:
                continue
            out.append(
                {
                    "title": ev.get("title"),
                    "time_utc": when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "country": ev.get("country"),
                    "impact": ev.get("impact"),
                    "forecast": ev.get("forecast", ""),
                    "previous": ev.get("previous", ""),
                    "hours_until": round(delta_hours, 1),
                }
            )
        out.sort(key=lambda e: e["hours_until"])
        return out
