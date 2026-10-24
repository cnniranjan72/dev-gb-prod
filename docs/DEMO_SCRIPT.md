# DEMO_SCRIPT — WindLens submission video (≤10:00 total)

Two parts as the brief demands:
**Part 1 — Customer pilot overview (≤5:00)** · **Part 2 — Tech-lead walkthrough (≤5:00)**.
Recording: incognito window, 1440p, narration at calm pace, every number on screen is real.

Deliverables page facts to keep visible where relevant:
Deployment https://windlens-flame.vercel.app · Repo https://github.com/cnniranjan72/dev-gb-prod

---

## PART 1 — Customer overview (0:00–4:50)

### 0:00–0:35 — Frame it as the pilot deliverable
- Open the login screen incognito. Say:
  "This is WindLens — the output of the pilot you commissioned. During the pilot we asked:
  when a desk commits day-ahead wind volume at 10:30 the day before delivery, what did the
  market forecasts actually look like at that instant, and how wrong were they across
  January 2026? The whole product answers that one question honestly."
- Sign in with the demo credentials the README documents (`analyst@windlens.demo`).
- Point at the header: data mode `snapshot` (reproducible), actuals/forecast row counts.

### 0:35–1:25 — The dashboard on 2026-01-15 (one day, numbers on screen)
- Stat cards MAE 836.8 MW · RMSE 995.3 · bias +817.7 (over-forecast) · 48/48 valid pairs.
- Say: "'Valid pairs' is the honest denominator — every pair is an actual half-hour and the
  forecast a trader could know at decision time. 48 of 48 intervals this day."
- Main chart: actual line (FUELHH settlement wind) vs dashed cutoff-selected forecast; hover
  one interval — settlement period, MW values, publish time of the selected vintage.

### 1:25–2:20 — The vintage ladder (the differentiator)
- Scroll to the Historical Vintage Explorer, period 1 (interval 00:00–00:30, Jan 15).
- Ladder of 24 publications; selected row flagged; later rows shaded "after cutoff".
- Say: "For the same half-hour, 24 different forecasts existed during the day. A normal
  dashboard shows the LAST one — it didn't exist at decision time, so its accuracy is
  fiction. This screen shows the winner under the rule 'latest publication at or before
  the cutoff' — and the ones that arrived too late, excluded rather than used."

### 2:20–3:00 — Cutoff is a business knob, not a hardcode
- Switch preset to "Auction gate close (09:50 GMT D−1)" — selection updates.
- Then "Custom instant" `2026-01-14T09:50:00Z` — same instant applied transparently.
- Say: "Your desk's decision moment is a setting. The rule recomputes everywhere — the
  month rollups included. Nothing in the analysis is welded to 10:30."

### 3:00–3:50 — The month + the one finding that matters to a buyer
- Daily MAE bars — ramp days punish; error histogram (fixed 500 MW zero-centred bins).
- Month rollup: 1488 pairs · MAE ≈ 2.1 GW · bias ≈ +1.8 GW over-forecast.
- Provenance card: WINDFOR (system-operator view, includes embedded wind) vs FUELHH
  (settlement-visible BM wind) gap ≈ +16% in January backfills.
- Say: "Procurement implication, stated plainly: a volume bought on the forecast view
  alone would lean conservative — the gap is disclosed on every screen, never quietly
  rescaled. This pilot measures the risk; it doesn't yet optimize procurement — demand,
  prices and your portfolio would extend this."

### 3:50–4:50 — What they get + close
- Bullet list verbatim (show README §11 / repo one-liner on screen briefly):
  1. Reproducible dataset (checksummed manifest, offline rebuild), live-retrieval mode.
  2. Every number traceable to a source record — the audit script re-derives the metrics.
  3. Role-gated access, deployable on your cloud or ours (Docker compose shown later).
  4. A day like Jan-15 becomes a defensible narrative: "here is what was knowable, here
     is what it cost."
- Close: "Next 5 minutes is for your technical lead — architecture and evidence."

---

## PART 2 — Tech-lead walkthrough (4:50–9:45)

### 4:50–5:30 — Architecture on one line
- Show repo tree top-to-bottom quickly (frontend/, backend/app/, scripts/, data/, docs/).
- Say: "React+TS SPA in front of a FastAPI backend. One immutable checksummed snapshot
  drives everything: local Docker, CI, and the Vercel deployment — same binary boundary,
  so local and production disagree about nothing. Palette of services: loader → dataset →
  vintage selection → metrics → typed API (Pydantic DTOs mirrored verbatim by the TS client)."

### 5:30–6:45 — The core algorithm + complexity (open vintage.py)
- `backend/app/services/vintage.py` on screen (~120 lines incl. comments).
- `select_forecast`: filter `hour_end == T and publish ≤ cutoff`, then
  `max(eligible, key=(publish_time, row_index))`.
- Complexity: O(candidates per hour) ≈ 24; day = 48 scans; month trivial. Indexed bucket map
  makes it effectively O(1) lookups per hour.
- Boundary semantics: `≤` inclusive — a publication exactly at the cutoff is eligible
  (test-proven). Missing eligible vintage → explicit "unavailable", never substitution.

### 6:45–7:45 — Trust engineering (the strongest 60 seconds)
- Terminal: `python scripts/audit_trace.py` → prints HAND-CALC mae=836.8 rmse=995.3
  bias=817.7 → "TRACE AGREES with service path" (re-parses raw JSON independently).
- Terminal: `pytest backend` → 60 passed (include the auth/RBAC regressions).
- Say: two bug-catch stories —
  1. Day-1 cutoff starvation: real-data smoke tests caught the fetch window missing
     D−1 publications → snapshot extended to Dec-30.
  2. A password-hash format defect (`$$` between fields) silently broke every login —
     caught by a roundtrip regression test the same day.

### 7:45–8:30 — Auth & RBAC (honest scope)
- `security.py` / `users.py`: PBKDF2-HMAC-SHA256 210k + per-user salt, HS256 JWT from env
  secret, role ladder viewer < analyst < admin surfaced as FastAPI dependencies.
- Probe live: anonymous `/api/summary` → 401; viewer token on `/api/vintages` → 403.
- Say: "Application-level auth fits a pilot. A production path would add a managed identity
  provider and persistent user store — disclosed in the README."

### 8:30–9:20 — Deploy + CI (boring on purpose)
- Docker: `docker compose ps` — backend (healthcheck) + nginx frontend on 8085.
- Vercel: one project ships SPA + Python serverless function with the snapshot baked in.
- `.github/workflows/ci.yml`: pytest + frontend build on every push/PR.
- Rates of honesty: env-overridable config; same-origin API via proxy/rewrites.

### 9:20–9:45 — Close
- Say: "Counter-balance: hour-ending alignment was resolved empirically (MAE sweep, margin
  ~3%) — the raw labels are retained so a reviewer can re-derive the alternative reading.
  Roadmap if funded: ramp-severity analytics, cutoff-sensitivity surface, managed identity.
  Everything submitted is evidenced in the repo: docs/PRE_SUBMISSION_AUDIT.md and
  docs/FINAL_READINESS_REPORT.md."

---

## Recording checklist

- [ ] Incognito (no stale token) · zoom 100% · terminal font ≥14 pt
- [ ] Login screen visible in Part 1 opening; demo creds autofill via UI hint buttons
- [ ] 2026-01-15 fully loaded BEFORE narration starts
- [ ] Commands pre-run once so outputs are proven before recording:
      pytest (60 pass), audit_trace (AGREES), docker compose ps
- [ ] Preset switch and custom cutoff demonstrated in Part 1 only
- [ ] Hard edits at 5:00 boundary; total ≤10:00
- [ ] End frame: deployment URL + repo URL + "AI-assisted, disclosed in README §9"
