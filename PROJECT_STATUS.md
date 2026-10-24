# PROJECT_STATUS.md — WindLens (Gridbricks challenge)

Updated: backend + frontend + docs + Docker configs DONE; 46 tests green; live smoke pass
(real snapshot, all endpoints verified); remaining = deployment execution (needs accounts)
and Docker engine boot (needs WSL distro / Desktop first-run) — see Blockers.

## Completed (verified)

### Data / evidence (Phase 1)
- Elexon BMRS API investigation vs official OpenAPI spec (docs/DATA_INVESTIGATION.md):
  endpoint params, streaming envelope quirks, latency, cadence, duplicates, alignment sweep.
- Full January 2026 retrieval: FUELHH (WIND) 1488/1488 half-hours; WINDFOR 19,272 rows /
  264 publishes, publication window 2025-12-30T02:30Z → 2026-02-01 (48h pre-window pad so
  that day-1 day-ahead cutoffs have eligible vintages).
- Canonical snapshot: data/snapshots/latest (+ manifest with counts, checksums, invariants,
  processing policy, alignment + cutoff notes). `scripts/build_snapshot.py` rebuilds offline
  from data/raw or `--live`.

### Domain decisions (documented, testable)
- Alignment: hour-ENDING convention (WINDFOR `startTime T` labels [T−1h, T)), chosen by
  MAE sweep on Jan 2026 (all-pairs 2019 vs 2063 MAE); configurable, raw labels retained.
- Settlement semantics: Europe/London dates, period = h*2 + m//30 + 1; verified around
  London midnight incl. BST.
- Procurement cutoff: preset `day_ahead_1030` (10:30 Europe/London on D−1, i.e. 13h30m
  before London midnight) = N2EX day-ahead auction results published ~10:00 GMT;
  also `day_ahead_gate_0950`, `intraday_auction_1730`, custom ISO-UTC override.
- Vintage rule: winner = argmax publishTime over publishTime ≤ cutoff (inclusive boundary
  at the exact cutoff instant); tie-break = later source row index; never substitutes a
  current forecast where none was eligible; missing stays missing (never zero).
- Scope-gap finding (product-critical): WINDFOR (system-op view incl. embedded wind) ran
  ~+16% above FUELHH (settlement view) in Jan-2026 backfills — surfaced as a transparency
  note, NO rescaling.

### Backend (Phases 2–4, 6)
- Modules: conventions (ISO/London/settlement math), loader (strict normalization,
  latest-publishTime-wins dedupe), vintage (presets + argmax selection + evaluation),
  metrics (MAE/RMSE/bias/error-histogram fixed 500 MW zero-centred bins), dataset
  (interval points + coverage dates), accuracy (cutoff policy, daily/by-hour/coverage),
  elexon_client (retries, backoff) + datasource (snapshot|live modes).
- FastAPI app: /api/health, /metadata, /summary, /series, /vintages, /accuracy with typed
  DTOs, query cutoff overrides, 404 outside coverage, CORS for GET.
- env config: WINDLENS_DATA_MODE, WINDLENS_SNAPSHOT_DIR, ELEXON_BASE_URL,
  WINDLENS_CORS_ORIGINS, WINDLENS_HTTP_TIMEOUT_S/RETRIES, WINDLENS_LOG_LEVEL,
  WINDLENS_API_HOST/PORT, WINDLENS_LIVE_SETTLEMENT_START/END.
- Tests: 46 pytest green (backend/tests: fixtures + loader/conventions + vintage + metrics
  + dataset alignment + API via TestClient on synthetic snapshot).
- Bugs caught by tests: late-binding histogram bounds; timezone-offset string leak; switch
  of lifespan to invalid injections (tests) while auto-loading in prod.

### Real-data API verification (smoke)
- uvicorn loaded snapshot: actuals=1488, vintages=19,272, period Jan-2026 coverage.
- /api/summary on 15 Jan (default cutoff): count 48, MAE 836.8 MW, bias +817.7 MW.
- /api/vintages period 1: 24 vintages (lead +45.5h earliest eligible … −22.5h future),
  selected publish 2026-01-14T09:30Z; custom cutoff filter verified inclusive boundary.
- /api/accuracy: 31/31 days with pairs (day-1 starve fixed by pre-window pad); overall
  count 1488, MAE 2068.7 MW, bias +1834.9 MW; 24 London-hour buckets, 22 histogram bins.

## In progress / next (user-executed)
1. Docker engine boot: Docker Desktop is installed and running but the Linux engine cannot
   start — `wsl -l -v` shows NO WSL distribution installed. Either finish Docker Desktop
   first-run / enable its WSL integration, or `wsl --install -d Ubuntu` (admin + reboot),
   then `docker compose up --build` (configs already validate via `docker compose config`).
2. Vercel deploy: README §8 + vercel/python-note.md describe both single-project and
   dual-deployment patterns; needs user account/token.
3. GitHub repo push + submission form + unlisted video recording (script ready, needs user).

## Recently finished this session
- Frontend: React 19 + TS + Vite 8 + Tailwind 4 + Recharts 3 dashboard; typed api client
  (mirrors backend DTOs), controls bar (date / cutoff preset / custom instant), main chart
  (actual vs cutoff-selected forecast + signed error), stat cards, daily MAE trend,
  zero-centred error histogram, by-London-hour panel (click → vintage explorer), vintage
  explorer (publication ladder, inclusive-boundary cutoff, missing-never-substituted),
  provenance/transparency card. `npm run build` passes; dev proxy verified end-to-end.
  API base is configurable via `VITE_WINDLENS_API_BASE` (defaults to same-origin /api).
- Docs: README.md (product decisions, architecture, run/test/deploy), docs/DEMO_SCRIPT.md
  (timed walkthrough), docs/INTERVIEW_PREPARATION.md (Q&A prep), vercel/python-note.md.
- Docker: backend/Dockerfile (.HEALTHCHECK + snapshot baked in), frontend/Dockerfile
  (node build + nginx serving SPA + reverse-proxying /api), compose/nginx.conf,
  compose.yaml (validates), .dockerignore, .env.example.
- Data fix: day-1 cutoff starvation — WINDFOR snapshot re-fetched with 48h pre-window pad
  (19,272 rows / 264 publishes, 2025-12-30→2026-02-01); build script persists live fetches
  back into data/raw so offline rebuilds reproduce byte-identical checksums.
- API polish: vintage `lead_hours` sign fixed (positive = hours before delivery); health DTO
  emits canonical ISO-Z; accuracy endpoint iterates per-day cutoffs across coverage.
- Docs corrections: settlement-period BST example (23:30Z → period 2), stray non-ASCII
  fragment, retrieval-log row for the extended windfor fetch.

## Environment notes / blockers
- Docker Desktop engine requires a WSL distro (not installed); serverless/CLI deploy needs
  Vercel/GitHub accounts — user-executed.
- Background uvicorn smoke server may still run on 127.0.0.1:8814 (kill freely).

## Deadline plan (16h) — through H10 done
- ✔ H2–4 backend (all tests green, real-data smoke pass).
- ✔ H4–8 frontend dashboard (built, proxy-verified against live API).
- ✔ H8–10 integration + edge cases (cutoff boundary inclusive, missing-not-zero,
  hour-picker ↔ vintage explorer linkage, provenance transparency panel).
- ✔ H10–12 Docker + deployment configs (pending engine boot + accounts).
- ✔ H12–14 README + demo script + interview prep + final test pass (46/46 green).
- H14–16 (user): video recording, repo push, submission form.
