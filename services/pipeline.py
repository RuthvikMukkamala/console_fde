from typing import Any

from constants import DATASET_ORDER
from models import ReportResponse, SignalResult, TimeSeriesPoint
from services.analysis import (
    compute_trend,
    determine_regime,
    extract_time_series,
    generate_report_text,
    generate_signals,
)
from services.charts import generate_all_charts
from services.notion_blocks import build_report_blocks
from services.notion_client import NotionClient
from services.polygon import ENDPOINTS, PolygonClient, RateLimitError
from utils.helpers import logger, today_str


class ReportPipeline:
    def __init__(self, polygon: PolygonClient, notion: NotionClient):
        self.polygon = polygon
        self.notion = notion

    def run(self, days: int = 100, report_name: str | None = None, author: str | None = None) -> ReportResponse:
        warnings: list[str] = []
        actions_taken: list[str] = []

        # Fetch data
        raw_data: dict[str, Any] = {}
        rate_limited = False
        for name in ENDPOINTS:
            try:
                raw_data[name] = self.polygon.fetch(name, limit=days)
            except RateLimitError as exc:
                raw_data[name] = None
                rate_limited = True
                warnings.append(f"polygon_{name}_rate_limited")
                logger.warning(str(exc))

        if rate_limited:
            return ReportResponse(
                status="error",
                report_date=today_str(),
                data_sources=[n for n, d in raw_data.items() if d is not None],
                signals={},
                overall_regime="UNKNOWN",
                report_summary="Polygon API rate limit reached (5 requests/minute on free tier). Please wait 60 seconds and retry.",
                actions_taken=[],
                warnings=warnings,
            )

        successful_sources = [name for name, data in raw_data.items() if data is not None]
        for name, data in raw_data.items():
            if data is None:
                warnings.append(f"polygon_{name}_fetch_failed")

        if not successful_sources:
            return ReportResponse(
                status="error",
                report_date=today_str(),
                data_sources=[],
                signals={},
                overall_regime="UNKNOWN",
                report_summary="All Polygon API requests failed",
                actions_taken=[],
                warnings=warnings,
            )

        # Extract time series
        all_time_series: dict[str, list[TimeSeriesPoint]] = {
            name: extract_time_series(raw_data.get(name), dataset=name)
            for name in ENDPOINTS
        }

        # Compute trends and signals
        trends = {name: compute_trend(raw_data.get(name), dataset=name) for name in ENDPOINTS}
        signals = generate_signals(trends)

        if not signals:
            return ReportResponse(
                status="error",
                report_date=today_str(),
                data_sources=successful_sources,
                signals={},
                overall_regime="UNKNOWN",
                report_summary="Could not compute any signals from the data",
                actions_taken=[],
                warnings=warnings,
            )

        regime = determine_regime(signals)
        report_text = generate_report_text(signals, regime)

        # Generate charts
        try:
            chart_paths = generate_all_charts(all_time_series, signals)
            if chart_paths:
                actions_taken.append("charts_generated")
        except Exception as exc:
            logger.error("Chart generation failed: %s", exc)
            warnings.append("chart_generation_failed")

        # Build Notion blocks and write
        blocks = build_report_blocks(
            signals=signals,
            regime=regime,
            all_time_series=all_time_series,
            raw_json=None,
            author=author,
        )

        base_name = report_name or "Daily Macro Report"
        title_parts = [base_name]
        if author:
            title_parts.append(author)
        title_parts.append(today_str())
        title = " - ".join(title_parts)
        notion_result = self.notion.create_or_update_report(title, blocks, author=author)

        notion_page_url: str | None = None
        if notion_result is not None:
            actions_taken.append("notion_page_created")
            notion_page_url = notion_result.get("url")
        else:
            warnings.append("notion_page_creation_failed")

        # Build response
        status = "success" if not warnings else "partial_success"

        return ReportResponse(
            status=status,
            report_date=today_str(),
            data_sources=successful_sources,
            signals=signals,
            overall_regime=regime,
            report_summary=report_text,
            actions_taken=actions_taken,
            notion_page_url=notion_page_url,
            warnings=warnings or None,
            raw_data=None,
        )
