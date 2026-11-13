# Trident latency, concurrency and backend analysis

Date: 14 November 2026 (Pacific/Auckland)

Status: local review only. No GitHub push, frontend deployment, API deployment,
paid service, live data change or production cutover has been performed.

## Executive answer

The website is not slow because React, Vite or the Python business logic is
slow. The live application uses BigQuery as its transactional database, and every
authenticated API request reads the complete application register from one
BigQuery row before doing any useful work.

Measured on 14 November 2026 from the user's machine:

| Check | Result |
|---|---:|
| Cloud Run warm `/api/health` TTFB | about 0.45-0.52 s |
| Cloudflare frontend TTFB | about 0.33 s |
| Authenticated request rejected only after state read | `database_read;dur=1199.8 ms`, total `1213.9 ms` |
| Local API reads (session, schedule, leave, on-call, stock) | about 4-12 ms |

The approximately 1.2 seconds is BigQuery query-job and single-row access
overhead. It is paid even by a request with an invalid token because
authentication currently depends on the register contents.

The best first Google-native move is therefore:

1. Keep React on Cloudflare and Python on Cloud Run.
2. Move the single JSON register from BigQuery to Cloud SQL for PostgreSQL in
   Sydney, preserving the existing application model.
3. Benchmark it as a separate replica before any production cutover.
4. Normalise the operational collections into PostgreSQL tables after the
   low-risk storage swap is accepted.

Spanner, AlloyDB and Firestore are not justified by the current scale and data
model. Supabase remains the documented long-term target, but the user has
paused that migration and it is outside this chat's scope.

## Changes already made locally

| Change | Why it matters | Expected effect |
|---|---|---|
| Removed duplicate register read from direct saves | API already reads state at request entry; `commit()` read it again solely to build the recycle snapshot | Saves about one BigQuery round trip, roughly 0.8-1.2 s, on affected writes |
| Reused the request snapshot for recycle capture and quote-save | The same snapshot can safely describe the pre-write state because the compare-and-swap revision still protects the commit | Fewer reads with unchanged conflict semantics |
| Coalesced simultaneous identical GETs in the browser | A focus event and timer can fire together and request the same data twice | One response instead of duplicate reads; no completed-response cache |
| Reduced session revalidation from 1 minute to 5 minutes, plus visibility checks | Every `/api/session` check reads the full BigQuery register | About 12 checks/hour instead of about 60 per open tab |
| Skip `/api/schedule/routes` after an unchanged schedule response | Routes were fetched immediately after every schedule poll even when bookings had not changed | Avoids one full API/BigQuery request per unchanged minute, while retrying after failures and real changes |
| Fallback schedule poll changed from 10 s to 30 s | The 10 s fallback created six full schedule reads per minute per tab | Up to two thirds fewer fallback polls; live WebSocket notifications still prompt immediate refresh |
| Live WebSocket ticket lifetime changed from 5 min to 30 min | Each reconnect calls an authenticated endpoint that reads the full register | About 2 ticket reads/hour instead of about 12, per active schedule tab |
| CORS preflight cache increased from 10 min to 2 hours | Browser preflight is separate from the actual API request | Fewer preflight round trips; Chrome caps preflight caching at 2 hours |
| Corrected stale API fallback host | A build without `VITE_API_URL` silently used an unhealthy old Cloud Run host | Prevents a total API failure after an environment/build mistake |
| Corrected `FRONTEND_ORIGIN` in `deploy-api.sh` | The script named an obsolete Worker origin; this also disables live schedule tickets when used | Prevents CORS and live-update breakage on a future deployment |

These changes reduce request volume and remove avoidable reads. They do not make
the first BigQuery-backed page read fast; that requires changing the storage
backend.

## Current architecture cost points

- Frontend: React/Vite static assets on Cloudflare. This is already fast and
  geographically appropriate.
- API: Python WSGI on Cloud Run, Sydney, 2 Gunicorn workers x 4 threads,
  512 MiB, minimum instances 0, maximum 2, concurrency 8.
- Database: BigQuery table `trident-dashboard-511019.trident_quotes.app_state`.
- Data shape: one row with `revision` and a complete JSON `state` value.
- Files: Google Cloud Storage bucket `trident-dashboard-511019-quote-pdfs`.
- Live schedule: Cloudflare Durable Object sends invalidation frames only; data
  still comes through the authenticated Python API.

Important consequences:

1. Every authenticated request reads and JSON-decodes the entire register.
2. Every write reads the register, modifies it, and performs a compare-and-swap
   update against one global revision.
3. BigQuery limits concurrent mutating DML on a table to about two statements,
   with an additional queue. This is an analytics system being used for OLTP.
4. Retries reduce user-visible 409s, but cannot remove the queue or query-job
   latency.
5. Production state size is unknown. The local register is about 302 KB, of
   which the workbook is about 287 KB. The local state has previously exceeded
   8 MB in design constraints, so obtain the live size before choosing a
   database tier.

Read-only size check to run later in Cloud Shell, never in this analysis:

```sql
SELECT revision, OCTET_LENGTH(TO_JSON_STRING(state)) AS state_bytes
FROM `trident-dashboard-511019.trident_quotes.app_state`
WHERE id = 'main';
```

## Option comparison

All costs are indicative Google Cloud public list prices in USD, before tax,
discounts and exchange-rate variation. Sydney SKUs can be higher than the
US examples. Confirm in Billing before enabling a paid service.

| Approach | Expected latency | Indicative cost | Complexity | Timeframe | Verdict |
|---|---|---:|---|---|---|
| Local request/read cleanup (applied) | Saves 0.8-1.2 s on affected writes; cuts background reads substantially; first read still slow | $0 | Low | Done locally; 1-2 review days | Do now |
| Cloud Run minimum instance 1 | Removes about 1.4 s cold start; steady reads still about 1.2 s | About $10-15/month for 1 vCPU + 512 MiB kept warm | Low | 1 hour | Optional after storage fix |
| BigQuery `query_and_wait` and client tuning | Possibly 0.1-0.4 s less polling overhead; must be measured | Near zero | Low | 0.5-1 day plus shadow test | Worth a contained experiment |
| BigQuery split rows/collections | Still pays BigQuery query-job overhead; smaller JSON decode | Near zero at current volume | Medium | 4-7 days | Not recommended |
| Cloud SQL PostgreSQL, one JSON row | In-region database work likely 5-30 ms; end-to-end read target 100-250 ms | `db-f1-micro` about $8-12/month; `db-g1-small` about $25-35/month; storage/backups extra | Medium | 3-5 days plus migration/verification | Best first backend move |
| Cloud SQL PostgreSQL, normalised tables | Indexed per-entity reads/writes; removes global JSON conflicts | Similar database compute; modestly more storage/backup | High | 3-5 weeks | Best long-term Google-native design |
| Firestore split documents | Potentially 30-100 ms; strong real-time listeners | Free daily quotas; then about $0.038/100k reads and $0.115/100k writes in Sydney | High | 4-8 weeks | Only if real-time collaboration dominates |
| Cloud Run in-memory/GCS snapshot cache | Variable; invalidation and stale-auth risk | Low | Medium-high | 1-3 weeks | Not recommended for the authoritative register |
| Cloudflare D1 + Workers | Very low edge latency for suitable workloads | Low/free at current scale | Very high; rewrite Python API and data model | 6-10 weeks | Not a business-first move |
| Supabase PostgreSQL, Sydney | Likely good latency and documented long-term target | Free tier may cover current scale; verify limits | High | 4-8 weeks | Paused; separate approved migration chat |
| Cloud Spanner / AlloyDB | Excellent scale and availability, unnecessary here | Materially higher fixed cost | Very high | Months | Not justified |

### BigQuery cost reality

BigQuery on-demand queries include the first 1 TiB of data processed per month,
with a 10 MB minimum per query/table. A 300 KB register therefore bills as at
least 10 MB per read. Even 10,000 reads/day would be about 3 GB/month for the
month, well inside the free allowance. Storage is also below the first 10 GiB
free allowance. BigQuery is currently cheap; its cost is latency and write
concurrency, not the monthly invoice.

## Why Cloud SQL is the first recommendation

The existing code already has a `SQLiteStore` with the same interface as
`BigQueryStore`:

- read revision and complete JSON state;
- write with `WHERE revision = ?` compare-and-swap.

A PostgreSQL implementation can preserve that interface:

- table `app_state(id text primary key, revision bigint, state text)`;
- read `SELECT revision, state FROM app_state WHERE id = 'main'`;
- commit `UPDATE ... SET revision = revision + 1, state = %s WHERE id = 'main' AND revision = %s`;
- use a small pooled connection set in Cloud Run.

Using `text` rather than `jsonb` in the first replica preserves the current
JSON bytes and avoids JSONB reordering/rewrite costs. Normalised tables come
later.

This is a storage swap, not a rewrite of scheduling, quotes, timesheets, stock,
leave, reminders or permissions. It is the lowest-risk way to remove the large
query-job delay.

### Cloud SQL acceptance test

Before cutover, benchmark against a separate Sydney Cloud SQL instance:

1. Sequential reads: 100 samples; record p50 and p95.
2. Concurrent reads: 20 browser-equivalent users for 5 minutes.
3. Concurrent writes: 10 users editing independent collections for 5 minutes.
4. Same-scope conflict: two users editing one appointment; confirm exactly one
   wins and the other receives the existing protected 409 flow.
5. One-uncertain-commit test: prove the operation IDs/receipts prevent duplicate
   leave, my-day and job-import events.
6. Payload test with the live-size register plus backup headroom.
7. Cold start test from zero Cloud Run instances.

Suggested acceptance target: database p95 below 100 ms in Sydney and no
unexplained save errors. Do not promise a fixed end-to-end millisecond target
until the real JSON size and concurrent-write profile are measured.

## Concurrency analysis

The current global CAS is logically correct but operationally fragile:

- unrelated writes increment the same revision;
- BigQuery mutating DML is serialised at about two statements per table;
- a queued DML statement makes the client appear slow and may lead to retries;
- retries can turn a short burst into a longer queue.

`Application.write()` already provides scoped rebase protection for schedule,
stock, stocktake and several related collections. Extending that pattern to
timesheets, drafts, office files, job imports, mail, users and settings is useful,
but it will not remove the BigQuery DML queue. Cloud SQL is the larger win.

For the normalised phase, use one transaction per business command and separate
tables for appointments, time sheets, leave, stock assets, stock movements,
quotes, files, users and audit/recycle records. Use collection-level or row-level
version columns so unrelated saves never conflict.

## Other Google Cloud choices

### Cloud Run minimum instances

This fixes cold starts, not BigQuery. It should not be enabled as a substitute
for the storage fix. A single warm instance is roughly $10-15/month at public
list rates, but it does not make a 1.2 s database read faster.

### Firestore

Firestore is attractive for real-time listeners and per-document changes, but
the current single-register design exceeds a comfortable document shape, and the
workbook plus broad reporting/export logic would need substantial restructuring.
It is a multi-week change with a different consistency and query model. Keep it
as an alternative, not the default.

### Cloud Spanner / AlloyDB

Both solve scale and availability problems this application does not yet have.
They add fixed cost and operational complexity without improving the current
bottleneck enough to justify the move.

### Cloudflare Worker API proxy

A same-origin `/api/*` Worker proxy would remove browser CORS preflight and hide
the direct Cloud Run hostname. It is useful polish, costs little at current
traffic, and is lower risk than a database rewrite. It still forwards to Cloud
Run and therefore does not remove the BigQuery delay. Do it after the storage
decision.

## Recommended sequence

### Phase 1 - local safeguards (complete locally)

- Duplicate-read elimination and request-volume reductions above.
- Tests: 586 backend tests, 93 existing frontend tests plus 2 live-ticket tests,
  targeted ESLint, and production build.
- Review the local preview; do not push until explicitly approved.

### Phase 2 - low-cost experiments

- Measure the actual production register size and BigQuery bytes/query.
- Trial BigQuery `query_and_wait` in a branch; compare p50/p95 against the
  current read.
- Consider Cloud Run minimum instance 1 only after measuring cold-start impact.
- Add a same-origin Worker proxy if browser preflight remains visible in traces.

No paid service should be enabled for these experiments.

### Phase 3 - approved Cloud SQL pilot

- Requires explicit approval because Cloud SQL is a paid service.
- Create a separate Sydney PostgreSQL instance and replica database.
- Keep Google/BigQuery authoritative; do not dual-write production business data.
- Restore/seed only a test replica, benchmark, compare and document rollback.
- Cut over only after a recoverable backup and explicit approval.

### Phase 4 - normalise

- Split the JSON register into typed tables after the storage pilot is stable.
- Add per-record versions, indexes, transaction boundaries and audit history.
- Retain the workbook/PDF object-storage path and all existing business rules.

## Bottom line

- Fastest safe improvement with the current architecture: remove duplicate reads
  and excessive polling; done locally in this branch.
- Best performance per dollar and per engineering hour in Google Cloud: move the
  JSON register to a small Cloud SQL PostgreSQL instance in Sydney first.
- Best long-term correctness and concurrency: normalise Cloud SQL tables after
  the JSON pilot is accepted.
- Do not spend weeks moving to Firestore, Spanner or a Cloudflare rewrite before
  measuring the simpler Cloud SQL option.

## Approval boundary

The local branch is ready for review only. A GitHub push to `main` automatically
triggers frontend and API deployments and is therefore a publishing action. The
user must review the local preview and explicitly approve that release before any
push, deployment or paid Cloud SQL provisioning.
