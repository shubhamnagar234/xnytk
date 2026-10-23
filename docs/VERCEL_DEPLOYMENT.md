# Vercel Deployment Guide

This project is configured as a **single-project, zero-overhead deployment** on [Vercel](https://vercel.com). It combines a static Vite React Single-Page Application (SPA) served globally at the edge with a Python 3.11 Serverless Function running the FastAPI analytical backend.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │          Vercel Global Edge          │
                      └──────────────────┬───────────────────┘
                                         │
             ┌───────────────────────────┴───────────────────────────┐
             │                                                       │
             ▼                                                       ▼
   Static SPA Assets                                   Serverless Python Function
  (Vite compiled bundle)                                (`api/index.py` -> Python 3.11)
  Mapped to `frontend/dist`                             Routes `/api/*`
  Fallback to `index.html`                              Loads cached `data/*.csv.gz`
```

---

## Configuration Details (`vercel.json`)

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

### Explanation of Settings:

1. **`"framework": null`**:
   Disables automatic framework override heuristics so Vercel uses our custom build and output commands cleanly without conflicts.

2. **`"installCommand": "npm --prefix frontend install"`**:
   Installs frontend node modules from `frontend/package.json` without requiring an unnecessary root-level `package.json`.

3. **`"buildCommand": "npm --prefix frontend run build"`**:
   Executes Vite's production build pipeline (`tsc -b && vite build`), compiling React TypeScript into minified static assets in `frontend/dist`.

4. **`"outputDirectory": "frontend/dist"`**:
   Tells Vercel's edge network where the static frontend assets reside for static CDN distribution.

5. **`"functions"."api/index.py"`**:
   - **`"runtime": "python3.11"`**: Locks the serverless Python environment to Python 3.11.
   - **`"includeFiles": ["data/**", "backend/**"]`**: Crucial setting. Vercel's Python bundler tree-shakes files; explicit inclusion guarantees that `data/actuals.csv.gz`, `data/forecasts.csv.gz`, and the `backend/app` package are bundled into the serverless function filesystem.
   - **`"excludeFiles": ["backend/tests/**"]`**: Keeps test code out of the production serverless bundle to reduce artifact size and cold start latency.

6. **`"rewrites"`**:
   - First rule (`/api/(.*)` -> `/api/index.py`): Routes all API calls to the serverless Python entrypoint.
   - Second rule (`/(.*)` -> `/index.html`): Implements client-side SPA routing fallback so routes like `/accuracy` and `/methodology` can be refreshed directly in the browser without 404 errors.

---

## Dependency Management

- **Root `requirements.txt` / `api/requirements.txt`**:
  Contains only lean runtime dependencies required by the serverless function:
  ```text
  fastapi>=0.110.0,<1.0.0
  uvicorn[standard]>=0.28.0,<1.0.0
  pandas>=2.2.0
  httpx>=0.27.0
  pydantic>=2.6.0
  ```
  Dev/test tooling (`pytest`, `ruff`, etc.) is strictly omitted to keep the serverless bundle well below Vercel's limit.

---

## How to Deploy

### Option A: Via GitHub Integration (Recommended)
1. Push this repository to GitHub.
2. In the Vercel dashboard, click **"Add New..."** -> **"Project"**.
3. Import the repository.
4. Leave all root and build settings as **Default** (the `vercel.json` automatically manages everything).
5. Click **"Deploy"**.

### Option B: Via Vercel CLI
```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Deploy preview from repo root
vercel

# 3. Deploy to production
vercel --prod
```
