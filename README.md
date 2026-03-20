# Daily Macro Intelligence Report

A lightweight FastAPI service that aggregates macroeconomic data from Polygon's Fed APIs (inflation, labor market, treasury yields, inflation expectations), computes trend signals and a macro regime classification, generates a human-readable report, and writes it into a Notion database.

## Architecture

```
Client ──POST /generate-report──▶ FastAPI Server
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
               Polygon Fed API  Analysis Engine  Notion API
               (4 endpoints)   (trends/signals)  (page write)
                      │              │              │
                      └──────────────┼──────────────┘
                                     ▼
                              JSON Response
```

**Data flow:**
1. Fetch last N observations from four Polygon Fed endpoints
2. Compute trend direction (UP / DOWN / FLAT) for each dataset
3. Map trends to macro signals (e.g. rising inflation → "Inflation pressure increasing")
4. Determine overall regime (HAWKISH / DOVISH / NEUTRAL)
5. Generate a human-readable summary
6. Create a Notion page with the report
7. Return structured JSON with signals, regime, actions taken

## Prerequisites

- Python 3.11+
- A [Polygon.io](https://polygon.io/) API key (free tier works)
- A Notion integration token and database ID ([setup guide](https://developers.notion.com/docs/getting-started))

### Notion Database Setup

Create a Notion database with these properties:
| Property | Type |
|----------|------|
| **Name** | Title |
| **Date** | Date |

Then share the database with your Notion integration.

## Local Setup

```bash
# Clone the repo
git clone <repo-url>
cd console_fde

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in your actual keys:
#   POLYGON_API_KEY=your_key
#   NOTION_API_KEY=your_key
#   NOTION_DATABASE_ID=your_db_id

# Start the server
uvicorn main:app --reload --port 8000
```

## API Endpoints

### `GET /health`

Health check.

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "service": "macro-intel", "date": "2026-03-19"}
```

### `POST /generate-report`

Generate a macro intelligence report and write it to Notion.

**Query parameters:**

| Parameter     | Type | Default | Description |
|---------------|------|---------|-------------|
| `days`        | int  | 100     | Number of observations to fetch per dataset (1–1000) |
| `include_raw` | bool | false   | Include raw API data in the response |

**Example requests:**

```bash
# Default (last 100 data points)
curl -X POST "http://localhost:8000/generate-report"

# Custom: last 50 data points, include raw data
curl -X POST "http://localhost:8000/generate-report?days=50&include_raw=true"
```

**Example success response:**

```json
{
  "status": "success",
  "report_date": "2026-03-19",
  "data_sources": ["inflation", "labor_market", "treasury_yields", "inflation_expectations"],
  "signals": {
    "inflation": {
      "latest": 3.2,
      "previous": 3.0,
      "delta": 0.2,
      "trend": "UP",
      "signal": "Inflation pressure increasing"
    },
    "labor_market": {
      "latest": 4.1,
      "previous": 4.3,
      "delta": -0.2,
      "trend": "DOWN",
      "signal": "Labor softening"
    }
  },
  "overall_regime": "HAWKISH",
  "report_summary": "Macro Report (2026-03-19)\n- Inflation: ↑ 3.0 -> 3.2 | Inflation pressure increasing\n...",
  "actions_taken": ["notion_page_created"],
  "notion_page_url": "https://www.notion.so/..."
}
```

**Example partial failure response:**

```json
{
  "status": "partial_success",
  "report_date": "2026-03-19",
  "data_sources": ["labor_market", "treasury_yields"],
  "signals": { "..." : "..." },
  "overall_regime": "NEUTRAL",
  "report_summary": "...",
  "actions_taken": [],
  "warnings": ["polygon_inflation_fetch_failed", "polygon_inflation_expectations_fetch_failed", "notion_page_creation_failed"]
}
```

## Deployment (Render)

This project includes a `render.yaml` blueprint for one-click deploy to [Render](https://render.com).

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**
3. Connect your repo and select the `render.yaml`
4. Set environment variables in the Render dashboard:
   - `POLYGON_API_KEY`
   - `NOTION_API_KEY`
   - `NOTION_DATABASE_ID`
5. Deploy — your service will be live at `https://<service-name>.onrender.com`

**Trigger remotely:**

```bash
curl -X POST "https://<service-name>.onrender.com/generate-report?days=50"
```

## APIs Used

| API | Role | Auth |
|-----|------|------|
| [Polygon Fed API](https://polygon.io/docs/stocks) | Data source — inflation, labor market, treasury yields, inflation expectations | API key as query param |
| [Notion API](https://developers.notion.com/) | Output — writes structured daily report as a database page | Bearer token |

## Design Decisions & Assumptions

- **Trend logic:** Direction is computed from the delta between the last two observations. A delta smaller than ±0.005 is classified as FLAT to avoid noise.
- **Regime classification:** Simple majority vote — if more indicators point hawkish (UP inflation, UP yields, UP expectations, tight labor) than dovish, the overall regime is HAWKISH. Ties are NEUTRAL.
- **Partial failure resilience:** If one or more Polygon endpoints fail, the service continues with available data and includes warnings in the response. If Notion fails, the analysis still returns successfully.
- **Synchronous requests:** Used `requests` (synchronous) for simplicity and clarity. For production scale, these could be parallelized with `asyncio` + `httpx`.
- **Notion page structure:** Title follows `Daily Macro Report - YYYY-MM-DD`. Body contains the human-readable summary as paragraphs, with optional raw JSON in a code block.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Polygon endpoint returns error/timeout | Skip that dataset, add warning, continue |
| Polygon returns 429 (rate limit) | Skip, add warning |
| All Polygon endpoints fail | Return HTTP 502 with error message |
| Notion API fails | Return analysis with `actions_taken: []` and warning |
| Missing env vars | Fail fast at startup with descriptive error |
| Invalid query params | FastAPI returns 422 with validation details |
