# WindLens — Pre-Submission Audit

Executed: 2026-10-24. Test baseline before audit actions: **46 tests, all
failing to collect** (backend did not import); after fixes: **60/60 pass**.
Evidence-first: every finding below was reproduced by running commands, not
asserted from memory.

## Headline results

| Area | State after audit |
| --- | --- |
| Backend tests | 60/60 pass (46 baseline + 14 new auth/RBAC regressions) |
| Frontend | `npm run build` green (TS + production bundle) |
| Domain trace | Independent re-parse of raw snapshot agrees with service path exactly (MAE/RMSE/bias, hand-calculated, 3 sample days) |
| Docker | Rebuilt with auth; `login → token → analytics` verified through the container; anonymous 401 |
| Deployment | https://windlens-flame.vercel.app verified live: health, login, gated analytics, 401 paths |
| Auth | JWT (HS256) + PBKDF2 (210k iters) + RBAC viewer<analyst<admin, seeded demo accounts |

## Findings

| # | Severity | Finding | Evidence | Consequence | Fix | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **P0** | Password hashes unrecoverable: format template emitted `iter$$salt$hash` (double `$`), verifier parsed empty salt → every login failed | `hash_password("x")` output showed `pbkdf2_sha256$210000$$9pSC...`; `verify_password(...)` returned `False` for correct input | Total auth outage (all accounts unusable) | Template → `pbkdf2_sha256${}${}${}` | `test_password_hash_roundtrip_and_rejection`; live login via curl/uvicorn |
| 2 | **P0** | `jwt` package missing from venv and dependency manifests → `app.main` import failed, **whole test suite could not collect** | `pytest` → `ModuleNotFoundError: No module named 'jwt'` | App cannot start anywhere (local, Docker, Vercel) | `pip install pyjwt`; added to `pyproject.toml` + `backend/requirements.txt` | `import jwt` → 2.15.1; full pytest green; Docker image rebuild OK |
| 3 | **P0** | Half-built auth wiring: `Depends` not imported in `routes.py`, no `LoginResponse` DTO, auth router missing from `main.py` | reading `routes.py` head / `dtos.py` after prior session's partial edits | NameError at import; login endpoint 500 | Import repaired; `LoginResponse`+`UserOut` added to `dtos.py`; `app.include_router(auth_router)` | pytest 60/60; uvicorn smoke |
| 4 | **P1** | CORS allowed only `GET` — the SPA login POST and admin DELETE would be blocked cross-origin | `app.add_middleware(..., allow_methods=["GET"])` | Auth unusable from browser deployment | `["GET","POST","DELETE"]` + explicit `Authorization` header | Prod login from SPA origin (rewrites make it same-origin; also tested cross-origin header set) |
| 5 | **P1** | Analytics endpoints unauthenticated — reviewers could evaluate "metrics" without any account; no separation between dashboard and user management | `curl /api/summary` → 200 pre-audit | Weak engineering credibility | `require_role("viewer"/"analyst")` on metadata/summary/series/vintages/accuracy; `/health` + auth endpoints public; admin-only user CRUD | RBAC matrix tests; prod anonymous → 401 |
| 6 | **P1** | No tests for auth at all | no `test_api_auth.py` before audit | Auth regressions silent (finding #1 proves it) | 14 tests: PBKDF2 roundtrip/salting, login fail paths, expired + malformed tokens, RBAC matrix, account CRUD, last-admin guard | pytest 14/14 |
| 7 | **P1** | Repository has **zero commits** — mandatory "public repository" deliverable unmet | `git log` → `fatal: your current branch 'main' does not have any commits yet` | Submission impossible until committed/pushed | **Remaining (user action required)**: commit + push to an anonymous-name repo; then connect Vercel CI | this document |
| 8 | **P2** | `Dockerfile` schema caches? no — rebuild verified auth + frontend images take the new code | `docker compose up --build -d`; login through container 200 | stale image risk | rebuild executed | health/login/401 through Docker |
| 9 | **P2** | Serverless user store falls back to in-memory on read-only FS — account writes don't persist across Vercel invocations (documented behavior, seeded accounts unaffected) | `users.py` `_try_persist` catches OSError; Vercel FS read-only | Admin-created users vanish (documented; logs disclose) | documented in README + logs | prod login of seeded accounts works |
| 10 | **P2** | Duplicate-vintage ordering on exact ties | `select_forecast` tie-breaks by `row_index` (already deterministic) | none — verified defensive | none needed | `test_vintage_selection` duplicate-tie tests |
| 11 | P3 | Frontend bundle >500 kB (single chunk) | `npm run build` warning | cold-load cost only | code-splitting deferred | build warning |

## Domain-correctness evidence (Phase 2)

`scripts/audit_trace.py` re-implements the domain rules from the raw snapshot
files **without** reusing the loader/dataset code, then cross-checks the
service path:

- WINDFOR `startTime` values are on the full hour only (`windfor_label_minutes[0]`)
  and label the hour ENDING at T; both half-hours of an hour map to the same
  hourly vintage (`hour_end_label(i) = floor(i)+1h`, documented in
  `docs/DATA_INVESTIGATION.md`).
- Cutoff rule `argmax publishTime ≤ cutoff` with the preset
  `day_ahead_1030` (D−1 10:30 London → `2026-01-14T10:30Z` for Jan 15).
  The sample hour had 24 records; 12 published after the cutoff were excluded.
- Hand-calculated metrics vs API for sample days (all agree):

| Day | MAE | RMSE | Bias (f−a) | Valid pairs |
| --- | --- | --- | --- | --- |
| 2026-01-02 | 3177.3 | 3233.5 | +3177.3 | 48 |
| 2026-01-15 | 836.8 | 995.3 | +817.7 | 48 |
| 2026-01-31 | 1618.1 | 1750.7 | +1618.1 | 48 |

MAE == bias on these days because all per-interval errors were positive
(systematic over-forecast) — cross-checked per-interval in the trace output,
not an artifact.

## Not verified / remaining

- Git commit/push (user has not authorized this yet) and the anonymous repo
  name — mandatory deliverable.
- Demo videos, submission form, incognito check — user actions.
- CI will only be demonstrably green on GitHub after the first push; locally
  the same commands (pytest 60/60, `npm run build`) pass.
