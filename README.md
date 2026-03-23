# Daily Macro Intelligence Report

A FastAPI service that pulls macroeconomic data from Polygon's Fed APIs, computes trend signals and regime classification, and writes a structured report into Notion.

## How It Works

1. Fetches data from four Polygon Fed endpoints (inflation, labor market, treasury yields, inflation expectations)
2. Computes trend direction (UP / DOWN / FLAT) and maps to macro signals
3. Determines overall regime (HAWKISH / DOVISH / NEUTRAL)
4. Writes a Notion page with callout blocks, data tables, and regime analysis
5. Returns structured JSON summarizing signals, regime, and actions taken

## Setup

```bash
git clone https://github.com/RuthvikMukkamala/console_fde.git
cd console_fde
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Fill in your keys
```

**Environment variables** (`.env`):

| Variable | Description |
|----------|-------------|
| `POLYGON_API_KEY` | Polygon.io API key |
| `NOTION_API_KEY` | Notion integration token |
| `NOTION_DATABASE_ID` | Target Notion database ID |

Your Notion database needs a **Report Name** (title) and **Author** (text) property, shared with your integration.

## Running

**Backend** (FastAPI):

```bash
uvicorn main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive Swagger docs at `http://localhost:8000/docs`.

**Frontend** (Streamlit):

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Use the sidebar to configure parameters and click "Generate Report" to trigger the backend.

## API

**`GET /`** — Service info and available endpoints

**`GET /health`** — Health check

**`POST /generate-report`** — Generate and publish a macro report

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 100 | Observations to fetch per dataset (1–1000) |
| `report_name` | string | null | Custom report title |
| `author` | string | null | Author name (sets Notion Author property) |

```bash
curl -X POST "http://localhost:8000/generate-report?days=50&author=Ruthvik"
```

Interactive docs at [localhost:8000/docs](http://localhost:8000/docs).

## Error Handling

- **Polygon rate limit (429):** Returns immediately with a clear error message and retry guidance
- **Polygon timeout/failure:** Skips that dataset, continues with partial data, includes warnings
- **All endpoints fail:** Returns error with explanation
- **Notion failure:** Returns analysis without writing a page
- **Missing env vars:** Fails fast at startup

## Design Decisions

- **Trend logic:** Delta between last two observations. Changes < ±0.005 are FLAT.
- **Regime:** Majority vote across four indicators. Ties → NEUTRAL.
- **Idempotent:** Same report name + author + date → updates existing Notion page instead of duplicating.
- **Graceful degradation:** Partial failures return what's available with warnings.

## Project Structure

```
├── main.py                  # FastAPI app + endpoints
├── app.py                   # Streamlit frontend
├── models.py                # Pydantic data models
├── constants.py             # Shared constants
├── services/
│   ├── polygon.py           # PolygonClient
│   ├── analysis.py          # Trends, signals, regime
│   ├── charts.py            # Matplotlib chart generation
│   ├── notion_blocks.py     # Notion block builders
│   ├── notion_client.py     # NotionClient
│   └── pipeline.py          # ReportPipeline orchestrator
├── utils/helpers.py         # Logging + date utilities
├── .env.example
└── requirements.txt
```

## Deployment

Deploy to any Python hosting platform (Render, Railway, Fly.io, etc):

1. Push to GitHub
2. Set env vars: `POLYGON_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## APIs Used

| API | Role | Auth |
|-----|------|------|
| [Polygon Fed API](https://polygon.io/) | Data source (4 macro endpoints) | API key query param |
| [Notion API](https://developers.notion.com/) | Report output (database pages) | Bearer token |
