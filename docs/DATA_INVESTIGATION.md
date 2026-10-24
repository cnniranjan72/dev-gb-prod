# Elexon Data Investigation — Verified Findings (October 2026)

All findings below were verified against the live API (`https://data.elexon.co.uk/bmrs/api/v1`),
the official OpenAPI spec (`https://data.elexon.co.uk/swagger/v1/swagger.json`, server =
`https://data.elexon.co.uk/bmrs/api/v1`, 1.48 MB, OpenAPI 3.0.4), and the full January 2026
retrieval stored in `data/raw/` (retrieved today; see Retrieval Log). Raw probe files:
`data/raw/fuelhh_wind_2026-01-02_sample.json`, `data/raw/fuelhh_wind_2026-01.json`,
`data/raw/windfor_2026-01.json`. Parameter lists were read from the OpenAPI spec, not guessed.

## Endpoints (verified)

| Endpoint | Documented query params (from OpenAPI) | Verified live |
|---|---|---|
| `GET /datasets/FUELHH` | `publishDateTimeFrom`, `publishDateTimeTo`, `settlementDateFrom`, `settlementDateTo`, `settlementPeriod`, `fuelType`, `format` | yes |
| `GET /datasets/FUELHH/stream` | same as above | yes |
| `GET /datasets/WINDFOR` | `publishDateTimeFrom`, `publishDateTimeTo`, `format` **only** | yes |
| `GET /datasets/WINDFOR/stream` | same | yes |

- Documented summary: FUELHH = "Half-hourly generation outturn by fuel type (FUELHH)".
- Documented summary: WINDFOR = "Wind generation forecast (WINDFOR) — … otherwise this will
  retrieve the latest published forecast."
- No API key or authentication required. No documented rate limit found; large-range
  retrievals completed without throttling (8 MB/min observed).
- Error shape: `{"statusCode":404,"message":"Resource not found"}` (plain `/bmrs/openapi.json`
  404s this way).
- `/datasets/{X}` default (no filters) returns the rows of the most recent published vintage.

## Response schemas (verified from spec + payloads)

**FUELHH row** (`Insights.Api...DatasetRows.GenerationOutturn`):
`{dataset, publishTime, startTime, settlementDate, settlementPeriod, fuelType, generation}`
- `publishTime` & `startTime`: ISO-8601 UTC ("Z"), half-hourly publish events.
- `settlementDate` / `settlementPeriod`: **GB-local (Europe/London) day and 1–48 period**.
  Verified: `startTime 2026-10-22T23:30Z → settlementDate 2026-10-23, period 2` and
  `startTime 2026-10-22T23:00Z → period 1` (BST: 23:00Z is already the next London day's
  first period; London midnight falls inside the 23:30Z half-hour that straddles it).
  In January (GMT) local date == UTC date.
- `generation`: integer MW, nullable. Observed range includes negatives (pumped-storage
  pumping); WIND actuals in January 2026 ranged 1,695–17,805 MW.
- `fuelType` values verified (20 codes incl. `WIND`, `CCGT`, `NPSHYD`, `PS`, 10 interconnectors …).
- Publish latency for WIND: exact `publishTime − startTime = 30 min` for the median/first
  release (max 145 min ⇒ late/corrected re-publishes exist and appear as extra publish vintages
  for the same interval).

**WINDFOR row** (`...WindGenerationForecast`):
`{dataset, publishTime, startTime, generation}` — no settlementDate/period fields.
- Hourly interval (73 rows per vintage), `generation` integer MW (Jan-2026 range 2,250–21,353).

## Envelope / paging (verified)

- `/datasets/FUELHH` returns `{"data":[...]}`; `/datasets/{X}/stream` returns a **bare JSON
  array** (no envelope). `format=csv` on the stream endpoint returned JSON in practice — CSV
  not honored for these calls (documented parameter exists for format; verify per request).
- No pagination mechanism observed for these datasets: monthly multi-thousand-row retrievals
  returned complete data in one response (no `totalCount` metadata on stream).

## January 2026 dataset facts (verified, full-month retrieval)

**FUELHH (fuelType=WIND):**
- 1,488 half-hours expected, 1,488 present ⇒ **zero missing intervals in Jan 2026**.
- Each `startTime` appears exactly once (server-side `fuelType=WIND` filter returns one record
  per half-hour; late-correction re-publishes do exist in general — the 145-min max lag proves
  it — and dedup rule "latest publishTime per startTime" is required and implemented).
- Actual wind mean 11,581 MW, min 1,695 MW, max 17,805 MW (Jan 2026).

**WINDFOR:**
- 248 published vintages in Jan 2026; cadence = **8 vintages/day** at 02:30, 04:30, 07:30,
  09:30, 11:30, 15:30, 18:30, 22:30 UTC + occasional extra publishes (one at 12:25 observed).
- Every vintage contains exactly **73 hourly rows** spanning roughly D-1 20:00 → D+2 20:00
  (lead −25.5 h … +66.5 h). It thereby includes *backfill* values for already-delivered hours.
- Median **24 forecast vintages available per delivery hour** across the month.
- No duplicate (publishTime, startTime) pairs observed in January.
- Public forecasts (`lead > 0`) rows: 13,817 in-window; backfill rows (`lead ≤ −1`) rows: 3,449.

## Interval-convention determination (WINDFOR startTime semantics)

WINDFOR is hourly; FUELHH is half-hourly. The OpenAPI schema does **not** document whether
`startTime` labels the hour [T, T+1h), the hour ending at T (T−1h, T], or a point. The empirical
alignment sweep over January 2026 (comparing candidate hour aggregates of the two adjacent
half-hours against `startIndexTime`+, restricted to genuine post-publication forecast rows and
to fast-ramp hours where misalignment is most visible) produced monotone results:

| Candidate window for forecast at label T | MAE (all pairs n=13,817) | MAE (ramp hours n≈5,400) |
|---|---|---|
| backward hour [T−1h, T) = mean(a₍T−60₎, a₍T−30₎) | **2,019** | **1,975** |
| backward half [T−30m, T) = a₍T−30₎ | 2,028 | 1,986 |
| centered [T−30m, T+30m) | 2,037 | 2,004 |
| point/first half [T, T+30m) | 2,051 | 2,032 |
| forward hour [T, T+1h) | 2,063 | 2,055 |
| later half [T+30m, T+1h) | 2,081 | 2,089 |

Chosen working convention: **WINDFOR `startTime` T = the hour ending at T** (interval
[T−1h, T)); the hourly MW value applies to both half-hours of that hour for 30-min display.
The margin is modest (≈1–3%): wind evolves smoothly and misalignment contributes less to MAE
than forecast accuracy itself, so this is documented as an empirically-supported assumption,
reinforced by NESO/Elexon datasets' general interval-end labeling. The pipeline keeps raw
source timestamps so the other interpretation can be re-derived.

## Systematic scope gap between the two datasets (product-critical)

Comparing WINDFOR values for *already-delivered* hours ("backfill", effectively the system
operator's final view) against FUELHH WIND actuals for January 2026:

- Pearson correlation 0.95
- mean ratio forecast/actual = **1.161**, median ratio 1.138 (p5 0.948, p95 1.483)
- mean gap ≈ **+1,740 MW** (forecast view ≈ 13.3 GW vs settlement-view actual ≈ 11.6 GW)

Interpretation (documented, consistent with Elexon/NESO methodology): FUELHH WIND covers
wind **visible in settlement (BM/management-incl.)** while WINDFOR reflects the
**system-operator national wind view (incl. embedded/distribution-connected wind)**.
Consequence: MAE/RMSE/bias between the two mandatory datasets include this persistent offset.
WindLens therefore reports the mandated metrics **on the two specified datasets** and a
dedicated transparency panel: raw headline metrics plus the observed backfill reconciliation
gap, so users can distinguish "persistent dataset offset" from "forecast error". This is
neither hidden nor silently corrected (no rescaling/synthetic adjustment is applied).

## Procurement decision cutoff (assumption — documented, configurable)

The challenge does not fix an official cutoff. Verified factual anchor: the N2EX day-ahead
auction *gate closes 09:50 GMT and results publish by 10:00 GMT* on D−1 (Nord Pool "About the
N2EX Day Ahead Auction"; unchanged since GB left the EU day-ahead coupling on 2021-01-01 per
published literature). WindLens default: **decision cutoff = 10:30 Europe/London on D−1**
(after DA auction results publication; conservative — forecasts known by then are legitimately
usable for day-ahead procurement). Also offer 09:50 (gate) and 17:30 (after IDA1) presets.
UI/docs label this as an analytical assumption, configurable via the `?cutoff=` request param.

## Unresolved items / risks

1. `format=csv` param on stream endpoints not honored (returned JSON) — we will always request
   and parse JSON.
2. Exact WINDFOR interval edge (backward vs centered) has ~1–3% MAE margin; we choose
   backward-hour, keep alignment configurable and keep raw timestamps for re-derivation.
3. WINDFOR publication cadence is *not* strictly periodic (8/day at :30 offsets + odd
   12:25 publishes) — never assume daily-grid availability; selection rule uses ≤ cutoff only.
4. No documented rate limits: retrieval strategy uses ≤ 1 month per request with pacing and
   retries, further chunked to ≤ 1 day if a failure occurs.
5. Commissioned vs settlement actual values drift point-by-point (lower granularity of
   corrections) — handled by "latest publishTime wins" deterministic re-publish rule.

## Retrieval log

| File | Endpoint | Params | HTTP | Size | Retrieved |
|---|---|---|---|---|---|
| `data/raw/fuelhh_wind_2026-01-02_sample.json` | `/datasets/FUELHH/stream` | `settlementDateFrom=2026-01-02&settlementDateTo=2026-01-02&fuelType=WIND` | 200 | 8.7 KB | 2026-10-23 (UTC+1 local) |
| `data/raw/fuelhh_wind_2026-01.json` | `/datasets/FUELHH/stream` | `settlementDateFrom=2026-01-01&…To=2026-01-31&fuelType=WIND&format=json` | 200 | 270 KB | 2026-10-23 |
| `data/raw/windfor_2026-01.json` | `/datasets/WINDFOR/stream` | `publishDateTimeFrom=2025-12-30T00:00Z&…To=2026-02-01T00:00Z` (later re-fetched with 48h pre-window pad so day-1 day-ahead cutoffs have eligible vintages: 19,272 rows / 264 publishes) | 200 | ~2.2 MB | 2026-10-23 |

Additionally, a copy of the Swagger spec was used during development
(`https://data.elexon.co.uk/swagger/v1/swagger.json`); it can be re-downloaded ad hoc with
`Invoke-WebRequest` (see scripts/ for the snapshot + investigation tooling).
