from typing import Any

from utils.helpers import logger, today_str

TREND_ARROW = {"UP": "\u2191", "DOWN": "\u2193", "FLAT": "\u2192"}

SIGNAL_MAP: dict[str, dict[str, str]] = {
    "inflation": {
        "UP": "Inflation pressure increasing",
        "DOWN": "Disinflation trend",
        "FLAT": "Inflation stable",
    },
    "labor_market": {
        "UP": "Labor softening (unemployment rising)",
        "DOWN": "Tight labor market (unemployment falling)",
        "FLAT": "Labor market stable",
    },
    "treasury_yields": {
        "UP": "Financial conditions tightening",
        "DOWN": "Easing financial conditions",
        "FLAT": "Yields stable",
    },
    "inflation_expectations": {
        "UP": "Forward inflation risk rising",
        "DOWN": "Inflation expectations anchored / falling",
        "FLAT": "Expectations stable",
    },
}

FLAT_THRESHOLD = 0.005

# Map each dataset to the primary numeric field in its Polygon response
# Ordered list of fields to try per dataset (first match wins)
VALUE_FIELDS: dict[str, list[str]] = {
    "inflation": ["cpi_year_over_year", "cpi"],
    "labor_market": ["unemployment_rate"],
    "treasury_yields": ["yield_10_year"],
    "inflation_expectations": ["model_10_year"],
}

UNIT_LABELS: dict[str, str] = {
    "inflation": "% YoY CPI",
    "labor_market": "% unemployment",
    "treasury_yields": "% 10Y yield",
    "inflation_expectations": "% 10Y model",
}


def _pick_field(record: dict, candidates: list[str]) -> float | None:
    """Return the value of the first field found in a record."""
    for field in candidates:
        val = record.get(field)
        if val is not None:
            return float(val)
    return None


def extract_time_series(
    raw: dict[str, Any] | None,
    dataset: str = "",
) -> list[dict[str, Any]]:
    """Extract the full time series from a Polygon Fed response.

    Returns a list of {"date": "YYYY-MM-DD", "value": float} dicts,
    ascending by date.
    """
    if raw is None:
        return []

    results = raw.get("results")
    if not results or not isinstance(results, list):
        return []

    candidates = VALUE_FIELDS.get(dataset, ["value"])
    series: list[dict[str, Any]] = []
    for record in results:
        val = _pick_field(record, candidates)
        date = record.get("date")
        if val is not None and date is not None:
            series.append({"date": date, "value": round(val, 4)})
    return series


def _extract_values(
    raw: dict[str, Any] | None,
    dataset: str = "",
) -> tuple[float | None, float | None]:
    """Pull the two most recent observation values from a Polygon Fed response.

    Results are ascending by date, so index -1 = latest, -2 = previous.
    """
    if raw is None:
        return None, None

    results = raw.get("results")
    if not results or not isinstance(results, list):
        return None, None

    candidates = VALUE_FIELDS.get(dataset, ["value"])

    if len(results) < 2:
        val = _pick_field(results[-1], candidates)
        return val, None

    latest = _pick_field(results[-1], candidates)
    previous = _pick_field(results[-2], candidates)
    return latest, previous


def compute_trend(
    raw: dict[str, Any] | None,
    dataset: str = "",
) -> dict[str, Any] | None:
    """Compute trend from raw API data. Returns dict with latest, previous, delta, trend."""
    latest, previous = _extract_values(raw, dataset)
    if latest is None:
        return None

    if previous is None:
        return {
            "latest": latest,
            "previous": None,
            "delta": None,
            "trend": "FLAT",
        }

    delta = latest - previous
    if abs(delta) < FLAT_THRESHOLD:
        trend = "FLAT"
    elif delta > 0:
        trend = "UP"
    else:
        trend = "DOWN"

    return {
        "latest": round(latest, 4),
        "previous": round(previous, 4),
        "delta": round(delta, 4),
        "trend": trend,
    }


def generate_signals(
    trends: dict[str, dict[str, Any] | None],
) -> dict[str, dict[str, Any]]:
    """Attach human-readable signal text to each trend."""
    signals: dict[str, dict[str, Any]] = {}
    for name, trend_data in trends.items():
        if trend_data is None:
            continue
        direction = trend_data["trend"]
        signal_text = SIGNAL_MAP.get(name, {}).get(direction, "No signal")
        signals[name] = {**trend_data, "signal": signal_text}
    return signals


def determine_regime(signals: dict[str, dict[str, Any]]) -> str:
    """Determine overall macro regime from individual signals.

    Heuristic:
      - Count hawkish signals (inflation UP, expectations UP, yields UP, labor UP)
      - Count dovish signals (the opposite directions)
      - Majority wins; tie → NEUTRAL
    """
    # Labor market uses unemployment_rate: UP = loosening (dovish), DOWN = tightening (hawkish)
    hawkish_combos = {
        ("inflation", "UP"),
        ("inflation_expectations", "UP"),
        ("treasury_yields", "UP"),
        ("labor_market", "DOWN"),
    }
    dovish_combos = {
        ("inflation", "DOWN"),
        ("inflation_expectations", "DOWN"),
        ("treasury_yields", "DOWN"),
        ("labor_market", "UP"),
    }

    hawk = 0
    dove = 0
    for name, info in signals.items():
        pair = (name, info["trend"])
        if pair in hawkish_combos:
            hawk += 1
        elif pair in dovish_combos:
            dove += 1

    if hawk > dove:
        return "HAWKISH"
    elif dove > hawk:
        return "DOVISH"
    return "NEUTRAL"


def generate_report_text(
    signals: dict[str, dict[str, Any]],
    regime: str,
) -> str:
    """Build the human-readable macro report string."""
    date = today_str()
    lines = [f"Macro Report ({date})", ""]

    display_names = {
        "inflation": "Inflation",
        "labor_market": "Labor Market",
        "treasury_yields": "Treasury Yields",
        "inflation_expectations": "Inflation Expectations",
    }

    for name in ("inflation", "labor_market", "treasury_yields", "inflation_expectations"):
        info = signals.get(name)
        if info is None:
            lines.append(f"- {display_names[name]}: DATA UNAVAILABLE")
            continue

        arrow = TREND_ARROW.get(info["trend"], "?")
        prev = info.get("previous", "?")
        latest = info.get("latest", "?")
        sig = info.get("signal", "")

        if prev is not None:
            lines.append(f"- {display_names[name]}: {arrow} {prev} -> {latest} | {sig}")
        else:
            lines.append(f"- {display_names[name]}: {arrow} {latest} | {sig}")

    regime_labels = {
        "HAWKISH": "Hawkish / Tightening Bias",
        "DOVISH": "Dovish / Easing Bias",
        "NEUTRAL": "Neutral / Mixed Signals",
    }
    lines.append("")
    lines.append(f"Overall Regime: {regime_labels.get(regime, regime)}")
    return "\n".join(lines)
