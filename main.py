import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query

from models import ReportResponse
from services.notion_client import NotionClient
from services.pipeline import ReportPipeline
from services.polygon import PolygonClient
from utils.helpers import today_str

load_dotenv()

_REQUIRED_VARS = ["POLYGON_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID"]
_missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
if _missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(_missing)}. "
        "Copy .env.example to .env and fill in your keys."
    )

polygon = PolygonClient(api_key=os.environ["POLYGON_API_KEY"])
notion = NotionClient(
    token=os.environ["NOTION_API_KEY"],
    database_id=os.environ["NOTION_DATABASE_ID"],
)
pipeline = ReportPipeline(polygon=polygon, notion=notion)

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


@app.post("/generate-report", response_model=ReportResponse)
def generate_report(
    days: int = Query(default=100, ge=1, le=1000, description="Number of observations to fetch"),
    report_name: str | None = Query(default=None, description="Custom report title (default: Daily Macro Report - <date>)"),
    author: str | None = Query(default=None, description="Author name to display on the report"),
):
    return pipeline.run(days=days, report_name=report_name, author=author)
