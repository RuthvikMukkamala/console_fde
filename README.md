# Daily Macro Intelligence Report

A FastAPI service that aggregates macroeconomic data from Polygon's Fed APIs (inflation, labor market, treasury yields, inflation expectations), computes trend signals and a macro regime classification, generates historical charts, and writes a rich structured report into a Notion database.

## Architecture

```
Client ──POST /generate-report──▶ FastAPI Server
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
               Polygon Fed API  Analysis Engine  Chart Generator
               (4 endpoints)   (trends/signals)  (matplotlib)
                      │              │              │
                      └──────────────┼──────────────┘
                                     │
                              ┌──────┴──────┐
                              ▼              ▼
                         Notion API     Imgur (optional)
                        (page write)   (chart hosting)
                              │
                              ▼
                       JSON Response
```

**Data flow:**
1. Fetch last N observations from four Polygon Fed endpoints
2. Extract full time series for each indicator
3. Compute trend direction (UP / DOWN / FLAT) for each dataset
4. Map trends to macro signals (e.g. rising inflation -> "Inflation pressure increasing")
5. Determine overall regime (HAWKISH / DOVISH / NEUTRAL)
6. Generate matplotlib charts for each indicator
7. Upload charts to imgur (optional, for embedding in Notion)
8. Create a rich Notion page with headings, callout blocks, chart images, data tables, and regime analysis
9. Return structured JSON with signals, regime, actions taken

## Prerequisites

- Python 3.11+
- A [Polygon.io](https://polygon.io/) API key (free tier works)
- A Notion integration token and database ID ([setup guide](https://developers.notion.com/docs/getting-started))
- (Optional) An [Imgur](https://apidocs.imgur.com/) Client ID for chart image hosting

### Notion Database Setup

Create a Notion database with this property:

| Property | Type |
|----------|------|
| **Report Name** | Title |

Then share the database with your Notion integration via the "Connections" menu.

## Local Setup

```bash
git clone https://github.com/RuthvikMukkamala/console_fde.git
cd console_fde

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in your actual keys
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POLYGON_API_KEY` | Yes | Polygon.io API key |
| `NOTION_API_KEY` | Yes | Notion integration token |
| `NOTION_DATABASE_ID` | Yes | Target Notion database ID |
| `IMGUR_CLIENT_ID` | No | Imgur Client ID for chart uploads |

### Start the Server

```bash
uvicorn main:app --reload --port 8000
```

## API Endpoints

### `GET /health`

Health check.

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "service": "macro-intel", "date": "2026-03-20"}
```

### `POST /generate-report`

Generate a macro intelligence report, write it to Notion, and return the analysis.

**Query parameters:**

| Parameter     | Type | Default | Description |
|---------------|------|---------|-------------|
| `days`        | int  | 100     | Number of observations to fetch per dataset (1-1000) |
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
  "report_date": "2026-03-20",
  "data_sources": ["inflation", "labor_market", "treasury_yields", "inflation_expectations"],
  "signals": {
    "inflation": {
      "latest": 327.46,
      "previous": 326.588,
      "delta": 0.872,
      "trend": "UP",
      "signal": "Inflation pressure increasing"
    },
    "labor_market": {
      "latest": 4.4,
      "previous": 4.3,
      "delta": 0.1,
      "trend": "UP",
      "signal": "Labor softening (unemployment rising)"
    },
    "treasury_yields": {
      "latest": 4.26,
      "previous": 4.2,
      "delta": 0.06,
      "trend": "UP",
      "signal": "Financial conditions tightening"
    },
    "inflation_expectations": {
      "latest": 2.2595,
      "previous": 2.3705,
      "delta": -0.111,
      "trend": "DOWN",
      "signal": "Inflation expectations anchored / falling"
    }
  },
  "overall_regime": "NEUTRAL",
  "report_summary": "Macro Report (2026-03-20)\n...",
  "actions_taken": ["charts_generated", "notion_page_created"],
  "notion_page_url": "https://www.notion.so/Daily-Macro-Report-2026-03-20-..."
}
```

**Example partial failure response:**

```json
{
  "status": "partial_success",
  "report_date": "2026-03-20",
  "data_sources": ["labor_market", "treasury_yields"],
  "signals": {},
  "overall_regime": "NEUTRAL",
  "report_summary": "...",
  "actions_taken": ["charts_generated"],
  "warnings": ["polygon_inflation_fetch_failed", "polygon_inflation_expectations_fetch_failed", "notion_page_creation_failed"]
}
```

## Notion Report Structure

Each generated Notion page includes:

- **Header** with date and regime classification
- **Per-indicator sections** (Inflation, Labor Market, Treasury Yields, Inflation Expectations):
  - Callout block with trend arrow, signal, and latest/previous/delta values
  - Historical chart image (if imgur is configured)
  - Table of the 5 most recent observations
- **Regime Classification** section with hawk/dove signal breakdown
- **Raw Data** section (optional, when `include_raw=true`)

## Deployment (Render)

This project includes a `render.yaml` blueprint for deploy to [Render](https://render.com).

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/) -> **New** -> **Blueprint**
3. Connect your repo and select the `render.yaml`
4. Set environment variables in the Render dashboard:
   - `POLYGON_API_KEY`
   - `NOTION_API_KEY`
   - `NOTION_DATABASE_ID`
   - `IMGUR_CLIENT_ID` (optional)
5. Deploy

**Trigger remotely:**

```bash
curl -X POST "https://<service-name>.onrender.com/generate-report?days=50"
```

## APIs Used

| API | Role | Auth |
|-----|------|------|
| [Polygon Fed API](https://polygon.io/) | Data source: inflation, labor market, treasury yields, inflation expectations | API key as query param |
| [Notion API](https://developers.notion.com/) | Output: writes structured daily report as a database page | Bearer token |
| [Imgur API](https://apidocs.imgur.com/) (optional) | Chart image hosting for Notion embeds | Client-ID header |

## Design Decisions and Assumptions

- **Trend logic:** Direction is computed from the delta between the last two observations. A delta smaller than +/-0.005 is classified as FLAT to avoid noise.
- **Primary fields per dataset:**
  - Inflation: `cpi_year_over_year` (falls back to `cpi` if unavailable)
  - Labor Market: `unemployment_rate` (rising = dovish, falling = hawkish)
  - Treasury Yields: `yield_10_year`
  - Inflation Expectations: `model_10_year`
- **Regime classification:** Simple majority vote across four indicators. Ties are NEUTRAL.
- **Partial failure resilience:** If any Polygon endpoint fails, the service continues with available data and includes warnings. If Notion or imgur fails, the analysis still returns successfully.
- **Chart generation:** Uses matplotlib with a dark theme. Charts are saved to `/tmp/macro_charts/` and optionally uploaded to imgur for Notion embedding. If imgur is not configured, the Notion report still works without images.
- **Synchronous requests:** Used `requests` for simplicity and clarity.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Polygon endpoint returns error/timeout | Skip that dataset, add warning, continue |
| Polygon returns 429 (rate limit) | Skip, add warning |
| All Polygon endpoints fail | Return HTTP 502 with error message |
| Chart generation fails | Skip charts, add warning, continue |
| Imgur upload fails or not configured | Skip image embeds in Notion, add warning |
| Notion API fails | Return analysis with `actions_taken: []` and warning |
| Missing env vars | Fail fast at startup with descriptive error |
| Invalid query params | FastAPI returns 422 with validation details |

## GitHub Repository

[https://github.com/RuthvikMukkamala/console_fde](https://github.com/RuthvikMukkamala/console_fde)
