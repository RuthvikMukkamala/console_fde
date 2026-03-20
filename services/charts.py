import base64
import os
import tempfile
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

import requests

from utils.helpers import logger

DISPLAY_NAMES: dict[str, str] = {
    "inflation": "Inflation (CPI)",
    "labor_market": "Unemployment Rate",
    "treasury_yields": "10-Year Treasury Yield",
    "inflation_expectations": "10-Year Inflation Expectations",
}

UNIT_SUFFIXES: dict[str, str] = {
    "inflation": "",
    "labor_market": "%",
    "treasury_yields": "%",
    "inflation_expectations": "%",
}

CHART_DIR = Path(tempfile.gettempdir()) / "macro_charts"


def _ensure_chart_dir() -> Path:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    return CHART_DIR


def generate_chart(
    dataset: str,
    time_series: list[dict[str, Any]],
    trend: str | None = None,
) -> str | None:
    """Generate a PNG chart for a single indicator and return the file path."""
    if not time_series or len(time_series) < 2:
        logger.warning("Not enough data to chart %s", dataset)
        return None

    _ensure_chart_dir()

    dates = [datetime.strptime(p["date"], "%Y-%m-%d") for p in time_series]
    values = [p["value"] for p in time_series]

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    ax.plot(dates, values, color="#00d4ff", linewidth=2, marker="o", markersize=3)
    ax.fill_between(dates, values, alpha=0.15, color="#00d4ff")

    ax.set_title(
        DISPLAY_NAMES.get(dataset, dataset),
        color="white",
        fontsize=14,
        fontweight="bold",
        pad=12,
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

    if trend and len(values) >= 1:
        arrow = {"UP": "\u2191", "DOWN": "\u2193", "FLAT": "\u2192"}.get(trend, "")
        color = {"UP": "#ff6b6b", "DOWN": "#51cf66", "FLAT": "#ffd43b"}.get(trend, "white")
        ax.annotate(
            f" {arrow} {values[-1]:.2f}",
            xy=(dates[-1], values[-1]),
            fontsize=11,
            fontweight="bold",
            color=color,
        )

    plt.tight_layout()
    filepath = str(CHART_DIR / f"{dataset}.png")
    fig.savefig(filepath, dpi=130, bbox_inches="tight")
    plt.close(fig)

    logger.info("Chart saved: %s", filepath)
    return filepath


def generate_all_charts(
    all_time_series: dict[str, list[dict[str, Any]]],
    signals: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Generate charts for all datasets. Returns {dataset: filepath}."""
    paths: dict[str, str] = {}
    for dataset, series in all_time_series.items():
        trend = signals.get(dataset, {}).get("trend")
        path = generate_chart(dataset, series, trend=trend)
        if path:
            paths[dataset] = path
    return paths


def upload_to_imgur(filepath: str) -> str | None:
    """Upload a PNG to imgur anonymously. Returns the image URL or None."""
    client_id = os.getenv("IMGUR_CLIENT_ID", "")
    if not client_id:
        logger.warning("IMGUR_CLIENT_ID not set — skipping image upload for %s", filepath)
        return None

    try:
        with open(filepath, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        resp = requests.post(
            "https://api.imgur.com/3/image",
            headers={"Authorization": f"Client-ID {client_id}"},
            data={"image": image_data, "type": "base64"},
            timeout=20,
        )

        if resp.status_code == 429:
            logger.warning("Imgur rate-limited")
            return None

        resp.raise_for_status()
        url = resp.json()["data"]["link"]
        logger.info("Uploaded chart to imgur: %s", url)
        return url

    except Exception as exc:
        logger.error("Imgur upload failed for %s: %s", filepath, exc)
        return None


def upload_all_charts(chart_paths: dict[str, str]) -> dict[str, str]:
    """Upload all chart images to imgur. Returns {dataset: url}."""
    urls: dict[str, str] = {}
    for dataset, path in chart_paths.items():
        url = upload_to_imgur(path)
        if url:
            urls[dataset] = url
    return urls
