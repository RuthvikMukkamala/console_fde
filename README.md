# Daily Macro Intelligence Report

A FastAPI service that aggregates macroeconomic data from Polygon's Fed APIs (inflation, labor market, treasury yields, inflation expectations), computes trend signals and a macro regime classification, generates historical charts, and writes a rich structured report into a Notion database.

---

## Requirements Checklist

| Requirement | How it's met |
|---|---|
| **Authenticates with both APIs correctly** | Polygon: API key passed as query param. Notion: Bearer token in `Authorization` header with `Notion-Version` header. Both validated at startup. |
| **Reads from one API, writes to another** | Reads macro data from four Polygon Fed endpoints; writes a structured report page to a Notion database. |
| **Handles at least one error case gracefully** | Polygon timeout/rate-limit → skips dataset, continues with partial data. Notion failure → returns analysis without page. Missing env vars → fails fast at startup with a descriptive error. See [Error Handling](#error-handling). |
| **README explains what it does, how to run it, and assumptions** | This document. See [Local Setup](#local-setup), [API Endpoints](#api-endpoints), and [Design Decisions](#design-decisions-and-assumptions). |
| **Exposes an HTTP endpoint we can hit live** | `POST /generate-report` accepts `days` and `include_raw` query params to control behavior. |
| **Endpoint accepts params that modify behavior** | `days` controls observation window (1–1000). `include_raw` toggles raw data in the response. |
| **Leverages connected systems to take action** | Pulls data from Polygon → computes analysis → writes a rich report page to Notion (creates or updates). |
| **Returns data about what was pulled and what actions were taken** | JSON response includes `data_sources`, `signals`, `overall_regime`, `report_summary`, `actions_taken`, and `warnings`. |
| **Deployed and triggerable over the web** | Deployed on Vercel. See [Deployment](#deployment-vercel). |

---

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
                                     ▼
                                Notion API
                               (page write)
                                     │
                                     ▼
                              JSON Response
```

**Data flow:**
1. Fetch last N observations from four Polygon Fed endpoints
2. Extract full time series for each indicator
3. Compute trend direction (UP / DOWN / FLAT) for each dataset
4. Map trends to macro signals (e.g. rising inflation → "Inflation pressure increasing")
5. Determine overall regime (HAWKISH / DOVISH / NEUTRAL)
6. Generate matplotlib charts for each indicator
7. Write a rich Notion page with headings, callout blocks, data tables, and regime analysis
8. Return structured JSON with signals, regime, and actions taken

---

## Prerequisites

- Python 3.11+
- A [Polygon.io](https://polygon.io/) API key (free tier works)
- A Notion integration token and database ID ([setup guide](https://developers.notion.com/docs/getting-started))

### Notion Database Setup

Create a Notion database with this property:

| Property | Type |
|----------|------|
| **Report Name** | Title |

Then share the database with your Notion integration via the "Connections" menu.

---

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

### Start the Server

```bash
uvicorn main:app --reload --port 8000
```

---

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
  "report_summary": "Macro Report (2026-03-20)\n- Inflation (CPI): ↑ 326.588 -> 327.46 | Inflation pressure increasing\n...",
  "actions_taken": ["charts_generated", "notion_page_created"],
  "notion_page_url": "https://www.notion.so/..."
}
```

**Example partial failure response:**

```json
{
  "status": "partial_success",
  "report_date": "2026-03-20",
  "data_sources": ["labor_market", "treasury_yields"],
  "warnings": ["polygon_inflation_fetch_failed", "notion_page_creation_failed"],
  "actions_taken": ["charts_generated"],
  "overall_regime": "NEUTRAL",
  "report_summary": "...",
  "signals": {}
}
```

---

## Notion Report Structure

Each generated Notion page includes:

- **Header** with date and regime classification
- **Per-indicator sections** (Inflation, Labor Market, Treasury Yields, Inflation Expectations):
  - Callout block with trend arrow, signal, and latest/previous/delta values
  - Table of the 5 most recent observations
- **Regime Classification** section with hawk/dove signal breakdown
- **Raw Data** section (optional, when `include_raw=true`)

If a report for today already exists in the database, it is updated in-place rather than duplicated.

---

## Deployment (Vercel)

This project includes a `vercel.json` config for deploying to [Vercel](https://vercel.com) as a Python serverless function.

1. Install the Vercel CLI: `npm i -g vercel`
2. Push this repo to GitHub
3. Run `vercel` from the project root (or import the repo at [vercel.com/new](https://vercel.com/new))
4. Set environment variables in the Vercel dashboard (Settings → Environment Variables):
   - `POLYGON_API_KEY`
   - `NOTION_API_KEY`
   - `NOTION_DATABASE_ID`
5. Deploy with `vercel --prod`

**Trigger remotely:**

```bash
curl -X POST "https://<project-name>.vercel.app/generate-report?days=50"
```

---

## APIs Used

| API | Role | Auth |
|-----|------|------|
| [Polygon Fed API](https://polygon.io/) | Data source: inflation, labor market, treasury yields, inflation expectations | API key as query param |
| [Notion API](https://developers.notion.com/) | Output: writes structured daily report as a database page | Bearer token |

---

## Design Decisions and Assumptions

- **Trend logic:** Direction is computed from the delta between the last two observations. A delta smaller than ±0.005 is classified as FLAT to avoid noise.
- **Primary fields per dataset:**
  - Inflation: `cpi_year_over_year` (falls back to `cpi` if unavailable)
  - Labor Market: `unemployment_rate` (rising = dovish, falling = hawkish)
  - Treasury Yields: `yield_10_year`
  - Inflation Expectations: `model_10_year`
- **Regime classification:** Simple majority vote across four indicators. Ties default to NEUTRAL.
- **Partial failure resilience:** If any Polygon endpoint fails, the service continues with available data and includes warnings. If Notion fails, the analysis still returns successfully.
- **Idempotent daily reports:** If a report for today already exists in Notion, it is cleared and rewritten rather than duplicated.
- **Chart generation:** Uses matplotlib with a dark theme. Charts are saved to a temp directory for local reference.
- **Synchronous requests:** Uses `requests` for simplicity and clarity. Suitable for the single-request-at-a-time nature of this service.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Polygon endpoint returns error/timeout | Skip that dataset, add warning, continue |
| Polygon returns 429 (rate limit) | Skip that dataset, add warning |
| All Polygon endpoints fail | Return error response with explanation |
| Chart generation fails | Skip charts, add warning, continue |
| Notion API fails | Return analysis with `actions_taken: []` and warning |
| Missing env vars | Fail fast at startup with descriptive error |
| Invalid query params | FastAPI returns 422 with validation details |

---

## Project Structure

```
console_fde/
├── main.py                      # FastAPI app, endpoint definitions
├── models.py                    # Pydantic data models
├── constants.py                 # Shared constants (single source of truth)
├── services/
│   ├── polygon.py               # PolygonClient – fetches macro data
│   ├── analysis.py              # Trend computation, signal generation, regime classification
│   ├── charts.py                # Chart generation (matplotlib)
│   ├── notion_blocks.py         # Notion block builders (pure functions, no HTTP)
│   ├── notion_client.py         # NotionClient – page create/update via API
│   └── pipeline.py              # ReportPipeline – orchestrates the full workflow
├── utils/
│   └── helpers.py               # Logging setup and date utilities
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
├── vercel.json                  # Vercel deployment config
└── README.md
```

---

## GitHub Repository

[https://github.com/RuthvikMukkamala/console_fde](https://github.com/RuthvikMukkamala/console_fde)
