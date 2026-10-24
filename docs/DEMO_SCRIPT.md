# DEMO_SCRIPT — WindLens walkthrough (customer ≤5:00 + technical ≤5:00)

Recording plan: 1440p, browser fullscreen, terminal only when needed, 1.1× narration pace.

## 0:00–0:25 — The hook: "the dashboard that doesn't cheat"
- Open `https://windlens-flame.vercel.app` (or `http://localhost:8085` in Docker).
- Sign in on the login screen with the seeded demo account — say: "access is role-gated —
  choose the ANALYST demo account the README documents (analyst@windlens.demo). Here I can
  reproduce exactly what a desk would have seen; the admin account additionally maintains
  users." (Show the role badge in the header.)
- Say: "Wind trade desks committing day-ahead volumes see only the forecasts that existed
  before their decision moment. Most forecast-vs-actual dashboards plot the LATEST forecast —
  which didn't exist at decision time. WindLens shows exactly what was knowable, and what
  it got wrong."
- Point at the header chips: data mode (snapshot = reproducible), row counts.

## 0:20–0:55 — Day view (2026-01-15)
- The main chart: teal/green actual line (FUELHH settlement wind), dashed cyan selected
  forecast, dotted purple error band (forecast − actual, signed).
- Stat cards: MAE 836.8 MW · RMSE 995.3 · bias +817.7 (over-forecast), coverage 48/48 —
  "every number here is a half-hour in January; 'valid pairs' is the honest denominator."
- Hover tooltip: settlement period, MW values; note the hour-ending alignment note under
  the chart.

## 0:55–1:30 — The vintage explorer (the differentiator)
- Scroll to "Historical vintage explorer"; period slider at 1.
- Point to the ladder: latest at top; purple "selected" row is the newest publication at
 /before the cutoff; rose "after cutoff (excluded)" rows are the ones a trader could NOT
  know.
- Drag the slider through periods; the explorer re-fetches per half-hour.
- Set cutoff preset to "Auction gate close (09:50 GMT D−1)" and re-show how the selection
  changes; then "Custom instant" with `2026-01-14T09:50:00Z` — same effect; the cutoff is a
  product knob, not a hardcode.

## 1:30–2:10 — The month: honesty about the rule's cost
- "What the cutoff rule does across the month": daily MAE bars — call out ramp days vs calm
  days; the error histogram panel: fixed 500 MW bins SYMMETRIC around zero ("scale fixed by
  policy, not data — two periods stay comparable; purple = over-forecast, rose = under").
- Overall: 1488 pairs, MAE ≈ 2.1 GW, bias ≈ +1.8 GW.
- Click a bar in "Accuracy by hour of day" to jump into that hour's vintage view.

## 2:10–2:40 — Data provenance + the two-views finding
- Provenance card: source endpoints, retrieval window, delivery-month coverage.
- Transparency note: WINDFOR = system-operator view (includes embedded wind), FUELHH =
  settlement-visible BM wind; Jan-2026 backfill gap ≈ +16%. "We report both as published;
  rescaling would fabricate a dataset that maps to neither."
- Terminal (10 s): `.\.venv\Scripts\python -m pytest backend` → **60 passed** (add: "14 of
  them pin the auth/RBAC behavior and a hash-encoding bug the roundtrip test caught").

## 2:40–3:20 — Architecture & data integrity (fast, but visible)
- `docs/DATA_INVESTIGATION.md` open at the alignment sweep; mention publish lag (median
  30 min, corrections up to 145 min → re-release dedupe = latest publishTime wins).
- `data/snapshots/latest/manifest.json` — counts, checksums, invariants (1488/1488, zero
  missing), policies. "The API loads this manifest at boot; /api/metadata exposes it."
- Docker: `docker compose up --build` (if already running, skip to the URL).

## 3:20–3:45 — Live-mode demo (only if stable network)
- Stop server; run with `WINDLENS_DATA_MODE=live WINDLENS_LIVE_SETTLEMENT_START=2026-01-05
  WINDLENS_LIVE_SETTLEMENT_END=2026-01-08` → fetches straight from BMRS, invariants hold.

## 3:45–4:00 — Close
- "Ship-ready: Dockerized, 60 tests, role-gated access, typed client/server contract,
  documented product decisions, and a Kaggle-in-reverse twist: it shows you the data as it
  was, not as we wish it had been."

### Recording checklist
- [ ] Incognito window open (no cached tokens)
- [ ] Login screen visible first (demo creds autofill button)
- [ ] 2026-01-15 default view has data loaded before narration
- [ ] Vintage explorer: 14 period × 24 ladder screenshot command ready
- [ ] Terminal: pytest green (60 passed) in advance
- [ ] Cutoff preset switch + custom instant both demonstrated
- [ ] Stop before rambling; hard cut at 5:00 per section

---

# TECHNICAL WALKTHROUGH (separate section, ≤5:00)

## T0:00–T0:40 — Data path (integrity-first)
- `data/raw/` → `scripts/build_snapshot.py` → `data/snapshots/latest/` (fuelhh_wind.json,
  windfor.json, manifest.json with SHA-256 checksums + invariants).
- Say: "The manifest pins the retrieval window (Dec-30 → Feb-1 so day-1 cutoffs have
  eligible vintages) and the policies; the API refuses to guess — it reports."

## T0:40–T2:00 — The one rule that matters
- Open `backend/app/services/vintage.py` (60 lines total). Highlight `select_forecast`:
  filter `hour_end == T and publish ≤ cutoff`, then `max` by `(publish_time, row_index)`.
- Complexity: O(candidates per hour) ≈ 24; the day is 48 such scans.
- Show the boundary test (`test_vintage_selection`): publish exactly at cutoff IS eligible.
- Show the exclusion proof in the UI ladder (after_cutoff rows highlighted).

## T2:00–T3:00 — Traceability evidence (the strongest 60 seconds of the demo)
- Terminal: `python scripts/audit_trace.py` — the script re-parses raw JSON files with its
  own independent code and hand-computes MAE/RMSE/bias; both print identical numbers, then
  "TRACE AGREES with service path". On Jan-15: 836.8 / 995.3 / +817.7, 48 pairs.
- Say: "You do not have to trust my dashboard code — the numbers are re-derivable from the
  raw files alone."

## T3:00–T3:50 — Auth skeleton (honest scope)
- `security.py`: PBKDF2 210k + per-user salt + constant-time compare; HS256 JWTs with
  env-provided secret; `require_role` dependency visible in every endpoint signature.
- Show 401 (anonymous) vs 403 (viewer hits /vintages) — the role ladder is real.
- Note: "On Vercel the account store is memory-per-invocation (disclosed limitation);
  the analysis itself is auth-insensitive — the snapshot is the same everywhere."

## T3:50–T4:30 — Tests & CI
- `pytest backend` → 60 pass list scroll; mention the two bug-catch stories:
  (1) day-1 cutoff starvation found only by live smoke (fetch window fixed),
  (2) PBKDF2 `$$` format defect caught by the roundtrip test during this audit.
- `.github/workflows/ci.yml`: pytest + frontend build on push/PR.

## T4:30–T5:00 — Deployment + close
- One project on Vercel: SPA + Python serverless function, snapshot baked in; identical
  Docker stack locally (`compose up`).
- "Same snapshot in CI, Docker and production — configuration differences reduced to env
  vars; anything else is treated as a bug."
