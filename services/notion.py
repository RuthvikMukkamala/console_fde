import json
import os
from typing import Any

import requests

from services.analysis import TREND_ARROW, UNIT_LABELS
from utils.helpers import logger, today_str

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"

DISPLAY_NAMES: dict[str, str] = {
    "inflation": "Inflation (CPI)",
    "labor_market": "Labor Market",
    "treasury_yields": "Treasury Yields",
    "inflation_expectations": "Inflation Expectations",
}

REGIME_DESCRIPTIONS: dict[str, str] = {
    "HAWKISH": (
        "The overall macro environment shows a hawkish / tightening bias. "
        "Rising inflation, tightening financial conditions, and elevated expectations "
        "suggest the Fed may maintain or increase restrictive policy."
    ),
    "DOVISH": (
        "The overall macro environment shows a dovish / easing bias. "
        "Falling inflation, loosening financial conditions, and softening labor "
        "suggest the Fed may ease monetary policy."
    ),
    "NEUTRAL": (
        "The macro environment is sending mixed signals. "
        "Some indicators point toward tightening while others suggest easing. "
        "Policy direction is uncertain."
    ),
}


def _get_credentials() -> tuple[str, str]:
    token = os.getenv("NOTION_API_KEY", "")
    db_id = os.getenv("NOTION_DATABASE_ID", "")
    if not token:
        raise RuntimeError("NOTION_API_KEY environment variable is not set")
    if not db_id:
        raise RuntimeError("NOTION_DATABASE_ID environment variable is not set")
    return token, db_id


def _rich_text(content: str, bold: bool = False, color: str = "default") -> dict:
    rt: dict[str, Any] = {"type": "text", "text": {"content": content}}
    annotations: dict[str, Any] = {}
    if bold:
        annotations["bold"] = True
    if color != "default":
        annotations["color"] = color
    if annotations:
        rt["annotations"] = annotations
    return rt


def _heading(level: int, text: str) -> dict:
    block_type = f"heading_{level}"
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": [_rich_text(text)]},
    }


def _paragraph(*segments: dict) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": list(segments)},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _callout(text_segments: list[dict], emoji: str = "📊") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": text_segments,
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


def _image_block(url: str) -> dict:
    return {
        "object": "block",
        "type": "image",
        "image": {"type": "external", "external": {"url": url}},
    }


def _table_block(headers: list[str], rows: list[list[str]]) -> dict:
    """Build a Notion table block with header + data rows."""
    width = len(headers)
    table_rows: list[dict] = []

    header_cells = [[_rich_text(h, bold=True)] for h in headers]
    table_rows.append({
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": header_cells},
    })

    for row in rows:
        cells = [[_rich_text(cell)] for cell in row]
        table_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": cells},
        })

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "children": table_rows,
        },
    }


def _build_rich_blocks(
    signals: dict[str, dict[str, Any]],
    regime: str,
    chart_urls: dict[str, str] | None = None,
    all_time_series: dict[str, list[dict[str, Any]]] | None = None,
    raw_json: dict[str, Any] | None = None,
) -> list[dict]:
    """Build the full structured Notion page body."""
    date = today_str()
    blocks: list[dict] = []
    chart_urls = chart_urls or {}
    all_time_series = all_time_series or {}

    # --- Title + regime overview ---
    blocks.append(_heading(1, f"Daily Macro Intelligence Report"))

    regime_label = {
        "HAWKISH": "🔴 Hawkish / Tightening Bias",
        "DOVISH": "🟢 Dovish / Easing Bias",
        "NEUTRAL": "🟡 Neutral / Mixed Signals",
    }.get(regime, regime)

    blocks.append(_paragraph(
        _rich_text(f"Date: {date}  |  Overall Regime: "),
        _rich_text(regime_label, bold=True),
    ))
    blocks.append(_divider())

    # --- Per-indicator sections ---
    dataset_order = ("inflation", "labor_market", "treasury_yields", "inflation_expectations")
    trend_emojis = {"UP": "📈", "DOWN": "📉", "FLAT": "➡️"}

    for dataset in dataset_order:
        info = signals.get(dataset)
        display_name = DISPLAY_NAMES.get(dataset, dataset)
        blocks.append(_heading(2, display_name))

        if info is None:
            blocks.append(_callout([_rich_text("Data unavailable for this indicator.")], emoji="⚠️"))
            continue

        arrow = TREND_ARROW.get(info["trend"], "?")
        emoji = trend_emojis.get(info["trend"], "📊")
        prev = info.get("previous")
        latest = info.get("latest")
        delta = info.get("delta")
        signal = info.get("signal", "")
        unit = UNIT_LABELS.get(dataset, "")

        callout_parts = [
            _rich_text(f"{arrow} Trend: {info['trend']}", bold=True),
            _rich_text(f"\n{signal}"),
        ]
        if prev is not None and delta is not None:
            sign = "+" if delta > 0 else ""
            callout_parts.append(
                _rich_text(f"\nLatest: {latest} {unit}  |  Previous: {prev} {unit}  |  Change: {sign}{delta}")
            )
        else:
            callout_parts.append(_rich_text(f"\nLatest: {latest} {unit}"))

        blocks.append(_callout(callout_parts, emoji=emoji))

        # Chart image
        chart_url = chart_urls.get(dataset)
        if chart_url:
            blocks.append(_image_block(chart_url))

        # Recent observations table (last 5)
        series = all_time_series.get(dataset, [])
        if series:
            recent = series[-5:]
            blocks.append(_paragraph(_rich_text("Recent Observations", bold=True)))
            blocks.append(_table_block(
                headers=["Date", "Value"],
                rows=[[p["date"], str(p["value"])] for p in reversed(recent)],
            ))

        blocks.append(_divider())

    # --- Regime classification section ---
    blocks.append(_heading(2, "Regime Classification"))

    regime_desc = REGIME_DESCRIPTIONS.get(regime, "")
    hawk_count = sum(
        1 for n, s in signals.items()
        if (n, s["trend"]) in {
            ("inflation", "UP"), ("inflation_expectations", "UP"),
            ("treasury_yields", "UP"), ("labor_market", "DOWN"),
        }
    )
    dove_count = sum(
        1 for n, s in signals.items()
        if (n, s["trend"]) in {
            ("inflation", "DOWN"), ("inflation_expectations", "DOWN"),
            ("treasury_yields", "DOWN"), ("labor_market", "UP"),
        }
    )

    blocks.append(_paragraph(
        _rich_text(regime_desc),
    ))
    blocks.append(_paragraph(
        _rich_text(f"Hawkish signals: {hawk_count}  |  Dovish signals: {dove_count}  |  Regime: ", bold=False),
        _rich_text(regime, bold=True),
    ))

    # --- Raw data (optional) ---
    if raw_json is not None:
        blocks.append(_divider())
        blocks.append(_heading(3, "Raw Data"))
        raw_str = json.dumps(raw_json, indent=2)
        for chunk_start in range(0, len(raw_str), 1900):
            chunk = raw_str[chunk_start : chunk_start + 1900]
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                    "language": "json",
                },
            })

    return blocks


def create_notion_page(
    signals: dict[str, dict[str, Any]],
    regime: str,
    chart_urls: dict[str, str] | None = None,
    all_time_series: dict[str, list[dict[str, Any]]] | None = None,
    raw_json: dict[str, Any] | None = None,
    timeout: int = 15,
) -> dict[str, Any] | None:
    """Create a new page in the configured Notion database.

    Returns the Notion API response dict on success, or None on failure.
    """
    token, db_id = _get_credentials()
    date = today_str()
    title = f"Daily Macro Report - {date}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    body: dict[str, Any] = {
        "parent": {"database_id": db_id},
        "properties": {
            "Report Name": {
                "title": [{"text": {"content": title}}],
            },
        },
        "children": _build_rich_blocks(
            signals=signals,
            regime=regime,
            chart_urls=chart_urls,
            all_time_series=all_time_series,
            raw_json=raw_json,
        ),
    }

    try:
        logger.info("Creating Notion page: %s", title)
        resp = requests.post(NOTION_API_URL, headers=headers, json=body, timeout=timeout)

        if resp.status_code == 429:
            logger.warning("Notion rate-limited – retry later")
            return None

        resp.raise_for_status()
        result = resp.json()
        page_url = result.get("url", "")
        logger.info("Notion page created: %s", page_url)
        return result

    except requests.exceptions.Timeout:
        logger.error("Timeout creating Notion page")
    except requests.exceptions.HTTPError as exc:
        logger.error("Notion HTTP error: %s – body: %s", exc, exc.response.text if exc.response else "")
    except requests.exceptions.RequestException as exc:
        logger.error("Notion request failed: %s", exc)

    return None
