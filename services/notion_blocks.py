import json
from typing import Any

from constants import (
    DATASET_ORDER,
    DISPLAY_NAMES,
    DOVISH_COMBOS,
    HAWKISH_COMBOS,
    REGIME_DESCRIPTIONS,
    TREND_ARROW,
    TREND_EMOJI,
    UNIT_LABELS,
)
from models import SignalResult, TimeSeriesPoint
from utils.helpers import today_str


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
    return {"object": "block", "type": block_type, block_type: {"rich_text": [_rich_text(text)]}}


def _paragraph(*segments: dict) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": list(segments)}}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _callout(text_segments: list[dict], emoji: str = "\U0001f4ca") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": text_segments,
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


def _table_block(headers: list[str], rows: list[list[str]]) -> dict:
    width = len(headers)
    table_rows: list[dict] = []

    header_cells = [[_rich_text(h, bold=True)] for h in headers]
    table_rows.append({"object": "block", "type": "table_row", "table_row": {"cells": header_cells}})

    for row in rows:
        cells = [[_rich_text(cell)] for cell in row]
        table_rows.append({"object": "block", "type": "table_row", "table_row": {"cells": cells}})

    return {
        "object": "block",
        "type": "table",
        "table": {"table_width": width, "has_column_header": True, "children": table_rows},
    }


def build_report_blocks(
    signals: dict[str, SignalResult],
    regime: str,
    all_time_series: dict[str, list[TimeSeriesPoint]] | None = None,
    raw_json: dict[str, Any] | None = None,
    author: str | None = None,
) -> list[dict]:
    date = today_str()
    blocks: list[dict] = []
    all_time_series = all_time_series or {}

    blocks.append(_heading(1, "Daily Macro Intelligence Report"))

    regime_label = {
        "HAWKISH": "\U0001f534 Hawkish / Tightening Bias",
        "DOVISH": "\U0001f7e2 Dovish / Easing Bias",
        "NEUTRAL": "\U0001f7e1 Neutral / Mixed Signals",
    }.get(regime, regime)

    header = f"Date: {date}"
    if author:
        header += f"  |  Author: {author}"
    header += "  |  Overall Regime: "

    blocks.append(_paragraph(
        _rich_text(header),
        _rich_text(regime_label, bold=True),
    ))
    blocks.append(_divider())

    for dataset in DATASET_ORDER:
        sig = signals.get(dataset)
        display_name = DISPLAY_NAMES.get(dataset, dataset)
        blocks.append(_heading(2, display_name))

        if sig is None:
            blocks.append(_callout([_rich_text("Data unavailable for this indicator.")], emoji="\u26a0\ufe0f"))
            continue

        arrow = TREND_ARROW.get(sig.trend, "?")
        emoji = TREND_EMOJI.get(sig.trend, "\U0001f4ca")
        unit = UNIT_LABELS.get(dataset, "")

        callout_parts = [
            _rich_text(f"{arrow} Trend: {sig.trend}", bold=True),
            _rich_text(f"\n{sig.signal}"),
        ]
        if sig.previous is not None and sig.delta is not None:
            sign = "+" if sig.delta > 0 else ""
            callout_parts.append(
                _rich_text(f"\nLatest: {sig.latest} {unit}  |  Previous: {sig.previous} {unit}  |  Change: {sign}{sig.delta}")
            )
        else:
            callout_parts.append(_rich_text(f"\nLatest: {sig.latest} {unit}"))

        blocks.append(_callout(callout_parts, emoji=emoji))

        series = all_time_series.get(dataset, [])
        if series:
            recent = series[-5:]
            blocks.append(_paragraph(_rich_text("Recent Observations", bold=True)))
            blocks.append(_table_block(
                headers=["Date", "Value"],
                rows=[[p.date, str(p.value)] for p in reversed(recent)],
            ))

        blocks.append(_divider())

    blocks.append(_heading(2, "Regime Classification"))

    regime_desc = REGIME_DESCRIPTIONS.get(regime, "")
    hawk_count = sum(1 for n, s in signals.items() if (n, s.trend) in HAWKISH_COMBOS)
    dove_count = sum(1 for n, s in signals.items() if (n, s.trend) in DOVISH_COMBOS)

    blocks.append(_paragraph(_rich_text(regime_desc)))
    blocks.append(_paragraph(
        _rich_text(f"Hawkish signals: {hawk_count}  |  Dovish signals: {dove_count}  |  Regime: "),
        _rich_text(regime, bold=True),
    ))

    if raw_json is not None:
        blocks.append(_divider())
        blocks.append(_heading(3, "Raw Data"))
        raw_str = json.dumps(raw_json, indent=2)
        for chunk_start in range(0, len(raw_str), 1900):
            chunk = raw_str[chunk_start: chunk_start + 1900]
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                    "language": "json",
                },
            })

    return blocks
