# AttendTrend

Full-stack attendance tracking with React, FastAPI, SQLAlchemy and PostgreSQL.
The frontend was recreated from the 13 supplied screenshots: blue navigation,
pale workspace, rounded cards, attendance charts, tables and existing page hierarchy.
No original React source was present in the input archive.

## Start with Docker (recommended, including on Windows)

Install Docker Desktop with Compose v2 and Python 3.12+. From this folder:

```sh
python scripts/configure.py
docker compose up --build
```

Open **http://localhost:8080**. Create your own account. There are no bundled
accounts, credentials, seeded students or fabricated attendance records.

The configuration script generates a private local database password. Keep the
generated `.env`. PostgreSQL data and original uploads persist in named volumes.
The migration service runs before the API and worker start.

## Local development without Docker

Requires Python 3.12+, Node 22.12+ (or Node 24), Tesseract OCR and Poppler
(`pdftoppm`). On Ubuntu, install `tesseract-ocr poppler-utils fonts-dejavu-core`.
On macOS use Homebrew's `tesseract` and `poppler`. On Windows install those
executables and add them to PATH, or use Docker/WSL.

```sh
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
pip install -r backend/requirements-dev.txt -c backend/requirements-lock.txt
cd frontend
npm ci
cd ..
python scripts/dev.py
```

Open **http://localhost:5173**. The launcher migrates the database and starts
the API, import worker and frontend. Ctrl+C stops them. Development defaults to
SQLite so it needs no separate database installation. To use PostgreSQL,
set `DATABASE_URL=postgresql+psycopg://...` before launching. Production rejects
SQLite. Run commands from their documented directories; database/upload paths
are relative to the backend working directory.

## First-use workflow

1. Create an account and complete **Profile & Settings**, including timezone,
   attendance target, student details and notification preferences.
2. Create a semester with its academic dates using the `+` next to the term selector.
3. Open **Data & Reconciliation → Subjects** to add courses, codes, instructors
   and theory/practical types, or let reviewed imports create courses.
4. Open **Academic setup** and upload attendance, academic calendar and timetable
   documents. The worker extracts text/OCR and queues a review notification.
5. Review and correct every extracted row; add missing rows. Confirm the import.
   Initial baselines are accepted only where there are no covered local records.
   Choose reconciliation for subsequent university reports.
   Confirmed baseline counts can be corrected explicitly in the baseline table;
   corrections are audited and rejected if they would cover local records.
6. Use **Calendar & Timetable** to add or edit weekly slots, events, holidays,
   additional classes and rescheduled occurrences. Weekly slots automatically
   generate class occurrences within the semester. Editing a recurring slot updates
   future classes and preserves historical records and manual reschedules.
7. In **Attendance**, select a date, mark completed classes and save the batch.
   All dependent views refetch automatically. Clear a record to return it to pending.

All routes check the signed-in user's ownership. Sessions use an HttpOnly cookie,
server-side revocation, Argon2 password hashing and a CSRF token on mutations.
Changing a password revokes all other sessions. Timezone is fixed after classes
exist because stored class times are local wall times.

## Documents and imports

Supported: PDF (including scanned pages via OCR), PNG/JPEG images, UTF-8 CSV/TXT.
Limit: 10 MB, 60 PDF pages or 20 megapixels per image. Extraction runs outside
the API process with a four-minute deadline and a memory ceiling on Linux.

CSV is the most reliable interchange format. See the three files in `docs/`.
They are illustrative fixtures, never automatically imported. Adjust dates/counts
to your actual semester. A timetable weekday can be 0–6 (Monday–Sunday) or an
English weekday name in CSV. Attendance rows require actual present/conducted
counts and an explicit `through_date`; percentage-only reports cannot determine
class counts safely. Course codes are normalized to uppercase. Exact names are
checked for conflicting codes; ambiguous subjects require review rather than
automatic fuzzy merging.

Text/OCR parsing recognizes these conservative line formats:

```text
M101 Mathematics 8 / 10 2020-01-31
M101 Mathematics Monday 09:00 - 10:00 Room1
2020-01-26 holiday Republic Day
2020-03-01 - 2020-03-05 exam Midterms
```

Arbitrary university layouts are not guaranteed to parse automatically. Unrecognized
documents produce an empty editable review and the extracted text, never fabricated
rows. Review every OCR result. Confirming is transactional: a validation conflict
saves none of the rows. Reconfirmation and silent baseline replacement are rejected.
Deleting an uploaded document keeps its already-confirmed academic data.

## Attendance, recovery and forecasting

One engine in `backend/app/services/attendance.py` powers every screen.

- **Attendance:** present ÷ (present + absent), using completed classes only.
  Excused, cancelled and pending classes are excluded. No observations display `—`.
- **Imported baseline:** aggregate counts through its date, plus local records
  after that date. Covered dates are protected from local edits to avoid double counting.
- **Recovery:** minimum consecutive present classes to reach the target, required
  present classes within the remaining schedule, and feasibility. A 100% target
  cannot be recovered after an absence. Decimal arithmetic protects threshold edges.
- **Safe to skip now:** absences allowed without relying on future present classes,
  capped by actual remaining classes. Final allowable absences assume the remaining
  non-absent classes are all present. These are different quantities.
- **What-if:** user-selected attend/miss counts within scheduled remaining classes.
  The scenario changes no attendance records.
- **Forecast:** Beta(1,1)-smoothed attendance rate `(present + 1)/(conducted + 2)`
  applied to future scheduled classes. Fewer than ten observations are labelled
  limited history; zero observations have no point estimate. Best/worst values
  are deterministic bounds, not confidence intervals. No trained ML model is claimed.
- **Risk:** unknown without observations; critical when best-case recovery is
  impossible; otherwise high when forecast is below the configured warning
  threshold, medium within the safety buffer and low above it. Cautious sensitivity
  adds the buffer to the forecast warning threshold; relaxed subtracts it.
- **Reconciliation:** compare official and local counts at the same through-date,
  with percentage-point differences and recorded review decisions. Local data stays
  intact. An official snapshot earlier than a local aggregate baseline cannot be
  reconstructed and is labelled for review.

Aggregate imports cannot reconstruct daily or weekday attendance. Trend charts
include the baseline at its through-date, while weekday statistics use only dated
local records. Unmarked past classes are surfaced as pending and can change results
when marked. Missing future timetable entries limit forecasts and recovery estimates.

## API and structure

Interactive API docs: **http://localhost:8000/docs** during local development.
Under Docker, `/api` is proxied on port 8080 and the database/API ports are private.

```text
backend/app/models.py             relational data and constraints
backend/app/security.py           session authentication, CSRF and login throttling
backend/app/main.py               REST endpoints, ownership checks and transactions
backend/app/services/attendance.py shared calculations and statistical forecasting
backend/app/services/scheduling.py recurrence, holidays and occurrence generation
backend/app/services/documents.py  file validation, extraction, OCR and parsing
backend/app/worker.py             durable DB queue and notification scheduling
backend/alembic/                   versioned PostgreSQL/SQLite migrations
frontend/src/                     recreated UI, API client and query caching
frontend/tests/                   unit and browser flows
docs/                             import samples and verification report
```

REST resources: `/api/auth/*`, `/api/profile`, `/api/semesters`, `/api/subjects`,
`/api/timetable`, `/api/events`, `/api/classes`, `/api/attendance`, `/api/summary`,
`/api/what-if`, `/api/documents`, `/api/reconciliation`, `/api/notifications`,
`/api/export`. Use `/api/auth/me` to obtain the session's CSRF token, then send
`X-CSRF-Token` on non-read requests. User IDs are never accepted for ownership.

The database queue survives worker restarts; stale processing jobs are requeued.
Notification keys are deduplicated atomically. PostgreSQL worker claims use
`FOR UPDATE SKIP LOCKED`. Use a single worker with development SQLite.
Notifications are an in-app feed and scheduled upcoming-class alerts; there is
no external email/SMS delivery provider configured.

## Tests

```sh
cd backend
pytest -q
# Optional dedicated disposable PostgreSQL test database:
# TEST_DATABASE_URL=postgresql+psycopg://.../attendtrend_test pytest -q
cd ../frontend
npm test
npm run build
npx playwright install chromium
# Start API/worker/frontend first using scripts/dev.py, in another terminal.
npm run test:e2e
```

Tests recreate all application tables in the test database. Default test runs use
a temporary SQLite file, ignoring the application DATABASE_URL. Only explicitly
set TEST_DATABASE_URL to a disposable test database. A GitHub Actions workflow
validates PostgreSQL, fresh migrations, the frontend build and browser flows.
The dependency lock files make installs reproducible.

## Production deployment

Use PostgreSQL and serve the web container behind an HTTPS reverse proxy. Set
`ENVIRONMENT=production`, `COOKIE_SECURE=true`, and `ALLOWED_ORIGINS` to the exact
HTTPS origin (comma-separated only when multiple origins are needed). The API
refuses production mode without PostgreSQL and secure cookies. Database credentials
must be supplied by environment/secret management; none are packaged. PostgreSQL
and the API are internal Compose services; expose only the frontend/reverse proxy.

Before a release, run migrations and tests against your target PostgreSQL version,
back up the database and uploads together, verify restore procedures, and configure
TLS, monitoring and retention for your deployment. Change .env only for your own
installation; do not commit it. Original uploads may contain personal academic data.
The app has account/password management but no email verification or password-reset
mailer; adding those requires your verified email provider and delivery configuration.
See `docs/VERIFICATION.md` for checks actually executed and the Docker verification boundary.
