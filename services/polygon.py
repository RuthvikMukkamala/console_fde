import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from utils.helpers import logger

BASE_URL = "https://api.polygon.io/fed/v1"

ENDPOINTS: dict[str, str] = {
    "inflation": f"{BASE_URL}/inflation",
    "labor_market": f"{BASE_URL}/labor-market",
    "treasury_yields": f"{BASE_URL}/treasury-yields",
    "inflation_expectations": f"{BASE_URL}/inflation-expectations",
}

# Monthly datasets need more calendar days per observation than daily ones
_CALENDAR_DAYS_PER_OBS = {
    "inflation": 32,
    "labor_market": 32,
    "inflation_expectations": 32,
    "treasury_yields": 2,
}


def _get_api_key() -> str:
    key = os.getenv("POLYGON_API_KEY", "")
    if not key:
        raise RuntimeError("POLYGON_API_KEY environment variable is not set")
    return key


def _lookback_date(dataset: str, num_observations: int) -> str:
    """Calculate a date.gte value that covers roughly num_observations data points."""
    days_per_obs = _CALENDAR_DAYS_PER_OBS.get(dataset, 32)
    lookback_days = num_observations * days_per_obs + 60  # buffer
    dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return dt.strftime("%Y-%m-%d")


def fetch_data(
    dataset: str,
    limit: int = 100,
    timeout: int = 15,
) -> dict[str, Any] | None:
    """Fetch observations from a Polygon Fed endpoint.

    Uses date.gte to scope to recent data. Results are always ascending by date,
    so the last entry is the most recent observation.
    Returns the parsed JSON body on success, or None if the request fails.
    """
    url = ENDPOINTS.get(dataset)
    if url is None:
        logger.error("Unknown dataset requested: %s", dataset)
        return None

    params: dict[str, Any] = {
        "limit": 1000,
        "sort": "date",
        "date.gte": _lookback_date(dataset, limit),
        "apiKey": _get_api_key(),
    }

    try:
        logger.info("Fetching %s (target observations=%d, since=%s)", dataset, limit, params["date.gte"])
        resp = requests.get(url, params=params, timeout=timeout)

        if resp.status_code == 429:
            logger.warning("Rate-limited on %s – retry later", dataset)
            return None

        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        logger.info("Fetched %s – %d observations returned", dataset, len(results))
        return data

    except requests.exceptions.Timeout:
        logger.error("Timeout fetching %s", dataset)
    except requests.exceptions.HTTPError as exc:
        logger.error("HTTP error fetching %s: %s", dataset, exc)
    except requests.exceptions.RequestException as exc:
        logger.error("Request failed for %s: %s", dataset, exc)
    except ValueError:
        logger.error("Invalid JSON from %s", dataset)

    return None


def fetch_all(limit: int = 100) -> dict[str, dict[str, Any] | None]:
    """Fetch data from all four Fed endpoints. Returns a dict keyed by dataset name."""
    return {name: fetch_data(name, limit=limit) for name in ENDPOINTS}
