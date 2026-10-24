# INTERVIEW_PREPARATION — WindLens (Gridbricks challenge)

Anticipated Q&A, with the answers we actually built and verified. Product decisions are the
differentiators: know the five in §2 cold, and rehearse the adversarial list in §8.

## 90-second architecture explanation (practice out loud)

WindLens is a December-fixed snapshot of Elexon BMRS (actual wind + every forecast vintage)
behind a FastAPI service that answers one question per half-hour: *which forecast could a
trader at the configured decision cutoff have used, and how wrong was it?* The React frontend
renders the interval chart, the publication ladder, accuracy panels and the data-provenance
manifest. One equation drives correctness everywhere: `winner = argmax publishTime ≤ cutoff`.
Tests (60), an independent audit script and a checksummed manifest make every number
traceable to a raw source record. The same snapshot serves the Docker stack (`compose up`)
and the Vercel serverless deployment, so local, CI and production disagree about nothing.

## 60-second explanation of the hardest decision (practice out loud)

The hardest call was the WINDFOR timestamp convention: the API labels forecast records with
`startTime` values that resolve — empirically, against actuals — as **hour-ending** labels
applied to both half-hours of that hour. We resolved it with an MAE sweep (2063 MW for the
hour-ending reading vs 2019 MW for the forward reading), said out loud that the margin (~3%)
is soft evidence, kept the raw labels in the snapshot so the alternative reading can be
re-derived, and documented the choice next to the data instead of hiding it in code.

## 1. Why is the vintage rule the right one?

`winner = argmax publishTime over {publishTime ≤ cutoff}` — because a trader at cutoff C can
only use publications at-or-before C. Non-selection of post-cutoff publications is not a
plotting choice; it is the definition without look-ahead bias. Subtleties we handle:

1. **Inclusive boundary** — a publication at exactly 10:30:00Z with cutoff 10:30:00Z is
   usable (and tested).
2. **Determinism on ties** — BMRS occasionally returns duplicate keys; the later source row
   wins (defined, stable, tested).
3. **No substitution** — if no vintage existed at cutoff (day 1 with an un-padded fetch, or
   a stable grid day), we display "unavailable"; substituting today's forecast is exactly
   the silent-cheat pattern this product exists to kill.
4. **Corrections** — FUELHH re-releases (median lag 30 min, max ~145 min) resolve by
   "latest publishTime wins" per interval.

## 2. The five product decisions (say them proud)

1. **Vintage rule** (§1).
2. **Missing is not zero** — `generation: null` renders as a gap, never 0. Zeros in wind
   forecasting are a supported claim ("no wind"), and faking one inflates MAE dishonestly.
3. **Hour-ending alignment** — WINDFOR `startTime T` labels [T−1h, T); chosen empirically
   (MAE sweep), kept configurable, raw labels retained.
4. **Cutoff anchored to the N2EX day-ahead auction** (10:30 London D−1 default; presets for
   gate close and an intraday alternative), computed in Europe/London for DST safety.
5. **Two dataset views, never reconciled quietly** — WINDFOR (system-op view incl. embedded
   wind) vs FUELHH (settlement view) differ ≈ +16% in Jan-2026 backfills; both are surfaced
   as-is with a transparency panel instead of a rescale that would "fix" one relationship by
   inventing a third dataset.

## 3. Data-quality findings (proves you looked)

- Jan-2026: 1488/1488 half-hours, zero gaps (great for reproducibility).
- WINDFOR cadence: 8 scheduled vintages/day (02:30 … 22:30) + occasional 12:25 extras; lead
  range −25.5 h … +66.5 h; 24 vintage candidates per delivery hour on average.
- Error histogram scale is policy (500 MW, zero-centred), not data-derived.
- Day-1 cutoff starvation discovered ONLY by live smoke tests (not visible in synthetic
  fixtures) → snapshot fetch extended to −48 h publication window.

## 4. Testing strategy

- **60 pytest cases** with a hand-built synthetic January designed to trip every policy:
  missing actual row, null generation, duplicate forecast key, CCGT leakage, re-release
  dedupe, post-cutoff vintage, exact-cutoff boundary, DST settlement math, plus auth/RBAC
  regressions (expired/malformed JWT, wrong password, role matrix, last-admin guard).
- FastAPI contract tests through TestClient (lifespan injection makes test isolation exact);
  each test seeds its own user store so auth tests can't pollute each other.
- Independent verification: `scripts/audit_trace.py` re-derives actuals, vintage selection
  and MAE/RMSE/bias straight from raw snapshot JSON (no application code) — it agreed on
  every sampled day (836.8/995.3/+817.7 for Jan 15, etc.).
- Property-ish checks: histogram fixed-width bins; empty-set behavior returns count 0 and
  nulls, never NaNs.
- The audit fully demonstrated the catch-a-real-bug story: the auth format-string defect
  (`pbkdf2_sha256$210000$$salt$hash`) silently broke **every** login; the roundtrip test now
  pins the encoding.

## 5. Architecture answers

- **Why FastAPI + Pydantic DTOs?** typed responses shared verbatim with the TS client;
  validation at the boundary; lifespan-managed singleton dataset.
- **Why snapshot-first data mode?** reproducibility: a checksummed manifest + "latest
  publishTime wins" replay produce identical API output every boot; live mode exists but is
  opt-in via env vars.
- **Why nginx in front of the backend in Docker?** same-origin SPA fetches, no CORS
  ambiguity locally, and the compose file doubles as a mini "production".
- **Scaling**: the dataset is 19k rows and immutable per boot; no cache needed at this size
  (the honest answer).
- **Why serverless on Vercel?** free, supported Python runtime (GA), the SPA and API ship in
  one project, and the snapshot is baked into the build — the same binary boundary as Docker.

## 6. What I'd do next (shows product-thinking)

- Ramp-hour severity panel (dMW/h before vs after) — procurement risk correlates with ramp
  mis-forecast more than with MAE.
- Cutoff sensitivity surface (MAE/bias as a function of cutoff hour).
- Registering the WINDFOR↔FUELHH gap by connected-plant mix (still without reconciling).
- Intraday revision-effect chart: bias of vintage at cutoff − bias of end-of-day vintage,
  per hour — quantifies the "value of waiting".

## 7. Dead-honest limitations

- Hourly forecast → uniform intra-hour (documented; margin measured).
- The alignment sweep margin is statistically soft — we chose, we didn't divine.
- Live mode latency depends on BMRS; snapshot mode is the deployment default for review.
- This is a wind-forecast analysis **pilot**, not a procurement optimizer (see Q14).
- On Vercel the user store is memory-per-invocation (read-only FS); Docker persists JSON.

## 8. Adversarial Q&A (25+, based on the actual code)

**Q1. Why is the forecast cutoff essential?** Without it you evaluate data the trader could
not have had — every dashboard showing "the forecast" with no cutoff silently uses the final
vintage and scores a best-case that never existed at decision time. Our whole product is the
difference between those two numbers.

**Q2. How would you prove there is no look-ahead bias?** Three ways, all implemented:
(i) the selection function is pure over `publishTime ≤ cutoff` and covered by boundary
tests; (ii) the vintage explorer shows, per interval, publications flagged `after_cutoff`
that the metrics provably ignore; (iii) `scripts/audit_trace.py` re-implements selection
from raw files and agrees with the API.

**Q3. How do you know all January intervals were retrieved?** Pagination until the dataset
is exhausted + an invariant check in the snapshot manifest: 31 days × 48 = 1488 expected
half-hours, 1488 found, zero gaps; the manifest checksums each raw file.

**Q4. How would a daylight-saving transition affect alignment?** Period 46–50 can occur on
transition days; `settlement_period_local` derives the 1-based period from Europe/London
wall-clock arithmetic, and the interval window comes from anchoring London midnight to UTC —
so a 50-period day yields 50 intervals; settlement dates are resolved from interval
mid-points to avoid boundary ambiguity. January has no transition, so this is tested on
synthetic fixtures, not observed in the data.

**Q5. What happens if a forecast is published exactly at the cutoff?** It is eligible —
`≤` is inclusive and tested (`test_vintage_selection` boundary case).

**Q6. How do you resolve conflicting duplicate records?** Actuals: latest publish-time wins
per interval (re-release semantics). Forecasts: exact-duplicate keys keep the later source
row (deterministic). Both are documented in the loader and tested.

**Q7. What happens when actual generation is missing?** It stays null end-to-end; the point
renders as a gap, is excluded from metrics (valid-pairs require both values finite), and the
coverage panel counts it as a missing actual. Never zero — a fabricated zero would be a
"no wind" claim (see Q8).

**Q8. Why is RMSE much higher than MAE on some days?** RMSE squares errors, so a few large
misses dominate. In Jan-2026 the by-hour panel shows big errors cluster around ramp hours;
the histogram panel shows the tail explicitly. RMSE ≫ MAE is the signature of a few severe
ramp misses rather than uniform error.

**Q9. What exactly does a positive mean bias represent?** `forecast − actual` > 0: the
forecasts systematically over-state generation. January's bias is ≈ +1.8 GW — driven by the
WINDFOR↔FUELHH scope gap (embedded wind included in one view, not the other) plus genuine
over-forecasting; both views are published as-is.

**Q10. How do missing observations affect accuracy?** Metrics use only aligned valid pairs;
the UI shows both the pair count and expected/available/missing counts, so a "good MAE" on
a thin day cannot hide behind a low denominator.

**Q11. What would happen if Elexon changed its API schema?** The loader only touches a small
surface (`fuelType`, `startTime`, `publishTime`, `generation`); the source contract is pinned
against the OpenAPI spec used at build time, and the snapshot keeps raw files + checksums —
a schema change breaks loudly at rebuild (validation errors), not silently.

**Q12. Why is national wind forecast accuracy insufficient for procurement decisions?**
Procurement needs demand, price curves, network constraints and the utility's own portfolio;
national-wind MAE is one input for one risk dimension. A procurement "decision" from this
data alone would be theater — the honest scope is forecast-intelligence.

**Q13. How would you test the system without the live upstream API?** That IS the test
strategy: a synthetic month exercising each edge case plus the checksummed real snapshot;
live mode is exercised separately (build_snapshot, smoke), never assumed.

**Q14. What would you change with another week of development?**
(i) ramp-severity analytics; (ii) a managed user store + database behind auth (the current
JSON store is a demo expedient) with refresh tokens; (iii) cutoff-sweep endpoint; (iv)
CI-deployed preview environments; (v) contract tests generated from the OpenAPI spec.

**Q15. Forecast publication time vs delivery interval time?** Publication: when BMRS
 ingested the vintage (e.g. 09:30Z the day before). Delivery interval: the half-hour the
 value predicts (e.g. [00:00, 00:30) London on the delivery day). The vintage explorer shows
 both, plus the derived lead hours — the number traders call "how far ahead this looked".

**Q16. How does caching behave?** The dataset is loaded once per boot (lifespan singleton)
from an immutable checksummed snapshot; the API layer is stateless per request (auth aside).
On Vercel each function instance rebuilds it from the baked files — deliberate, since cold
loads are dominated by JSON parsing of <6 MB.

**Q17. How do retries work against upstream failures?** Live mode uses bounded HTTP
timeouts + retries with backoff (env-tunable), and failures degrade to explicit
"unavailable" states rather than zeros; the snapshot mode used in production is immune by
construction.

**Q18. Why a JWT (HS256) rather than sessions?** The backend may run in serverless stateless
instances; HS256 with a 24 h TTL requires no shared session store. The signing secret comes
from env (`WINDLENS_JWT_SECRET`); because the store is per-instance on Vercel we documented
that account persistence is a Docker/deployment concern.

**Q19. How is the password store protected?** PBKDF2-HMAC-SHA256, 210k iterations, 16-byte
per-user salt, 32-byte digests, constant-time comparison; failed logins burn comparable
time whether or not the account exists (limits username probing).

**Q20. What does admin-only endpoint gating look like in code?** FastAPI dependencies:
`require_role("admin")` resolves the bearer token, verifies the signature/expiry, then
compares ordered roles; 401 (bad token) vs 403 (insufficient role) are distinct signals.
Endpoints declare their role in the signature, so the RBAC map is visible in routing.

**Q21. Frontend/backend contract?** TypeScript interfaces mirror the Pydantic DTOs verbatim
(one file each, cross-checked); build fails on drift; contract tests assert response shapes.

**Q22. How do you handle CORS?** Deployment is same-origin (rewrites proxy `/api`), so cross-
origin is not required; the middleware whitelist is env-configured, restricted to
GET/POST/DELETE with Authorization/Content-Type headers only.

**Q23. What about CSRF?** All mutating endpoints consume JSON bodies and require the
Authorization header — a classic CSRF-protected posture (no ambient cookies). Login itself
is CSRF-relevant only insofar as minting a token for the attacker's own account, which
gains nothing.

**Q24. Tell me about a failed design choice.** The first auth implementation had a
format-string defect (`$$` in the PBKDF2 encoding) that broke every login — caught by a
roundtrip test before first demo; also the day-1 fetch window (Dec-30 pad) was missed by
synthetic fixtures and only live smoke caught it. Both are pinned by regression tests now.

**Q25. What's the time complexity of selection?** Per interval: O(n) scan of that hour's
candidate list (n ≈ 24) with O(1) tie-max — the day needs 48 scans; a month ~1500 → trivial.
Indexing by hour-end makes it effectively O(candidates per hour), not O(total rows).

**Q26. What is the biggest remaining business risk in this data?** Scope: WINDFOR
over-covers FUELHH by ≈16% in backfills; a customer making a purchase decision on WINDFOR
alone would systematically over-procure. We surface the gap rather than patch it silently —
the next development step (mix-aware reconciliation) is on the roadmap (Q14).

**Q27. Incognito/demo: what does a reviewer see?** Login with the seeded demo account →
dashboard with real January data; all numbers come from the deployed backend (no mocked
data anywhere); the data-mode chip honestly says `snapshot`.
