# WindLens — UK Wind Forecast Intelligence

**Gridbricks hiring challenge · January 2026 procurement · Elexon BMRS data**

WindLens shows what GB electricity traders could have known about wind generation when they
had to commit volumes in the day-ahead market, how wrong those commitments turned out to be,
and which exact forecast vintage produced every number on screen.

---

## 1. What problem does this solve?

Wind is the largest—and least predictable—source of GB renewable power. Traders referencing
market data at 10:30 on D−1 do **not** see today's forecast: they see the snapshot of data
published **before** that instant. Most "forecast vs actual" dashboards silently cheat by
plotting the *latest* forecast. WindLens never does: for every half-hour it resolves the
forecast vintage that existed at the configured decision cutoff, shows the alternatives that
were available and the ones that arrived too late, and reports honest metrics.

## 2. Product decisions (the interesting part)

| Decision | What we do | Why |
|---|---|---|
| **Vintage rule** | `winner = argmax publishTime over publishTime ≤ cutoff` (inclusive at the exact cutoff); deterministic tie-break on source row index | The cardinal rule that kills look-ahead bias |
| **Missing data policy** | An actual with `generation: null` stays **missing** (never a zero); "no forecast was published before cutoff" stays **unavailable** (never substituted with today's data) | Dashboards that silently impute hide the story |
| **Alignment** | WINDFOR `startTime T` labels the hour **ending** at T; hourly MW is applied to both half-hours of that hour | Empirically resolved on Jan-2026 via MAE sweep (2019 MW vs 2063 MW); raw labels retained |
| **Cutoff semantics** | Presets `day_ahead_1030` (default), `day_ahead_gate_0950`, `intraday_auction_1730`, plus custom ISO-UTC; computed in **Europe/London** so it is DST-safe | Anchored to the N2EX day-ahead auction (gate 09:50 GMT D−1, results ~10:00 GMT) |
| **Two data views** | WINDFOR (system-operator view incl. embedded wind) vs FUELHH (settlement-visible BM wind) — ≈ **+16%** mean gap in Jan-2026 backfills — reported **as-published, never rescaled**, surfaced as a transparency note | Blending or rescaling datasets would fabricate a third, unmapped dataset |

Every panel in the UI states where each number comes from; the vintage explorer shows all
candidate publications and shades the ones a trader could/couldn't know.

## 3. Data (reproducible)

* Source: `https://data.elexon.co.uk/bmrs/api/v1` — `/datasets/FUELHH` (WIND) and
  `/datasets/WINDFOR`, against the official OpenAPI spec (see docs/DATA_INVESTIGATION.md).
* January 2026: **1488/1488** half-hours of actuals; **19,272** forecast rows across **264**
  publication vintages (window 2025-12-30 → 2026-02-01 so that D−1 cutoffs for day 1 work).
* Snapshot includes a manifest with source URLs, counts, checksums, invariants (zero missing
  half-hours, publish cadence facts) and all processing policies. `scripts/build_snapshot.py`
  rebuilds deterministically from `data/raw` or live.

## 4. Architecture

```
frontend/                 React 19 + TypeScript + Vite + Tailwind 4 + Recharts
src/lib/api.ts            typed client (mirrors backend DTOs, JWT attach + 401 handling)
src/components/           LoginView · ForecastChart · VintageExplorer · AccuracyPanels · Header
backend/app/services/     conventions · loader · vintage · metrics · dataset · accuracy
                          elexon_client · datasource (snapshot|live) · security (PBKDF2+JWT) · users (RBAC store)
backend/app/api/          FastAPI routes (health | metadata | summary | series | vintages | accuracy | auth)
backend/tests/            60 pytest cases on a hand-crafted synthetic month + auth/RBAC regressions
scripts/                  inspect_data.py · build_snapshot.py · audit_trace.py (independent raw-data verification)
data/snapshots/latest     snapshot + manifest (checksummed)
docs/                     DATA_INVESTIGATION.md · DEMO_SCRIPT.md · INTERVIEW_PREPARATION.md · PRE_SUBMISSION_AUDIT.md
```

**Auth & RBAC** — `/api/auth/login` issues an HS256 JWT (24 h TTL); passwords are stored
as PBKDF2-HMAC-SHA256 (210k iterations, per-user salt). Roles `viewer < analyst < admin`
gate the analytics endpoints; `/api/health`, docs and the login endpoint stay public.
Seeded demo accounts (documented for reproducibility, overridable by env):

| Account | Password | Can do |
|---|---|---|
| `analyst@windlens.demo` | `windlens-analyst` | dashboards + vintage explorer |
| `admin@windlens.demo` | `windlens-admin` | everything incl. account management |
| `viewer@windlens.demo` | `windlens-viewer` | dashboards (no vintage explorer) |

**API** (FastAPI, prefix `/api`, query params `preset`/`cutoff` override everywhere):

| Endpoint | Purpose | Min role |
|---|---|---|
| `GET /health` | mode, coverage window, row counts | public |
| `POST /auth/login` | issue JWT | public |
| `GET /auth/me` | current identity | viewer |
| `GET /metadata` | snapshot manifest (provenance, policies, checksums) | viewer |
| `GET /summary?date=` | metrics + coverage for one delivery day | viewer |
| `GET /series?date=` | 48 half-hours: actual, cutoff-selected forecast, signed error | viewer |
| `GET /vintages?date=&period=` | full publication ladder for one half-hour + winner | analyst |
| `GET /accuracy` | month-wide daily/by-London-hour MAE/bias, zero-centred 500 MW error histogram | analyst |
| `GET/POST/DELETE /auth/users…` | account management | admin |

## 5. Run it

### Local dev
```powershell
# backend (Python 3.12)
py -3.12 -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --port 8000

# frontend
cd frontend; npm install; npm run dev   # proxies /api → http://127.0.0.1:8000
```

### Docker
```bash
docker compose up --build
# UI     → http://localhost:8085
# API    → http://localhost:8000/api/health
```

### Env vars (see `.env.example`)
`WINDLENS_DATA_MODE`, `WINDLENS_SNAPSHOT_DIR`, `ELEXON_BASE_URL`, `WINDLENS_CORS_ORIGINS`,
`WINDLENS_HTTP_TIMEOUT_S`, `WINDLENS_HTTP_RETRIES`, `WINDLENS_LIVE_SETTLEMENT_START/END`,
`WINDLENS_JWT_SECRET` (required in production; tokens are invalid if it changes),
`WINDLENS_AUTH_ADMIN_EMAIL`, `WINDLENS_AUTH_ADMIN_PASSWORD`.

## 6. Tests

```powershell
.\.venv\Scripts\python -m pytest backend
# 60 passed — vintage exclusion, cutoff boundary, dedupe/re-release, BST settlement
# math, missing-not-zero, histogram fixed-width properties, FastAPI contract tests,
# PBKDF2/JWT/RBAC regressions (incl. the double-`$` hash-format bug it caught)
```

Notable test-caught bugs: a late-binding bug in histogram bin bounds, an +00:00/Z leak in the
health DTO, the day-1 forecast starvation (publish-window not covering D−1 cutoff) found by
live-data smoke tests, and a password-hash format-string defect that silently broke every
login (see docs/PRE_SUBMISSION_AUDIT.md).

The raw-data numbers can be independently verified — the audit script re-derives actuals,
vintage selection and MAE/RMSE/bias straight from the snapshot JSON without importing the
application:

```powershell
.\.venv\Scripts\python scripts\audit_trace.py data\snapshots\latest 2026-01-15
# HAND-CALC mae=836.8 rmse=995.3 bias=817.7  → TRACE AGREES with service path
```

## 7. Headline numbers (snapshot, default cutoff 10:30 London D−1)

* Month pairs: **1488** · overall MAE **≈ 2,069 MW** · mean bias **≈ +1,835 MW** (over-forecast)
* Daily MAE swings strongly with wind ramps; by-London-hour panel localises the pain.
* Screenshot-worthy day: 2026-01-15 (count 48, MAE 836.8 MW, bias +817.7 MW).

## 8. Deployment

* **Live deployment (verified 2026-10-24): https://windlens-flame.vercel.app** — React SPA +
  FastAPI serverless (Python runtime) in one project; snapshot baked into the build;
  anonymous requests to analytics endpoints get `401`, signed in demo accounts see real data.
* Docker: `frontend/Dockerfile` + `backend/Dockerfile` + `compose.yaml` (nginx serves the
  SPA and reverse-proxies `/api`); `docker compose up --build` verified 2026-10-24.
* CI: `.github/workflows/ci.yml` runs `pytest backend` and the frontend production build
  on every push/PR.

## 9. AI-tool disclosure (explicit, as required by the challenge)

This submission was produced with AI coding assistants (Claude / GLM-based agents) used as
engineering tools under direct instruction: API research against the Elexon OpenAPI spec,
scaffolding, implementation of features, test writing, debugging, deployment automation and
this documentation. All architectural and product decisions (cutoff presets, vintage rule,
missing-data policy, alignment convention, metric surface) were reviewed and verified with
independent scripts and tests:

* every displayed metric is reproduced hand-calculated by `scripts/audit_trace.py` from raw
  snapshot files in an independent code path;
* the test suite (60 cases) expresses the domain rules (cutoff boundary, duplicate handling,
  missing-not-zero, DST settlement math) and caught real defects during development;
* the domain logic is small and explicitly commented so it can be read in one sitting.

## 10. Known limitations

* WINDFOR is hourly; half-hour resolution inside an hour is uniform (documented assumption).
* Live mode pads publication windows (−48 h) for cutoff eligibility, but BMRS latency/lag
  means "today" can legitimately be missing mid-day actuals — surfaced, not imputed.
* The two dataset views differ materially (+16%); we expose rather than reconcile them.
* Error histogram bin size (500 MW) is a fixed product decision — changed only deliberately.
* On Vercel (read-only FS) admin-created accounts live in memory per invocation; the seeded
  demo accounts are always available. Persistent account management works in Docker.
* Auth is application-level (JWT + PBKDF2) — not OAuth SSO; a production deployment would
  bring a managed identity provider and a real database instead of the JSON user store.

## 11. Submission assets

* `docs/DEMO_SCRIPT.md` — customer demo (<5 min) + technical walkthrough (<5 min) script and
  recording checklist.
* `docs/INTERVIEW_PREPARATION.md` — 26 prepared answers incl. adversarial follow-ups.
* `docs/PRE_SUBMISSION_AUDIT.md` — evidence-based audit trail of this submission.
