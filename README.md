# UK Wind Forecast Dashboard

A decision-support web application for a UK energy utility's day-ahead power trading and buying desk. Decisions for delivery day D are made on day D-1, relying on national wind generation forecasts from Elexon BMRS.

## Overview
- **Backend**: FastAPI, pandas, httpx, pytest, ruff (Python 3.11)
- **Frontend**: Vite + React + TypeScript, Recharts, TanStack Query, React Router
- **Deployment**: Vercel (FastAPI serverless function + static React build) and Docker

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- GNU Make (or execute commands directly)

### Quick Start
```bash
# Backend
make dev-backend
# Or directly:
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
make dev-frontend
# Or directly:
cd frontend && npm run dev
```

### Running Tests and Lint
```bash
make test
make lint
```
