# Verification report

Validated on 30 September 2026 with Python 3.12, Node 24 and PostgreSQL 16.2.

| Check | Result |
| --- | --- |
| Backend suite, PostgreSQL (before final timetable effective-date change) | 35 passed |
| Final backend suite, SQLite | 36 passed |
| Frontend unit suite | 4 passed |
| Chromium end-to-end suite (before final scheduling-only change) | 2 passed |
| Production TypeScript/Vite build | Passed |
| npm dependency audit after patching | 0 known vulnerabilities reported |
| PostgreSQL first two migrations | Passed |
| SQLite full final three-migration chain | Fresh upgrade, schema check, downgrade and re-upgrade passed |
| PostgreSQL final three-migration SQL generation | Passed (offline; final added column not applied to a live PostgreSQL server) |
| Alembic schema comparison | No new upgrade operations detected |
| PostgreSQL downgrade to base and re-upgrade | Passed |
| OCR execution using Tesseract | Passed |
| PDF extraction using pypdf | Passed |
| Desktop and 390px mobile visual inspection | Passed |

The earlier PostgreSQL end-to-end run used the compiled production frontend, a live FastAPI
server, PostgreSQL and the actual background import worker. It exercised signup,
semester and subject setup, timetable generation, daily attendance, analytics,
what-if, forecasts, CSV upload, worker extraction, editable review, reconciliation,
profile updates, notifications and logout. The mobile test exercised navigation,
empty states and horizontal overflow. Test accounts and academic fixtures are
created explicitly by tests; application startup never seeds them.

After resuming, the final scheduling-only change added an effective date to edited
recurring definitions and preserved manual reschedules when slots are edited/deleted.
The final 36-test SQLite suite, full fresh SQLite migration chain, TypeScript/Vite
build and four frontend tests passed. PostgreSQL and browser checks above were
completed before that last backend-only change; they were not repeated afterward.

The backend suite covers:

- Password hashing/authentication, logout, CSRF, cross-origin blocking,
  password-change session revocation, login rate limiting and owner isolation.
- 0/0, 0%, 100%, exact/below target, decimal thresholds, impossible recovery,
  100% recovery after an absence, safe-to-skip and brute-force formula checks.
- Future/ongoing exclusion, pending/excused/cancelled exclusion, atomic bulk
  writes, record editing/clearing and audit entries.
- Duplicate course codes, invalid ranges, timetable overlap, idempotent class
  generation, reschedules, holidays, preservation of marked attendance and
  edits to recurring schedules and academic events.
- Attendance baselines, explicit baseline corrections, protected covered dates,
  reconciliation comparisons and decisions, import confirmation idempotency,
  transactional rollback and conflicts with existing local attendance.
- Calendar/timetable import confirmation, file validation, owner-scoped uploads,
  text PDF extraction, timetable image OCR, conservative parsing and honest
  empty results for unrelated documents.
- Export, notification deduplication and read/unread state.

Screenshots in `screenshots/` show the recreated UI using explicit test fixtures.
The supplied visual references are preserved in `reference-ui/`.

## Verification boundary

Docker was not installed in the execution environment. The individual API,
worker, production frontend, PostgreSQL and migration processes were run and
tested, but the supplied Dockerfiles/Compose stack was not built or launched.
Run `docker compose up --build` on your host to validate container startup and
volume permissions there. The CI workflow is included but was not executed in
a remote GitHub environment during this task.

Production HTTPS, your domain, deployment credentials, backup/restore procedures
and email delivery are environment-specific and have not been provisioned.
Import parsing intentionally requires human review for arbitrary university
formats. Statistical forecasts are not a trained or externally validated ML model.

Starlette's test client emitted a deprecation notice recommending httpx2. The
locked httpx adapter completed all tests; this notice does not affect runtime
API behavior.
