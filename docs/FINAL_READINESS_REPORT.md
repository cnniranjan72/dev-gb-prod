# WindLens — Final Readiness Report

Date: 2026-10-24. Verdict: **READY WITH DISCLOSED LIMITATIONS** (limitation list in §6;
the only mandatory deliverables that remain are user-performed and listed in §7).

## 1. Summary

WindLens evaluates UK national wind-forecast accuracy for January 2026 with strict
historical forecast-vintage selection (`argmax publishTime ≤ cutoff`), serving a React
dashboard + FastAPI backend from one Python serverless project on Vercel, from Docker, or
from a local dev process — all from the same checksummed BMRS snapshot.

## 2. Findings status (from docs/PRE_SUBMISSION_AUDIT.md)

| ID | Sev | Item | Status |
| --- | --- | --- | --- |
| 1 | P0 | PBKDF2 format-string defect broke every login | FIXED + regression test |
| 2 | P0 | `pyjwt` missing → app import failure across all targets | FIXED (venv + pyproject + requirements) |
| 3 | P0 | Half-built auth wiring (Depends, LoginResponse, router) | FIXED |
| 4 | P1 | CORS methods/headers too narrow for auth flows | FIXED |
| 5 | P1 | Analytics endpoints publicly readable | FIXED (viewer/analyst RBAC) |
| 6 | P1 | No auth tests | FIXED (14 auth/RBAC tests) |
| 7 | P1 | Repo has zero commits | **PENDING — user must authorize commit/push** |
| 8 | P2 | Docker images stale vs auth code | RESOLVED (rebuild verified) |
| 9 | P2 | Serverless user-store persistence | DISCLOSED (README §10) |
| 11 | P3 | Single-chunk 500 kB+ bundle | Deferred |

## 3. Tests executed (this audit)

| Command | Result |
| --- | --- |
| `.\.venv\Scripts\python -m pytest backend -q` | **60 passed** |
| `npm --prefix frontend run build` (tsc + vite) | green (chunk-size warning only) |
| `docker compose up --build -d` then health/login/gated/401 probes | all pass |
| Live uvicorn auth smoke (`login → summary → vintages → accuracy`) | all pass |
| `scripts/audit_trace.py` (2026-01-02, ‑01‑15, ‑01‑31) | HAND-CALC == SERVICE (`AGREES`) |
| Production probes (see §5) | all pass |

## 4. Data-validation evidence

* Snapshot invariants: actuals 1488/1488 half-hours; 19,272 forecast rows over 264
  publication vintages (2025-12-30 → 2026-02-01 window so day-1 cutoffs are usable).
* Independent trace reproduces displayed MAE/RMSE/bias for three sample days, and proves
  post-cutoff publications are excluded from selection (320 excluded winners on Jan-15 for
  the traced hour window).
* WINDFOR labels verified empirically to be on-the-hour, hour-ending; both half-hours of an
  hour map to the same hourly vintage (documented convention, raw labels retained).

## 5. Deployment verification evidence (2026-10-24)

| Check | Result |
| --- | --- |
| `https://windlens-flame.vercel.app/api/health` | 200, snapshot counts 1488/19272 |
| `POST /api/auth/login` (seeded analyst/admin) | 200 + JWT |
| `GET /api/summary?date=2026-01-15` **with token** | 200 (MAE 836.8, 48 pairs) |
| `GET /api/vintages…` **with analyst token** | 200 (ladder 24, selected 15454.0) |
| Same requests **anonymous** | **401** |
| Malformed `Bearer garbage` | **401** |
| SPA `/` | 200 |
| Docker (`:8000`, `:8085`) | health/login/auth/analytics/401/SPA all pass |

## 6. Known limitations (disclosed)

1. Analyst-facing auth uses seeded demo accounts; on Vercel account writes are in-memory
   per invocation (read-only FS). Docker persistently manages accounts via JSON store.
2. WINDFOR is hourly; intra-hour half values are uniform by design.
3. WINDFOR↔FUELHH scope gap (≈ +16%) is surfaced, not reconciled.
4. Single-chunk frontend bundle (engineering-cosmetic).
5. Live BMRS mode exists but the deployed instances use the fixed snapshot (stated openly
   in the UI provenance panel).

## 7. Remaining manual actions (user-performed)

1. **Commit + push to the public repo** (repository currently has no commits). Anonymous
   repo name required by the challenge — create e.g. `windlens-8f3a2c` (random suffix),
   push `main`, then re-link Vercel GitHub connection (or keep CLI deploys).
2. **Record the demo**: follow docs/DEMO_SCRIPT.md (customer <5 min + technical <5 min),
   upload **unlisted** YouTube, keep total ≤10 min.
3. **Submission form** — locate/complete it per the challenge board (no form URL was
   provided to this agent; it must not be invented). Then open every submitted URL in an
   incognito window and verify: repo, deployment, health endpoint, login works, video plays.
4. Rotate the Vercel CLI token that was pasted in chat earlier (account → Tokens).

## 8. Mandatory submission checklist (agent-verifiable only)

| Requirement | Status |
| --- | --- |
| React frontend | DONE (React 19 + TS + Vite) |
| Python backend | DONE (FastAPI) |
| Elexon national WIND + WINDFOR, Jan-2026 | DONE (checksummed snapshot + live mode) |
| Docker | DONE (verified stack) |
| Vercel/Heroku-compatible deployment | DONE (https://windlens-flame.vercel.app) |
| Public repo, anonymous name | **PENDING (needs user git push)** |
| README w/ explicit AI disclosure | DONE (§9) |
| Unlisted YouTube ≤10 min (2×≤5) | PENDING (script ready in docs/DEMO_SCRIPT.md) |
| Submission form + incognito verification | PENDING (user) |

## 9. Five strongest engineering decisions to discuss

1. **Vintage selection definition** — one line of code that eliminates look-ahead bias, with
   tests at the exact-cutoff boundary.
2. **Missing is not zero** — coverage panels make the denominator visible per metric.
3. **Snapshot-first provenance** — checksummed manifest + independent audit script
   (traceability without trusting the app code).
4. **Cutoff presets in Europe/London time** — DST-safe by construction; custom UTC instant
   is labelled "analytical lens" in the UI.
5. **Auth/RBAC as route-visible dependencies** — the RBAC map reads directly from endpoint
   signatures; distinct 401/403 semantics; PBKDF2+JWT implemented without heavyweight deps.

## 10. Verdict

**READY WITH DISCLOSED LIMITATIONS** — technically complete, tested, deployed and
domain-verified. The remaining mandatory items (git push, video, form) are user actions;
everything agent-verifiable has been executed and evidenced above.
