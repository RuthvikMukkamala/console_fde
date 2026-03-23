import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from models import ReportResponse
from services.notion_client import NotionClient
from services.pipeline import ReportPipeline
from services.polygon import PolygonClient
from utils.helpers import today_str

load_dotenv()

_REQUIRED_VARS = ["POLYGON_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID", "API_SECRET_KEY"]
_missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
if _missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(_missing)}. "
        "Copy .env.example to .env and fill in your keys."
    )

API_SECRET_KEY = os.environ["API_SECRET_KEY"]


def verify_api_key(x_api_key: str = Header(..., description="API secret key")):
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

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
    _key=Depends(verify_api_key),
):
    return pipeline.run(days=days, report_name=report_name, author=author)
