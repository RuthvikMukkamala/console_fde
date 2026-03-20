import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from services.polygon import fetch_all, ENDPOINTS
from services.analysis import (
    compute_trend,
    extract_time_series,
    generate_signals,
    determine_regime,
    generate_report_text,
)
from services.charts import generate_all_charts, upload_all_charts
from services.notion import create_notion_page
from utils.helpers import logger, today_str

load_dotenv()

_REQUIRED_VARS = ["POLYGON_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID"]
_missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
if _missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(_missing)}. "
        "Copy .env.example to .env and fill in your keys."
    )

app = FastAPI(
    title="Daily Macro Intelligence Report",
    description=(
        "Aggregates macroeconomic data from Polygon Fed APIs, "
        "computes trend signals, and writes a daily report to Notion."
    ),
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "macro-intel", "date": today_str()}


@app.post("/generate-report")
def generate_report(
    days: int = Query(default=100, ge=1, le=1000, description="Number of observations to fetch per dataset"),
    include_raw: bool = Query(default=False, description="Include raw API data in the response"),
):
    warnings: list[str] = []
    actions_taken: list[str] = []

    # ── Step 1: Fetch data from all Polygon endpoints ──────────────────────────
    raw_data = fetch_all(limit=days)

    successful_sources: list[str] = []
    for name, data in raw_data.items():
        if data is not None:
            successful_sources.append(name)
        else:
            warnings.append(f"polygon_{name}_fetch_failed")

    if not successful_sources:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": "All Polygon API requests failed",
                "warnings": warnings,
                "actions_taken": [],
            },
        )

    # ── Step 2: Extract time series ────────────────────────────────────────────
    all_time_series: dict[str, list[dict[str, Any]]] = {}
    for name in ENDPOINTS:
        all_time_series[name] = extract_time_series(raw_data.get(name), dataset=name)

    # ── Step 3: Compute trends ─────────────────────────────────────────────────
    trends: dict[str, dict[str, Any] | None] = {}
    for name in ENDPOINTS:
        trends[name] = compute_trend(raw_data.get(name), dataset=name)

    # ── Step 4: Generate signals ───────────────────────────────────────────────
    signals = generate_signals(trends)

    if not signals:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": "Could not compute any signals from the data",
                "warnings": warnings,
                "actions_taken": [],
            },
        )

    # ── Step 5: Determine regime ───────────────────────────────────────────────
    regime = determine_regime(signals)

    # ── Step 6: Generate report text ───────────────────────────────────────────
    report_text = generate_report_text(signals, regime)

    # ── Step 7: Generate charts and upload ─────────────────────────────────────
    chart_urls: dict[str, str] = {}
    try:
        chart_paths = generate_all_charts(all_time_series, signals)
        if chart_paths:
            actions_taken.append("charts_generated")
            chart_urls = upload_all_charts(chart_paths)
            if chart_urls:
                actions_taken.append("charts_uploaded")
            else:
                warnings.append("chart_upload_failed_or_skipped")
    except Exception as exc:
        logger.error("Chart generation failed: %s", exc)
        warnings.append("chart_generation_failed")

    # ── Step 8: Write to Notion ────────────────────────────────────────────────
    notion_result = create_notion_page(
        signals=signals,
        regime=regime,
        chart_urls=chart_urls if chart_urls else None,
        all_time_series=all_time_series,
        raw_json=_build_raw_payload(signals, regime) if include_raw else None,
    )

    notion_page_url: str | None = None
    if notion_result is not None:
        actions_taken.append("notion_page_created")
        notion_page_url = notion_result.get("url")
    else:
        warnings.append("notion_page_creation_failed")

    # ── Step 9: Build response ─────────────────────────────────────────────────
    status = "success" if not warnings else "partial_success"

    response: dict[str, Any] = {
        "status": status,
        "report_date": today_str(),
        "data_sources": successful_sources,
        "signals": signals,
        "overall_regime": regime,
        "report_summary": report_text,
        "actions_taken": actions_taken,
    }

    if notion_page_url:
        response["notion_page_url"] = notion_page_url

    if warnings:
        response["warnings"] = warnings

    if include_raw:
        response["raw_data"] = {
            name: data for name, data in raw_data.items() if data is not None
        }

    return response


def _build_raw_payload(
    signals: dict[str, dict[str, Any]],
    regime: str,
) -> dict[str, Any]:
    return {"signals": signals, "regime": regime}
