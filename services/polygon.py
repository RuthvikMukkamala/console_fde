from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from utils.helpers import logger


class RateLimitError(Exception):
    pass

BASE_URL = "https://api.polygon.io/fed/v1"

ENDPOINTS: dict[str, str] = {
    "inflation": f"{BASE_URL}/inflation",
    "labor_market": f"{BASE_URL}/labor-market",
    "treasury_yields": f"{BASE_URL}/treasury-yields",
    "inflation_expectations": f"{BASE_URL}/inflation-expectations",
}

_CALENDAR_DAYS_PER_OBS: dict[str, int] = {
    "inflation": 32,
    "labor_market": 32,
    "inflation_expectations": 32,
    "treasury_yields": 2,
}


class PolygonClient:
    def __init__(self, api_key: str, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.params = {"apiKey": api_key}

    @staticmethod
    def _lookback_date(dataset: str, num_observations: int) -> str:
        days_per_obs = _CALENDAR_DAYS_PER_OBS.get(dataset, 32)
        lookback_days = num_observations * days_per_obs + 60
        dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        return dt.strftime("%Y-%m-%d")

    def fetch(self, dataset: str, limit: int = 100) -> dict[str, Any] | None:
        url = ENDPOINTS.get(dataset)
        if url is None:
            logger.error("Unknown dataset requested: %s", dataset)
            return None

        params = {
            "limit": 1000,
            "sort": "date",
            "date.gte": self._lookback_date(dataset, limit),
        }

        try:
            logger.info("Fetching %s (target=%d, since=%s)", dataset, limit, params["date.gte"])
            resp = self.session.get(url, params=params, timeout=self.timeout)

            if resp.status_code == 429:
                logger.warning("Rate-limited on %s", dataset)
                raise RateLimitError(f"Polygon rate limit hit for {dataset}. Free tier allows 5 requests/minute — wait 60 seconds and retry.")

            resp.raise_for_status()
            data = resp.json()
            logger.info("Fetched %s – %d observations", dataset, len(data.get("results", [])))
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

    def fetch_all(self, limit: int = 100) -> dict[str, dict[str, Any] | None]:
        return {name: self.fetch(name, limit=limit) for name in ENDPOINTS}
