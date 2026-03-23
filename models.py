from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: str
    value: float


class TrendResult(BaseModel):
    latest: float
    previous: float | None = None
    delta: float | None = None
    trend: str  # "UP" | "DOWN" | "FLAT"


class SignalResult(TrendResult):
    signal: str


class ReportResponse(BaseModel):
    status: str
    report_date: str
    data_sources: list[str]
    signals: dict[str, SignalResult]
    overall_regime: str
    report_summary: str
    actions_taken: list[str]
    notion_page_url: str | None = None
    warnings: list[str] | None = None
    raw_data: dict | None = None
