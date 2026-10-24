# Vercel deployment notes for the FastAPI backend

The React frontend deploys to Vercel as a standard Vite project with
`frontend/vercel.json` (SPA rewrites; `/api` requests must resolve to the backend).

Two supported patterns:

## Pattern A — frontend + backend in ONE Vercel project (recommended for review)

1. Backend entrypoint: `api/index.py` at REPO ROOT:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from fastapi.middleware.cors import CORSMiddleware
from app.main import app  # noqa: E402

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])
```

2. `vercel.json` (repo root):

```json
{
  "builds": [
    { "src": "frontend/package.json", "use": "@vercel/static-build", "config": { "distDir": "dist" },
      "cwd": "frontend" },
    { "src": "api/index.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "api/index.py" },
    { "src": "/(.*)", "dest": "frontend/dist/$1" }
  ]
}
```

3. Snapshot data Vercel allows `<250MB serverless bundles`; the snapshot is ~4 MB. Reference
   data files from the working dir: in live serverless, the bundle CWD is not the repo —
   pass `WINDLENS_SNAPSHOT_DIR=/var/task/data/snapshots/latest` (files are zipped into the
   function bundle) or switch to `WINDLENS_DATA_MODE=snapshot` with data included in
   `api/`'s include pattern via `functions`/`includeFiles` in vercel.json:

```json
"functions": { "api/index.py": { "includeFiles": "data/snapshots/latest/**" } }
```

`backend/app/services/datasource.py` already resolves a relative snapshot dir against the
process CWD; set the absolute env var above if you prefer no CWD dependence.

4. Memory/limits: dataset load is ~30–60 MB; leave the 1 GB default memory. The single
   function handles all `/api/*`.

## Pattern B — backend elsewhere (Docker host / Fly.io / Render), frontend on Vercel

1. Deploy backend with `backend/Dockerfile` on your host of choice.
2. On Vercel set `WINDLENS_API_BASE=https://<your-backend>/api` and make
   `frontend/src/lib/api.ts` read `const BASE = import.meta.env.VITE_WINDLENS_API_BASE ?? '/api'`.
3. In production the frontend fetches cross-origin; the backend CORS env
   `WINDLENS_CORS_ORIGINS` must list the Vercel domain (it defaults to the wildcard).

## Data freshness

Vercel builds freeze the snapshot at build time. For a "current data" deployment use
Pattern B with a host that can run `scripts/build_snapshot.py --live` on a schedule, or
enable `WINDLENS_LIVE_SETTLEMENT_START/END` in the serverless function (adds Elexon
latency to the first request of each day).
