import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from constants import CHART_TITLES, TREND_ARROW, TREND_COLOR, UNIT_SUFFIXES
from models import TimeSeriesPoint, SignalResult
from utils.helpers import logger

CHART_DIR = Path(tempfile.gettempdir()) / "macro_charts"


def _ensure_chart_dir() -> Path:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    return CHART_DIR


def generate_chart(
    dataset: str,
    time_series: list[TimeSeriesPoint],
    trend: str | None = None,
) -> str | None:
    if not time_series or len(time_series) < 2:
        logger.warning("Not enough data to chart %s", dataset)
        return None

    _ensure_chart_dir()

    dates = [datetime.strptime(p.date, "%Y-%m-%d") for p in time_series]
    values = [p.value for p in time_series]

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    ax.plot(dates, values, color="#00d4ff", linewidth=2, marker="o", markersize=3)
    ax.fill_between(dates, values, alpha=0.15, color="#00d4ff")

    ax.set_title(
        CHART_TITLES.get(dataset, dataset),
        color="white", fontsize=14, fontweight="bold", pad=12,
    )

    suffix = UNIT_SUFFIXES.get(dataset, "")
    ax.set_ylabel(f"Value{' (' + suffix + ')' if suffix else ''}", color="#aaaaaa", fontsize=10)
    ax.tick_params(colors="#aaaaaa", labelsize=9)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
    fig.autofmt_xdate(rotation=30)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")
    ax.grid(axis="y", color="#333333", linewidth=0.5, alpha=0.7)

    if trend and values:
        arrow = TREND_ARROW.get(trend, "")
        color = TREND_COLOR.get(trend, "white")
        ax.annotate(
            f" {arrow} {values[-1]:.2f}",
            xy=(dates[-1], values[-1]),
            fontsize=11, fontweight="bold", color=color,
        )

    plt.tight_layout()
    filepath = str(CHART_DIR / f"{dataset}.png")
    fig.savefig(filepath, dpi=130, bbox_inches="tight")
    plt.close(fig)

    logger.info("Chart saved: %s", filepath)
    return filepath


def generate_all_charts(
    all_time_series: dict[str, list[TimeSeriesPoint]],
    signals: dict[str, SignalResult],
) -> dict[str, str]:
    paths: dict[str, str] = {}
    for dataset, series in all_time_series.items():
        trend = signals[dataset].trend if dataset in signals else None
        path = generate_chart(dataset, series, trend=trend)
        if path:
            paths[dataset] = path
    return paths
