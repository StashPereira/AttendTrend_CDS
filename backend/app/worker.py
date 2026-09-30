"""Durable DB-backed processing queue. Run python -m app.worker beside the API."""

import logging
import subprocess
import sys
import time
import json
from datetime import timedelta
from sqlalchemy import select
from .db import SessionLocal
from .models import Document, Profile, Semester, Subject, utcnow
from .services.notifications import refresh, notify

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("attendtrend.worker")


def process_one():
    with SessionLocal() as db:
        # Single lock transaction claims one job. PostgreSQL supports concurrent workers.
        job = db.scalar(
            select(Document)
            .where(Document.status == "queued")
            .order_by(Document.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        job.status = "processing"
        job.updated_at = utcnow()
        job_id, path, kind = job.id, job.path, job.kind
        db.commit()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.extract_job", path, kind],
            capture_output=True,
            timeout=240,
            check=True,
        )
        preview = json.loads(result.stdout)
        error = ""
    except Exception as exc:
        log.warning("Processing failed for job %s (%s)", job_id, type(exc).__name__)
        preview, error = (
            {},
            "Extraction failed or exceeded four minutes. Try a smaller file or upload CSV.",
        )
    with SessionLocal() as db:
        job = db.get(Document, job_id)
        if job and job.status == "processing":
            if job.kind == 'timetable' and not error:
                subjects = db.scalars(select(Subject).where(Subject.user_id == job.user_id, Subject.semester_id == job.semester_id)).all()
                for row in preview.get('rows', []):
                    if not row.get('code'):
                        matches = [subject for subject in subjects if ' '.join(subject.name.upper().split()) == ' '.join(row.get('name', '').upper().split())]
                        if len(matches) == 1: row['code'] = matches[0].code
                preview.setdefault('warnings', []).append('Subject matching uses exact names only. Select the existing course code where a name differs or theory/practical assignment is unclear.')
            job.preview = preview
            job.error = error
            job.status = "failed" if error else "review"
            job.updated_at = utcnow()
            profile = db.get(Profile, job.user_id)
            if profile.notify_imports:
                notify(
                    db,
                    job.user_id,
                    f"import:{job.id}:{job.status}",
                    "import",
                    f"{job.name}: {job.status}. {error}",
                )
            db.commit()
    return True


def maintain():
    with SessionLocal() as db:
        for job in db.scalars(
            select(Document).where(
                Document.status == "processing",
                Document.updated_at < utcnow() - timedelta(minutes=10),
            )
        ):
            job.status = "queued"
            job.updated_at = utcnow()
        for semester in db.scalars(select(Semester)):
            refresh(db, semester.user_id, semester.id)
        db.commit()


def main():
    last_maintenance = 0
    while True:
        try:
            if time.monotonic() - last_maintenance > 60:
                maintain()
                last_maintenance = time.monotonic()
            if not process_one():
                time.sleep(2)
        except Exception:
            log.exception("Worker iteration failed")
            time.sleep(5)


if __name__ == "__main__":
    main()
