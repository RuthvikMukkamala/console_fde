from typing import Any

from constants import (
    DATASET_ORDER,
    DISPLAY_NAMES,
    FLAT_THRESHOLD,
    HAWKISH_COMBOS,
    DOVISH_COMBOS,
    REGIME_LABELS,
    SIGNAL_MAP,
    TREND_ARROW,
    VALUE_FIELDS,
)
from models import TimeSeriesPoint, TrendResult, SignalResult
from utils.helpers import today_str


def _pick_field(record: dict, candidates: list[str]) -> float | None:
    for field in candidates:
        val = record.get(field)
        if val is not None:
            return float(val)
    return None


def extract_time_series(raw: dict[str, Any] | None, dataset: str = "") -> list[TimeSeriesPoint]:
    if raw is None:
        return []

    results = raw.get("results")
    if not results or not isinstance(results, list):
        return []

    candidates = VALUE_FIELDS.get(dataset, ["value"])
    series: list[TimeSeriesPoint] = []
    for record in results:
        val = _pick_field(record, candidates)
        date = record.get("date")
        if val is not None and date is not None:
            series.append(TimeSeriesPoint(date=date, value=round(val, 4)))
    return series


def compute_trend(raw: dict[str, Any] | None, dataset: str = "") -> TrendResult | None:
    series = extract_time_series(raw, dataset)
    if not series:
        return None

    latest = series[-1].value
    previous = series[-2].value if len(series) >= 2 else None

    if previous is None:
        return TrendResult(latest=latest, trend="FLAT")

    delta = latest - previous
    if abs(delta) < FLAT_THRESHOLD:
        trend = "FLAT"
    elif delta > 0:
        trend = "UP"
    else:
        trend = "DOWN"

    return TrendResult(
        latest=round(latest, 4),
        previous=round(previous, 4),
        delta=round(delta, 4),
        trend=trend,
    )


def generate_signals(trends: dict[str, TrendResult | None]) -> dict[str, SignalResult]:
    signals: dict[str, SignalResult] = {}
    for name, trend in trends.items():
        if trend is None:
            continue
        signal_text = SIGNAL_MAP.get(name, {}).get(trend.trend, "No signal")
        signals[name] = SignalResult(**trend.model_dump(), signal=signal_text)
    return signals


def determine_regime(signals: dict[str, SignalResult]) -> str:
    hawk = sum(1 for n, s in signals.items() if (n, s.trend) in HAWKISH_COMBOS)
    dove = sum(1 for n, s in signals.items() if (n, s.trend) in DOVISH_COMBOS)

    if hawk > dove:
        return "HAWKISH"
    elif dove > hawk:
        return "DOVISH"
    return "NEUTRAL"


def generate_report_text(signals: dict[str, SignalResult], regime: str) -> str:
    date = today_str()
    lines = [f"Macro Report ({date})", ""]

    for name in DATASET_ORDER:
        sig = signals.get(name)
        display = DISPLAY_NAMES.get(name, name)
        if sig is None:
            lines.append(f"- {display}: DATA UNAVAILABLE")
            continue

        arrow = TREND_ARROW.get(sig.trend, "?")
        if sig.previous is not None:
            lines.append(f"- {display}: {arrow} {sig.previous} -> {sig.latest} | {sig.signal}")
        else:
            lines.append(f"- {display}: {arrow} {sig.latest} | {sig.signal}")

    lines.append("")
    lines.append(f"Overall Regime: {REGIME_LABELS.get(regime, regime)}")
    return "\n".join(lines)
