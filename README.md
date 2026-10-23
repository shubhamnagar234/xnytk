# UK Wind Generation Forecast Dashboard

[![Tests](https://img.shields.io/badge/tests-27%20passed-brightgreen.svg)](#running-tests-and-linters)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](#overview)
[![React](https://img.shields.io/badge/react-18%20%2B%20typescript-blue.svg)](#overview)
[![Docker](https://img.shields.io/badge/docker-compose%20ready-blue.svg)](#running-with-docker)
[![Vercel](https://img.shields.io/badge/deploy-vercel-black.svg)](#vercel-deployment)

> **Live Deployment:** [https://uk-wind-forecast-dashboard.vercel.app](https://uk-wind-forecast-dashboard.vercel.app) *(placeholder — deploy via your Vercel account)*

A decision-support web application for a UK energy utility's day-ahead power trading desk. Power purchase decisions for delivery day $D$ are executed on day $D-1$ before power exchange gate closure, heavily relying on national wind generation forecasts from **Elexon BMRS**.

This dashboard enables power traders and portfolio managers to:
1. **Inspect Decision-Time Forecasts**: View the latest available wind forecast at any chosen $D-1$ decision cutoff (default `09:00` London local time), inspect forecast errors against actual outturn generation, and compare revisions against earlier forecast vintages.
2. **Quantitatively Evaluate Forecast Accuracy**: Factor systematic model uncertainty into physical auction bids using lead-time horizon decay (0–48h), diurnal hour-of-day bias curves, error distributions, and generation terciles.
3. **Understand Market Rationale**: Connect statistical metrics directly to power trading decisions, imbalance risk, and market gate closures.

---

## Table of Contents
- [Product Summary](#product-summary)
- [Repository Map](#repository-map)
- [Running with Docker](#running-with-docker)
- [Running without Docker (Local Development)](#running-without-docker-local-development)
- [Regenerating Data (Data Ingestion)](#regenerating-data-data-ingestion)
- [Running Tests and Linters](#running-tests-and-linters)
- [Vercel Deployment](#vercel-deployment)
- [Key Design Decisions](#key-design-decisions)
- [Limitations and Next Steps](#limitations-and-next-steps)
- [AI Tools Used](#ai-tools-used)

---

## Product Summary

In the UK electricity market (BETTA), wind generators and day-ahead buyers submit physical notifications and trade on power exchanges (EPEX SPOT and Nord Pool / N2EX). The day-ahead auction closes at **11:00–12:00 London local time**. A utility's trading desk runs position and commitment models between **09:00 and 10:30 on day $D-1$**.

This dashboard evaluates decision forecasts made throughout **January 2026** (delivery window: `2026-01-02 00:00:00Z` to `2026-02-01 23:30:00Z`, 31 delivery days = 1,488 half-hours) across three dedicated views:

1. **Decision View (`/`)**:
   - Target delivery date selector and interactive $D-1$ cutoff selector (`07:00` to `12:00`).
   - Key day-ahead KPIs: Total Wind Energy (MWh), Peak/Min Wind (MW), Day-Level MAE, and Bias.
   - Interactive Recharts visualization with actual outturn (`#0284c7`), decision forecast (`#d97706`), toggleable historical forecast vintages (`#94a3b8`), and error fill bands.
   - Custom tooltips displaying London local time, Settlement Period (SP 1–48), forecast horizon lead time, and forecast error.
   - Complete half-hourly position table with over-forecast / under-forecast badges and CSV export.

2. **Accuracy View (`/accuracy`)**:
   - Multi-dimensional quantitative evaluation over configurable date ranges.
   - Macro KPIs: Sample Size, MAE (MW), RMSE (MW), Mean Bias (MW), P50/P90/P95 Absolute Error, and MAE % of Mean Actual.
   - Lead-Time Horizon Decay Curve: Evaluates forecast degradation across 5 trading horizons ($0\text{--}6\text{h}$, $6\text{--}12\text{h}$, $12\text{--}24\text{h}$, $24\text{--}36\text{h}$, $36\text{--}48\text{h}$) across all vintages.
   - Diurnal 24-Hour Error Pattern: Displays hour-by-hour MAE and signed bias to identify recurring daily thermal or wind ramp cycle errors.
   - Error Distribution Histogram: Displays skewness and fat tails (P90/P95 risk bands) with clear over-forecast vs under-forecast risk labeling.
   - Generation Level Terciles: Evaluates accuracy across Low, Medium, and High wind generation regimes.

3. **Methodology View (`/methodology`)**:
   - Comprehensive market documentation explaining day-ahead gate closure, decision cutoff rationale, error conventions, Elexon BMRS API feeds, and trading desk recommendations.

---

## Repository Map

```text
assessment/
├── .dockerignore                  # Docker build context exclusions for root
├── .env.example                   # Environment variable template
├── .gitignore                     # Git ignore rules for Python, Node, OS files
├── Makefile                       # Developer automation shortcuts (test, lint, run, docker)
├── README.md                      # This comprehensive handbook and runbook
├── docker-compose.yml             # Orchestration for local containerized deployment
├── requirements.txt               # Root runtime-only dependencies for Vercel
├── vercel.json                    # Single-project Vercel serverless configuration
│
├── api/                           # Vercel Serverless Function entrypoint
│   ├── index.py                   # Serverless ASGI adapter importing FastAPI app
│   └── requirements.txt           # Python runtime dependencies for Vercel
│
├── backend/                       # FastAPI analytical backend service
│   ├── .dockerignore              # Backend Docker build context exclusions
│   ├── Dockerfile                 # Python 3.11-slim production container
│   ├── pytest.ini                 # Pytest configuration and test path definitions
│   ├── requirements.txt           # Full backend dependencies (runtime + pytest + ruff)
│   ├── app/
│   │   ├── main.py                # FastAPI app initialization, CORS, lifespan data loader
│   │   ├── config.py              # Configuration constants, delivery window, paths, timezone
│   │   ├── data_loader.py         # In-memory snapshot caching with lazy-loading fallback
│   │   ├── models.py              # Pydantic schemas for all API responses
│   │   ├── analytics/             # Pure pandas analytical core (zero web dependencies)
│   │   │   ├── __init__.py        # Exported analytics functions
│   │   │   ├── decision.py        # Decision forecast selection, vintages, cutoff logic
│   │   │   └── metrics.py         # MAE, RMSE, bias, percentiles, horizon/diurnal/tercile metrics
│   │   └── api/                   # API endpoint routers
│   │       ├── health.py          # GET /api/health
│   │       ├── meta.py            # GET /api/meta (available delivery dates, data bounds)
│   │       ├── forecast.py        # GET /api/forecast/decision, GET /api/forecast/vintages
│   │       └── accuracy.py        # GET /api/accuracy/summary, by-horizon, breakdowns
│   ├── ingest/
│   │   └── fetch_elexon.py        # CLI ingestion script with chunking, retry, and schema validation
│   └── tests/                     # Test suite (27 unit and integration tests)
│       ├── test_analytics.py      # Tests for pure analytics, cutoff boundaries, edge cases
│       ├── test_api.py            # FastAPI TestClient endpoint integration tests
│       ├── test_health.py         # Health check tests
│       ├── test_ingest.py         # Offline parser and schema tests
│       └── fixtures/              # Offline JSON fixtures from real Elexon responses
│
├── data/                          # Committed snapshot data (gzipped CSV, < 0.1 MB total)
│   ├── actuals.csv.gz             # FUELHH stream (1,488 half-hours, 7.8 KB)
│   └── forecasts.csv.gz           # WINDFOR stream (11,777 forecast rows, 83.0 KB)
│
├── docs/                          # Documentation and assets
│   ├── AI_USAGE.md                # Phase-by-phase AI pairing disclosure and verification log
│   ├── VERCEL_DEPLOYMENT.md       # Detailed single-project Vercel configuration guide
│   └── screenshots/               # Verification screenshots of the dashboard
│       ├── decision_view.png      # Screenshot of the Decision View
│       ├── accuracy_view.png      # Screenshot of the Accuracy View
│       └── methodology_view.png   # Screenshot of the Methodology View
│
└── frontend/                      # Vite + React + TypeScript single-page application
    ├── .dockerignore              # Frontend Docker build context exclusions
    ├── Dockerfile                 # Multi-stage Dockerfile (Node 20 build -> Nginx alpine)
    ├── nginx.conf                 # Nginx configuration: static SPA serving + /api proxy
    ├── package.json               # Frontend dependencies and build scripts
    ├── tsconfig.json              # TypeScript configuration
    ├── vite.config.ts             # Vite dev server configuration and /api proxy
    └── src/
        ├── App.tsx                # Root layout, React Router routes, TanStack Query provider
        ├── main.tsx               # DOM mounting entrypoint
        ├── index.css              # Color tokens, typography, dark institutional theme
        ├── api/
        │   └── client.ts          # Typed fetch API client
        ├── types/
        │   └── api.ts             # TypeScript interfaces mirroring backend Pydantic models
        ├── components/
        │   ├── Navbar.tsx         # Navigation header with date badge and live health ping
        │   ├── KpiCard.tsx        # Financial metric KPI card with sub-labels
        │   └── InsightBanner.tsx  # Dynamic plain-English insight callouts above charts
        └── pages/
            ├── DecisionView.tsx   # Day-ahead decision view with actuals, forecast, vintages
            ├── AccuracyView.tsx   # Multi-dimensional forecast error and horizon evaluation
            └── MethodologyView.tsx# Market rules, auction timeline, and methodology guide
```

---

## Running with Docker

The fastest way to run the entire stack locally with zero Python or Node dependencies installed on your host machine.

### 1. Start Containers
```bash
# Start backend and frontend in detached mode (builds images on first run)
docker compose up -d --build

# Or using the Makefile:
make docker-up
```

### 2. Access the Application
- **Frontend Web Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Backend API Direct**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

*The frontend Nginx container automatically reverse-proxies `/api/*` requests to the internal backend container (`http://backend:8000/api/*`), mirroring production routing.*

### 3. Stop Containers
```bash
docker compose down

# Or using the Makefile:
make docker-down
```

---

## Running without Docker (Local Development)

### Prerequisites
- **Python**: 3.11+ (Python 3.11, 3.12, 3.13, or 3.14)
- **Node.js**: 20+ and `npm`
- **Make** *(optional)*: GNU Make for running convenience targets

### 1. Backend Setup
```bash
# 1. Install backend dependencies
pip install -r backend/requirements.txt
# (or make install-backend)

# 2. Run the FastAPI development server with hot reload
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
# (or make dev-backend)
```
The API is now live at [http://localhost:8000](http://localhost:8000) with docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend Setup
In a second terminal window:
```bash
# 1. Navigate to frontend directory and install dependencies
cd frontend
npm install
# (or make install-frontend)

# 2. Run Vite development server
npm run dev
# (or make dev-frontend)
```
The frontend is now live at [http://localhost:5173](http://localhost:5173).

*The Vite development server is preconfigured in `vite.config.ts` to automatically proxy all `/api/*` calls to `http://localhost:8000`, so no manual CORS or environment variable adjustments are needed.*

---

## Regenerating Data (Data Ingestion)

The project ships with committed snapshots in `data/` (`actuals.csv.gz` and `forecasts.csv.gz`), so **you do not need to fetch data from Elexon to run the application or tests**.

If you wish to re-query the live Elexon BMRS API and regenerate the snapshots:

```bash
# Run the ingestion script
python backend/ingest/fetch_elexon.py

# Or using the Makefile:
make ingest
```

### Ingestion Script Design:
- **Zero API Keys Required**: Elexon BMRS API v1 `/stream` endpoints are public and require no authentication.
- **Streams Ingested**:
  - `FUELHH` (`/datasets/FUELHH/stream?fuelType=WIND`): Ingests outturn generation at 30-minute resolution. Yields exactly 1,488 half-hours for Jan 2 to Feb 1, 2026 (0 missing periods).
  - `WINDFOR` (`/datasets/WINDFOR/stream`): Ingests all historical forecast revisions.
- **5-Day Chunking**: Chunks queries into 5-day intervals to adhere to Elexon streaming limits without connection timeouts.
- **Exponential Backoff**: Automatic retry with exponential backoff on network hiccups or rate limits.
- **Horizon Computation**: Computes lead-time horizon in hours: $\text{horizon} = (\text{startTime} - \text{publishTime})$. Filters to valid day-ahead horizons between $0$ and $48$ hours.
- **Lightweight Storage**: Saves datasets as compressed `gzip` CSVs (`data/actuals.csv.gz`: 7.8 KB; `data/forecasts.csv.gz`: 83.0 KB). Total size is **0.09 MB**, well below the 20 MB repository budget.

---

## Running Tests and Linters

All 27 backend tests run completely **offline** in ~1.5–3 seconds using local fixtures and pure analytical dataframes, with zero external network dependencies.

### 1. Run Backend Unit and Integration Tests
```bash
python -m pytest backend/tests

# Or using the Makefile:
make test
```

Test coverage includes:
- `test_analytics.py`: Pure pandas decision forecast selection, cutoff time boundary logic across London/UTC day transitions, pre-cutoff vs post-cutoff revision filtering, preservation of unforecasted half-hours as `NaN`, hand-calculated metric verification against a 4-row benchmark, and spot checks against real Elexon data.
- `test_api.py`: FastAPI `TestClient` endpoint tests for `/api/health`, `/api/meta`, `/api/forecast/decision`, `/api/forecast/vintages`, `/api/accuracy/summary`, `/api/accuracy/by-horizon`, and `/api/accuracy/breakdowns`. Validates Pydantic serialization, 400 Bad Request on invalid date/time formats, and 404 Not Found on out-of-range dates.
- `test_health.py`: Healthcheck status and timestamp validation.
- `test_ingest.py`: Parser validation against recorded Elexon JSON stream fixtures, schema validation, horizon filtering, and missing period counting.

### 2. Run Linters
```bash
# Backend linting (Ruff)
python -m ruff check backend

# Frontend TypeScript typechecking
cd frontend && npm run lint

# Or run both via Makefile:
make lint
```

### 3. Verify Frontend Production Build
```bash
cd frontend && npm run build
```

---

## Vercel Deployment

The application is architected for a **single-project serverless deployment** on Vercel:

```text
Incoming Request
      │
      ├── /api/*  ──────►  api/index.py (FastAPI on Python 3.11 Serverless Function)
      │                     └── Loads data/actuals.csv.gz & data/forecasts.csv.gz
      │
      └── /*      ──────►  frontend/dist (Vite static React bundle served at Edge CDN)
                            └── SPA fallback to /index.html
```

### Deployment Configuration (`vercel.json`)
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": null,
  "installCommand": "npm --prefix frontend install",
  "buildCommand": "npm --prefix frontend run build",
  "outputDirectory": "frontend/dist",
  "functions": {
    "api/index.py": {
      "runtime": "python3.11",
      "includeFiles": [
        "data/**",
        "backend/**"
      ],
      "excludeFiles": [
        "backend/tests/**"
      ]
    }
  },
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "/api/index.py"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

### How to Deploy to Vercel
1. Push this repository to GitHub.
2. In the [Vercel Dashboard](https://vercel.com/dashboard), click **"Add New..."** -> **"Project"**.
3. Import the repository.
4. Leave all build settings as **Default** (`vercel.json` automatically configures commands, output directory, and serverless runtime).
5. Click **"Deploy"**.

*For full details on serverless architecture, bundling, and cold-start optimizations, refer to [docs/VERCEL_DEPLOYMENT.md](docs/VERCEL_DEPLOYMENT.md).*

---

## Key Design Decisions

### 1. Decision Cutoff Rationale (D-1 at 09:00 London Time)
- **Market Context**: In the UK power market, day-ahead power auctions at EPEX SPOT (Day-Ahead Auction) and Nord Pool / N2EX close between **11:00 and 12:00 London local time**.
- **Desk Workflow**: Power trading desks run unit commitment, dispatch optimization, and demand-balance models between **09:00 and 10:30** to formulate auction order curves.
- **Implementation**: The dashboard selects the latest forecast published at or before the cutoff time: $\text{publishTime} \le \text{Cutoff}_{(D-1, \text{London converted to UTC})}$. The cutoff is configurable from 07:00 to 12:00, allowing traders to evaluate the value of delaying bids to receive later forecast revisions.

### 2. Error Definition and Trading Implications
$$\text{Error} = \text{Forecast} - \text{Actual}$$
- **Positive Error ($\text{Error} > 0$) — Over-Forecast Risk**:
  - The model projected higher wind generation than materialized.
  - *Trading consequence*: The utility over-bought wind day-ahead or under-hedged backup generation. The utility is left "short" in the balancing mechanism and must buy replacement energy at the **System Buy Price (SBP)**, typically the most expensive power of the day.
- **Negative Error ($\text{Error} < 0$) — Under-Forecast Risk**:
  - The model projected lower wind generation than materialized.
  - *Trading consequence*: The utility bought unnecessary fossil generation or sold wind too cheaply. The utility is "spilling" wind and receives the **System Sell Price (SSP)**, incurring volume cannibalization losses.

### 3. Horizon Definition
$$\text{Horizon (hours)} = \frac{\text{Target startTime} - \text{publishTime}}{3600}$$
Only forecasts with $0 \le \text{Horizon} \le 48\text{ h}$ are retained. For day-ahead decisions made at 09:00 $D-1$ for delivery throughout day $D$, the decision lead-time spans **15.0 hours** (for 00:00 delivery) up to **38.5 hours** (for 23:30 delivery).

### 4. Gzipped CSV Storage (`.csv.gz`) vs Parquet
- The repository stores snapshots as compressed CSV (`data/actuals.csv.gz` [7.8 KB] and `data/forecasts.csv.gz` [83.0 KB]).
- **Why**: Standard `pandas.read_csv(..., compression="gzip")` relies purely on Python's built-in `gzip` module with zero external C-dependencies or `pyarrow` requirements. This guarantees instant cold-start times on Vercel Python serverless functions, avoids OS-specific wheel binary issues, and keeps total repository data storage under 0.1 MB.

### 5. Strict Preservation of Unforecasted Half-Hours (`NaN`)
- Elexon BMRS `WINDFOR` publishes national forecasts at **hourly** start times (`:00`), whereas `FUELHH` actuals record generation for every **half-hour** (`:00` and `:30`).
- Across the 31 delivery days (1,488 half-hours), exactly **744 half-hours** have matching forecast start times, and **744 intermediate half-hours** have no published forecast.
- **Strict Rule**: Intermediate half-hours remain `NaN` and are never interpolated, forward-filled, or zero-filled. Metrics and charts accurately ignore `NaN` values, and tooltips explicitly display `Unforecasted` to reflect reality rather than synthetic assumptions.

### 6. Metric Selection: Why MAE & RMSE, Never MAPE
- Metrics reported: **MAE (MW)**, **RMSE (MW)**, **Mean Bias (MW)**, **P50 / P90 / P95 Absolute Error (MW)**, and **MAE % of Mean Actual**.
- **Strict Exclusion**: **MAPE (Mean Absolute Percentage Error) is strictly prohibited**. Wind generation in the UK frequently drops to near-zero (e.g. 100–300 MW out of 25,000 MW capacity during summer doldrums or winter high-pressure blocks). In near-zero periods, small absolute errors (e.g. 200 MW) produce runaway percentage errors of 400%–1,000%, completely distorting statistical summaries and misleading trading decisions. Instead, we report **MAE as a percentage of mean actual generation** ($\frac{\text{MAE}}{\overline{\text{Actual}}} \times 100$).

### 7. Accessible, Color-Blind Safe Palette
- Institutional energy trading aesthetic using dark slate backgrounds (`#090d16` and `#111827`).
- Color-blind safe palette:
  - **Actual Outturn Generation**: Sky Blue (`#0284c7`)
  - **Decision Forecast**: Vivid Amber (`#d97706`)
  - **Historical Forecast Vintages**: Muted Slate (`#94a3b8`)
  - **Over-Forecast Risk**: Orange / Amber (`#ea580c`)
  - **Under-Forecast Risk**: Cyan / Blue (`#0284c7`)
- All chart axes include physical units (**MW** for power rate, **MWh** for cumulative energy), and all chart tooltips display both **UTC** and **Europe/London** clock times.

---

## Limitations and Next Steps

### Current Limitations
1. **National-Level Aggregation Only**: Data reflects total GB transmission-system wind generation. It does not disaggregate between onshore and offshore wind, nor does it provide Distribution Network Operator (DNO) or Grid Supply Point (GSP) regional locational forecasts.
2. **Hourly Forecast Granularity**: Because Elexon BMRS `WINDFOR` publishes forecasts at 60-minute resolution, 30-minute settlement periods (e.g., 14:30) lack published forecasts and are shown as unforecasted.
3. **Static January 2026 Time Window**: The decision evaluation window is bounded between `2026-01-02` and `2026-02-01`.

### Future Roadmap / Next Steps
1. **Regional & Locational Zonal Breakdown**: Ingest Scottish vs English transmission boundary data (e.g. B6 boundary) to identify wind curtailment and transmission constraint risk.
2. **Probabilistic Quantile Forecasts**: Ingest or generate P10, P50, and P90 confidence intervals around decision forecasts to enable explicit Value-at-Risk (VaR) calculations.
3. **Financial Imbalance Cashout Simulation**: Integrate real-time Elexon System Buy Price (SBP) and System Sell Price (SSP) data to calculate the exact £ monetary profit & loss impact of forecast errors for an unhedged power portfolio.
4. **Automated Live Ingestion Webhook**: Implement a scheduled GitHub Action or cron worker to stream incoming Elexon BMRS forecasts in real time and automatically refresh the dashboard daily.

---

## AI Tools Used

This project was built with the assistance of **Google Antigravity** (powered by Gemini 3.8 Flash).

### Scope of AI Assistance:
- **Scaffolding and Boilerplate**: Rapidly initialized the monorepo structure, FastAPI endpoint boilerplate, Pydantic schemas, and Vite React components.
- **Visualization Implementation**: Accelerated the implementation of responsive Recharts visualizations, dark-theme styling, and SVG layout formatting.
- **Documentation Structuring**: Drafted initial outlines for README and deployment documentation.

### Human Engineering & Verification:
- **Elexon API Domain Logic**: Inspected raw Elexon OpenAPI specifications to determine correct streaming endpoint parameter syntax, ISO-8601 formatting, and the distinction between `FUELHH` and `WINDFOR` timestamps.
- **Mathematical Integrity**: Hand-calculated verification benchmarks for MAE, RMSE, Bias, and percentiles to ensure pandas analytics functions are mathematically sound.
- **Boundary Conditions**: Tested UTC vs Europe/London timezone conversion and day-ahead cutoff date calculation to guarantee no lookahead bias.
- **Zero Hallucination Guarantee**: All API endpoints and test cases were verified offline against committed snapshot data.

A complete phase-by-phase log of all AI prompts, generated code, and human verifications is maintained in [docs/AI_USAGE.md](docs/AI_USAGE.md).

---

## License
MIT License. Created for the UK Energy Utility Take-Home Assessment (October 2026).
