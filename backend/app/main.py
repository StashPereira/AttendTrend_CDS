import csv
import io
import logging
import secrets
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Literal
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select, delete, text
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import get_db
from .models import (
    User,
    Profile,
    Semester,
    Subject,
    Instructor,
    Timetable,
    CalendarEvent,
    Occurrence,
    Attendance,
    AuthSession,
    Document,
    Baseline,
    Reconciliation,
    Notification,
    Audit,
    utcnow,
)
from .schemas import (
    Signup,
    Credentials,
    ProfileInput,
    PasswordChange,
    SemesterInput,
    SubjectInput,
    TimetableInput,
    EventInput,
    OccurrenceInput,
    Marks,
    Scenario,
    ImportConfirm,
    AttendanceImportRow,
    TimetableImportRow,
    CalendarImportRow,
    Resolve,
)
from .security import (
    current_user,
    issue_session,
    verify_password,
    hasher,
    dummy_hash,
    throttle,
)
from .services.attendance import summary, subject_stats, scenario, percentage, local_now
from .services.scheduling import regenerate, validate_overlap, delete_timetable
from .services.documents import validate_bytes
from .services.notifications import refresh, notify

app = FastAPI(title="AttendTrend API", version="1.0.0")
origins = [s.strip() for s in settings().allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(IntegrityError)
async def constraint_error(request, exc):
    return JSONResponse(
        {
            "detail": "This change conflicts with existing data. Check duplicate codes, names or times."
        },
        status_code=409,
    )


def serialize(obj):
    return jsonable_encoder(
        {col.name: getattr(obj, col.name) for col in obj.__table__.columns}
    )


def owned(db, model, item_id, user):
    obj = db.scalar(select(model).where(model.id == item_id, model.user_id == user.id))
    if not obj:
        raise HTTPException(404, "Record not found")
    return obj


def audit(db, user_id, action, payload):
    db.add(Audit(user_id=user_id, action=action, payload=jsonable_encoder(payload)))


def instructor_id(db, user_id, name):
    if not name:
        return None
    item = db.scalar(
        select(Instructor).where(Instructor.user_id == user_id, Instructor.name == name)
    )
    if not item:
        item = Instructor(user_id=user_id, name=name)
        db.add(item)
        db.flush()
    return item.id


@app.get("/api/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/auth/signup", status_code=201)
def signup(body: Signup, request: Request, response: Response, db=Depends(get_db)):
    email = str(body.email).lower()
    throttle(db, request, email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(email=email, name=body.name, password_hash=hasher.hash(body.password))
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id))
    db.commit()
    return issue_session(db, response, user)


@app.post("/api/auth/login")
def login(body: Credentials, request: Request, response: Response, db=Depends(get_db)):
    email = str(body.email).lower()
    throttle(db, request, email)
    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(user.password_hash if user else dummy_hash, body.password)
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    return issue_session(db, response, user)


@app.get("/api/auth/me")
def me(request: Request, user=Depends(current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "csrf": request.state.auth_session.csrf,
    }


@app.post("/api/auth/logout")
def logout(
    request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)
):
    db.delete(request.state.auth_session)
    db.commit()
    response.delete_cookie("attendtrend_session", path="/api")
    return {"ok": True}


@app.post("/api/auth/password")
def change_password(
    body: PasswordChange,
    response: Response,
    user=Depends(current_user),
    db=Depends(get_db),
):
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(403, "Current password is incorrect")
    user.password_hash = hasher.hash(body.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    audit(db, user.id, "password_changed", {})
    db.commit()
    return issue_session(db, response, user)


@app.get("/api/profile")
def profile(user=Depends(current_user), db=Depends(get_db)):
    return serialize(db.get(Profile, user.id)) | {
        "name": user.name,
        "email": user.email,
    }


@app.put("/api/profile")
def update_profile(body: ProfileInput, user=Depends(current_user), db=Depends(get_db)):
    record = db.get(Profile, user.id)
    if record.timezone != body.timezone and db.scalar(
        select(Occurrence.id).where(Occurrence.user_id == user.id).limit(1)
    ):
        raise HTTPException(
            409,
            "Timezone cannot change after classes exist. Class times are local wall times.",
        )
    user.name = body.name
    for key, value in body.model_dump(exclude={"name"}).items():
        setattr(record, key, value)
    db.commit()
    return serialize(record) | {"name": user.name, "email": user.email}


@app.get("/api/semesters")
def semesters(user=Depends(current_user), db=Depends(get_db)):
    return [
        serialize(row)
        for row in db.scalars(
            select(Semester)
            .where(Semester.user_id == user.id)
            .order_by(Semester.start_date.desc())
        )
    ]


@app.post("/api/semesters", status_code=201)
def create_semester(
    body: SemesterInput, user=Depends(current_user), db=Depends(get_db)
):
    item = Semester(user_id=user.id, **body.model_dump())
    db.add(item)
    db.commit()
    return serialize(item)


@app.delete("/api/semesters/{item_id}")
def remove_semester(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    item = owned(db, Semester, item_id, user)
    # Destructive dataset operation is explicit in UI and audited.
    audit(db, user.id, "semester_deleted", {"id": item.id, "name": item.name})
    paths = list(
        db.scalars(select(Document.path).where(Document.semester_id == item.id))
    )
    db.delete(item)
    db.commit()
    for path in paths:
        Path(path).unlink(missing_ok=True)
    return {"ok": True}


@app.put("/api/semesters/{item_id}")
def edit_semester(
    item_id: int, body: SemesterInput, user=Depends(current_user), db=Depends(get_db)
):
    row = owned(db, Semester, item_id, user)
    ids = select(Subject.id).where(Subject.semester_id == row.id)
    out_of_range = db.scalar(
        select(Occurrence.id).where(
            Occurrence.subject_id.in_(ids),
            (Occurrence.starts_at < datetime.combine(body.start_date, time.min))
            | (
                Occurrence.ends_at
                >= datetime.combine(body.end_date + timedelta(days=1), time.min)
            ),
        )
    )
    if out_of_range:
        raise HTTPException(
            409,
            "Existing classes are outside the requested dates. Reschedule or remove them first.",
        )
    for event in db.scalars(
        select(CalendarEvent).where(CalendarEvent.semester_id == row.id)
    ):
        if event.start_date < body.start_date or event.end_date > body.end_date:
            raise HTTPException(
                409, "An academic event is outside the requested semester dates"
            )
    for baseline in db.scalars(select(Baseline).where(Baseline.subject_id.in_(ids))):
        if not body.start_date <= baseline.through_date <= body.end_date:
            raise HTTPException(
                409, "Imported baseline date must stay within the semester"
            )
    audit(
        db,
        user.id,
        "semester_changed",
        {"before": serialize(row), "after": body.model_dump()},
    )
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.flush()
    regenerate(db, user.id, row.id)
    db.commit()
    return serialize(row)


@app.get("/api/subjects")
def subjects(semester_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, semester_id, user)
    rows = db.scalars(
        select(Subject)
        .where(Subject.user_id == user.id, Subject.semester_id == semester_id)
        .order_by(Subject.name)
    ).all()
    return [
        serialize(row)
        | {
            "instructor": (
                db.get(Instructor, row.instructor_id).name if row.instructor_id else ""
            )
        }
        for row in rows
    ]


@app.post("/api/subjects", status_code=201)
def create_subject(body: SubjectInput, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, body.semester_id, user)
    row = Subject(
        user_id=user.id,
        instructor_id=instructor_id(db, user.id, body.instructor),
        **body.model_dump(exclude={"instructor"}),
    )
    db.add(row)
    db.commit()
    return serialize(row)


@app.put("/api/subjects/{item_id}")
def update_subject(
    item_id: int, body: SubjectInput, user=Depends(current_user), db=Depends(get_db)
):
    row = owned(db, Subject, item_id, user)
    if row.semester_id != body.semester_id:
        raise HTTPException(409, "A subject cannot be moved between semesters")
    for key, value in body.model_dump(exclude={"instructor"}).items():
        setattr(row, key, value)
    row.instructor_id = instructor_id(db, user.id, body.instructor)
    db.commit()
    return serialize(row)


@app.delete("/api/subjects/{item_id}")
def remove_subject(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, Subject, item_id, user)
    audit(db, user.id, "subject_deleted", serialize(row))
    db.delete(row)
    db.commit()
    return {"ok": True}


@app.get("/api/timetable")
def timetable(semester_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, semester_id, user)
    ids = select(Subject.id).where(
        Subject.semester_id == semester_id, Subject.user_id == user.id
    )
    return [
        serialize(row)
        for row in db.scalars(
            select(Timetable)
            .where(Timetable.subject_id.in_(ids))
            .order_by(Timetable.weekday, Timetable.start_time)
        )
    ]


@app.post("/api/timetable", status_code=201)
def add_timetable(body: TimetableInput, user=Depends(current_user), db=Depends(get_db)):
    subject = owned(db, Subject, body.subject_id, user)
    validate_overlap(db, user.id, subject, body.weekday, body.start_time, body.end_time)
    row = Timetable(user_id=user.id, **body.model_dump())
    db.add(row)
    db.flush()
    regenerate(db, user.id, subject.semester_id)
    db.commit()
    return serialize(row)


@app.delete("/api/timetable/{item_id}")
def remove_timetable(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, Timetable, item_id, user)
    delete_timetable(db, row)
    db.commit()
    return {"ok": True}


@app.put("/api/timetable/{item_id}")
def edit_timetable(
    item_id: int, body: TimetableInput, user=Depends(current_user), db=Depends(get_db)
):
    row = owned(db, Timetable, item_id, user)
    subject = owned(db, Subject, body.subject_id, user)
    if subject.id != row.subject_id:
        raise HTTPException(409, "Cannot change the subject of an existing slot")
    validate_overlap(
        db, user.id, subject, body.weekday, body.start_time, body.end_time, item_id
    )
    now = local_now(db.get(Profile, user.id))
    marked = set(
        db.scalars(
            select(Attendance.occurrence_id).where(Attendance.user_id == user.id)
        )
    )
    same_slot = row.weekday == body.weekday and row.start_time == body.start_time
    for occ in db.scalars(select(Occurrence).where(Occurrence.timetable_id == row.id)):
        if (
            occ.ends_at > now
            and occ.id not in marked
            and not occ.source_start
            and occ.cancellation_reason != "manual"
        ):
            db.delete(occ)
        elif not (
            occ.ends_at > now
            and same_slot
            and (occ.source_start or occ.cancellation_reason == 'manual')
        ):
            occ.timetable_id = None
    db.flush()
    audit(
        db,
        user.id,
        "timetable_changed",
        {"before": serialize(row), "after": body.model_dump()},
    )
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.effective_from = now
    db.flush()
    regenerate(db, user.id, subject.semester_id, after=now, entry_id=row.id)
    db.commit()
    return serialize(row)


@app.post("/api/semesters/{item_id}/generate")
def generate(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, item_id, user)
    count = regenerate(db, user.id, item_id)
    db.commit()
    return {"created": count}


@app.get("/api/events")
def events(semester_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, semester_id, user)
    return [
        serialize(row)
        for row in db.scalars(
            select(CalendarEvent)
            .where(
                CalendarEvent.user_id == user.id,
                CalendarEvent.semester_id == semester_id,
            )
            .order_by(CalendarEvent.start_date)
        )
    ]


@app.post("/api/events", status_code=201)
def add_event(body: EventInput, user=Depends(current_user), db=Depends(get_db)):
    semester = owned(db, Semester, body.semester_id, user)
    if not semester.start_date <= body.start_date <= body.end_date <= semester.end_date:
        raise HTTPException(422, "Event must be within semester dates")
    row = CalendarEvent(user_id=user.id, **body.model_dump())
    db.add(row)
    db.flush()
    regenerate(db, user.id, semester.id)
    db.commit()
    return serialize(row)


@app.delete("/api/events/{item_id}")
def remove_event(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, CalendarEvent, item_id, user)
    semester_id = row.semester_id
    db.delete(row)
    db.flush()
    regenerate(db, user.id, semester_id)
    db.commit()
    return {"ok": True}


@app.put("/api/events/{item_id}")
def edit_event(
    item_id: int, body: EventInput, user=Depends(current_user), db=Depends(get_db)
):
    row = owned(db, CalendarEvent, item_id, user)
    semester = owned(db, Semester, body.semester_id, user)
    if (
        row.semester_id != semester.id
        or not semester.start_date
        <= body.start_date
        <= body.end_date
        <= semester.end_date
    ):
        raise HTTPException(422, "Keep the event within its original semester")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.flush()
    regenerate(db, user.id, semester.id)
    db.commit()
    return serialize(row)


@app.get("/api/classes")
def classes(
    semester_id: int,
    start: date | None = None,
    end: date | None = None,
    user=Depends(current_user),
    db=Depends(get_db),
):
    owned(db, Semester, semester_id, user)
    ids = select(Subject.id).where(
        Subject.user_id == user.id, Subject.semester_id == semester_id
    )
    query = (
        select(Occurrence, Attendance.status, Subject.name, Subject.code)
        .join(Subject)
        .outerjoin(Attendance, Attendance.occurrence_id == Occurrence.id)
        .where(Occurrence.user_id == user.id, Occurrence.subject_id.in_(ids))
    )
    if start:
        query = query.where(Occurrence.starts_at >= datetime.combine(start, time.min))
    if end:
        query = query.where(
            Occurrence.starts_at < datetime.combine(end + timedelta(days=1), time.min)
        )
    now = local_now(db.get(Profile, user.id))
    return [
        serialize(o)
        | {
            "status": "cancelled" if o.cancelled else status or "pending",
            "subject": name,
            "code": code,
            "future": o.ends_at > now,
        }
        for o, status, name, code in db.execute(
            query.order_by(Occurrence.starts_at).limit(20000)
        )
    ]


def validate_occurrence(db, user, body, exclude=None):
    subject = owned(db, Subject, body.subject_id, user)
    semester = db.get(Semester, subject.semester_id)
    if (
        not semester.start_date
        <= body.starts_at.date()
        <= body.ends_at.date()
        <= semester.end_date
    ):
        raise HTTPException(422, "Class must be within semester dates")
    ids = select(Subject.id).where(
        Subject.user_id == user.id, Subject.semester_id == semester.id
    )
    query = select(Occurrence.id).where(
        Occurrence.subject_id.in_(ids),
        Occurrence.cancelled == False,
        Occurrence.starts_at < body.ends_at,
        Occurrence.ends_at > body.starts_at,
    )
    if exclude:
        query = query.where(Occurrence.id != exclude)
    if not body.cancelled and db.scalar(query):
        raise HTTPException(409, "Class overlaps another scheduled class")
    return subject


@app.post("/api/classes", status_code=201)
def add_class(body: OccurrenceInput, user=Depends(current_user), db=Depends(get_db)):
    validate_occurrence(db, user, body)
    row = Occurrence(
        user_id=user.id,
        cancellation_reason="manual" if body.cancelled else "",
        **body.model_dump(),
    )
    db.add(row)
    db.commit()
    return serialize(row)


@app.put("/api/classes/{item_id}")
def edit_class(
    item_id: int, body: OccurrenceInput, user=Depends(current_user), db=Depends(get_db)
):
    row = owned(db, Occurrence, item_id, user)
    if row.subject_id != body.subject_id:
        raise HTTPException(409, "Cannot change subject of an existing class")
    validate_occurrence(db, user, body, item_id)
    record = db.scalar(
        select(Attendance).where(
            Attendance.occurrence_id == item_id,
            Attendance.status.in_(["present", "absent", "excused"]),
        )
    )
    now = local_now(db.get(Profile, user.id))
    if record and body.ends_at > now:
        raise HTTPException(
            409, "Clear attendance before rescheduling a marked class into the future"
        )
    audit(
        db,
        user.id,
        "class_changed",
        {"before": serialize(row), "after": body.model_dump()},
    )
    if row.starts_at != body.starts_at and row.timetable_id and not row.source_start:
        row.source_start = row.starts_at
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    # Keep the original recurring-slot link so generation cannot recreate a moved class.
    row.cancellation_reason = "manual" if row.cancelled else ""
    db.commit()
    return serialize(row)


@app.delete("/api/classes/{item_id}")
def delete_class(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, Occurrence, item_id, user)
    audit(db, user.id, "class_deleted", serialize(row))
    if row.timetable_id:
        row.cancelled = True
        row.cancellation_reason = "manual"
        db.execute(delete(Attendance).where(Attendance.occurrence_id == row.id))
    else:
        db.delete(row)
    db.commit()
    return {"ok": True}


@app.put("/api/attendance")
def mark(body: Marks, user=Depends(current_user), db=Depends(get_db)):
    if len({r.occurrence_id for r in body.records}) != len(body.records):
        raise HTTPException(422, "Duplicate class in batch")
    now = local_now(db.get(Profile, user.id))
    for item in body.records:
        row = owned(db, Occurrence, item.occurrence_id, user)
        baseline = db.scalar(
            select(Baseline).where(Baseline.subject_id == row.subject_id)
        )
        if baseline and row.starts_at.date() <= baseline.through_date:
            raise HTTPException(
                409,
                "This date is covered by an imported baseline; review reconciliation instead",
            )
        if row.ends_at > now and item.status not in ("cancelled", "pending"):
            raise HTTPException(
                422,
                "Future or ongoing classes cannot be marked present, absent or excused",
            )
        old = db.scalar(select(Attendance).where(Attendance.occurrence_id == row.id))
        audit(
            db,
            user.id,
            "attendance_changed",
            {
                "occurrence_id": row.id,
                "before": old.status if old else None,
                "after": item.status,
            },
        )
        row.cancelled = item.status == "cancelled"
        row.cancellation_reason = "manual" if row.cancelled else ""
        if row.cancelled or item.status == "pending":
            if old:
                db.delete(old)
        elif old:
            old.status = item.status
            old.updated_at = utcnow()
        else:
            db.add(
                Attendance(user_id=user.id, occurrence_id=row.id, status=item.status)
            )
    db.commit()
    return {"saved": len(body.records)}


@app.delete("/api/attendance/{item_id}")
def clear_attendance(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, Occurrence, item_id, user)
    baseline = db.scalar(select(Baseline).where(Baseline.subject_id == row.subject_id))
    if baseline and row.starts_at.date() <= baseline.through_date:
        raise HTTPException(409, "Date is covered by an imported baseline")
    db.execute(delete(Attendance).where(Attendance.occurrence_id == row.id))
    row.cancelled = False
    row.cancellation_reason = ""
    audit(db, user.id, "attendance_cleared", {"occurrence_id": item_id})
    db.commit()
    return {"ok": True}


@app.get("/api/summary")
def get_summary(semester_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, semester_id, user)
    return summary(db, user.id, semester_id)


@app.post("/api/what-if")
def what_if(body: Scenario, user=Depends(current_user), db=Depends(get_db)):
    subject = owned(db, Subject, body.subject_id, user)
    profile = db.get(Profile, user.id)
    s = subject_stats(db, subject, profile)
    if body.attend + body.miss > s["recovery"]["remaining"]:
        raise HTTPException(422, "Scenario exceeds the scheduled remaining classes")
    return scenario(
        s["attended"],
        s["conducted"],
        body.attend,
        body.miss,
        body.target or profile.target,
    )


@app.post("/api/documents", status_code=201)
async def upload(
    semester_id: int = Form(...),
    kind: Literal["attendance", "calendar", "timetable"] = Form(...),
    file: UploadFile = File(...),
    user=Depends(current_user),
    db=Depends(get_db),
):
    owned(db, Semester, semester_id, user)
    active = db.scalars(
        select(Document.id).where(
            Document.user_id == user.id,
            Document.status.in_(["queued", "processing", "review"]),
        )
    ).all()
    if len(active) >= 20:
        raise HTTPException(
            429, "Finish or delete pending imports before uploading more"
        )
    content = await file.read(settings().max_upload_bytes + 1)
    try:
        suffix = validate_bytes(
            file.filename or "", content, settings().max_upload_bytes
        )
    except Exception as exc:
        raise HTTPException(
            422,
            str(exc) if isinstance(exc, ValueError) else "File could not be validated",
        )
    settings().upload_dir.mkdir(parents=True, exist_ok=True)
    path = (settings().upload_dir / (secrets.token_hex(24) + suffix)).resolve()
    path.write_bytes(content)
    row = Document(
        user_id=user.id,
        semester_id=semester_id,
        kind=kind,
        name=Path(file.filename).name[:255],
        path=str(path),
    )
    try:
        db.add(row)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return document_view(row)


def document_view(row):
    data = serialize(row)
    data.pop("path", None)
    return data


@app.get("/api/documents")
def documents(semester_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, semester_id, user)
    return [
        document_view(row)
        for row in db.scalars(
            select(Document)
            .where(Document.user_id == user.id, Document.semester_id == semester_id)
            .order_by(Document.id.desc())
        )
    ]


@app.get("/api/documents/{item_id}")
def document(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    return document_view(owned(db, Document, item_id, user))


@app.delete("/api/documents/{item_id}")
def delete_document(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, Document, item_id, user)
    if row.status == "processing":
        raise HTTPException(409, "Wait for extraction to finish before deleting")
    path = row.path
    db.delete(row)
    db.commit()
    Path(path).unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/documents/{item_id}/retry")
def retry_document(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, Document, item_id, user)
    if row.status not in ('failed', 'review'):
        raise HTTPException(409, 'Only failed or unconfirmed review imports can be re-extracted')
    row.status = "queued"
    row.error = ""
    row.preview = {}
    row.updated_at = utcnow()
    db.commit()
    return document_view(row)


@app.post("/api/documents/{item_id}/confirm")
def confirm(
    item_id: int, body: ImportConfirm, user=Depends(current_user), db=Depends(get_db)
):
    row = db.scalar(
        select(Document)
        .where(Document.id == item_id, Document.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Record not found")
    if row.status != "review":
        raise HTTPException(
            409, "Import must be in review; it may already be confirmed"
        )
    semester = db.get(Semester, row.semester_id)
    profile = db.get(Profile, user.id)
    try:
        validator = {
            "attendance": AttendanceImportRow,
            "timetable": TimetableImportRow,
            "calendar": CalendarImportRow,
        }[row.kind]
        parsed = [validator.model_validate(r) for r in body.rows]
    except ValidationError as exc:
        raise HTTPException(422, jsonable_encoder(exc.errors(include_context=False)))
    seen = set()
    for item in parsed:
        if row.kind == "calendar":
            if (
                not semester.start_date
                <= item.start_date
                <= item.end_date
                <= semester.end_date
            ):
                raise HTTPException(422, "Calendar dates must be within the semester")
            key = (item.title.casefold(), item.start_date, item.end_date, item.kind)
            if key in seen:
                raise HTTPException(409, "Duplicate calendar event in preview")
            seen.add(key)
            duplicate = db.scalar(
                select(CalendarEvent).where(
                    CalendarEvent.semester_id == semester.id,
                    CalendarEvent.title == item.title,
                    CalendarEvent.start_date == item.start_date,
                    CalendarEvent.end_date == item.end_date,
                    CalendarEvent.kind == item.kind,
                )
            )
            if duplicate:
                raise HTTPException(409, "Calendar event already exists")
            db.add(
                CalendarEvent(
                    user_id=user.id, semester_id=semester.id, **item.model_dump()
                )
            )
            continue
        code = item.code.upper().strip()
        subject = db.scalar(
            select(Subject).where(
                Subject.semester_id == semester.id, Subject.code == code
            )
        )
        if not subject:
            # Exact normalized names are matched; ambiguous fuzzy matches are never auto-merged.
            candidates = [
                s
                for s in db.scalars(
                    select(Subject).where(Subject.semester_id == semester.id)
                )
                if " ".join(s.name.casefold().split())
                == " ".join(item.name.casefold().split())
            ]
            if candidates:
                raise HTTPException(
                    409,
                    f"{item.name} already exists under another code. Correct the course code in preview.",
                )
            subject = Subject(
                user_id=user.id,
                semester_id=semester.id,
                code=code,
                name=item.name,
                kind=item.kind if row.kind == 'attendance' else 'theory',
                instructor_id=instructor_id(db, user.id, item.instructor) if row.kind == 'attendance' else None,
            )
            db.add(subject)
            db.flush()
        if row.kind == "attendance":
            if code in seen:
                raise HTTPException(409, "Duplicate subject in attendance preview")
            seen.add(code)
            if (
                not semester.start_date
                <= item.through_date
                <= min(semester.end_date, local_now(profile).date())
            ):
                raise HTTPException(
                    422,
                    "Attendance through-date must be within the semester and not in the future",
                )
            fields = dict(
                user_id=user.id,
                subject_id=subject.id,
                document_id=row.id,
                through_date=item.through_date,
                attended=item.attended,
                conducted=item.conducted,
            )
            if body.mode == "baseline":
                if db.scalar(
                    select(Baseline.id).where(Baseline.subject_id == subject.id)
                ):
                    raise HTTPException(
                        409,
                        "Baseline already exists. Import as reconciliation instead.",
                    )
                count = db.scalar(
                    select(Attendance.id)
                    .join(Occurrence)
                    .where(
                        Occurrence.subject_id == subject.id,
                        Occurrence.starts_at
                        < datetime.combine(
                            item.through_date + timedelta(days=1), time.min
                        ),
                        Attendance.status != "pending",
                    )
                )
                if count:
                    raise HTTPException(
                        409,
                        "Local attendance exists through that date. Use reconciliation; no local data was overwritten.",
                    )
                db.add(Baseline(**fields))
            else:
                db.add(Reconciliation(**fields))
        elif row.kind == "timetable":
            validate_overlap(
                db, user.id, subject, item.weekday, item.start_time, item.end_time
            )
            db.add(
                Timetable(
                    user_id=user.id,
                    subject_id=subject.id,
                    **item.model_dump(exclude={"code", "name"}),
                )
            )
            db.flush()
    row.preview = row.preview | {
        "rows": [item.model_dump(mode="json") for item in parsed],
        "confirmed_mode": body.mode,
    }
    row.status = "confirmed"
    row.updated_at = utcnow()
    db.flush()
    if row.kind in ("calendar", "timetable"):
        regenerate(db, user.id, semester.id)
    audit(
        db,
        user.id,
        "import_confirmed",
        {"document_id": row.id, "mode": body.mode, "rows": body.rows},
    )
    if profile.notify_imports:
        notify(
            db,
            user.id,
            f"import:{row.id}:confirmed",
            "import",
            f"{row.name}: {len(parsed)} reviewed rows saved.",
        )
    db.commit()
    return document_view(row)


@app.get("/api/reconciliation")
def reconciliations(semester_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, semester_id, user)
    ids = select(Subject.id).where(
        Subject.semester_id == semester_id, Subject.user_id == user.id
    )
    profile = db.get(Profile, user.id)
    output = []
    for row in db.scalars(
        select(Reconciliation)
        .where(Reconciliation.user_id == user.id, Reconciliation.subject_id.in_(ids))
        .order_by(Reconciliation.id.desc())
    ):
        subject = db.get(Subject, row.subject_id)
        baseline = db.scalar(select(Baseline).where(Baseline.subject_id == subject.id))
        # A later aggregate baseline cannot reconstruct an earlier official snapshot.
        comparable = not baseline or baseline.through_date <= row.through_date
        local = (
            subject_stats(
                db, subject, profile, datetime.combine(row.through_date, time.max)
            )
            if comparable
            else None
        )
        official = percentage(row.attended, row.conducted)
        match = (
            local
            and local["attended"] == row.attended
            and local["conducted"] == row.conducted
        )
        output.append(
            serialize(row)
            | {
                "subject": subject.name,
                "local_attended": local["attended"] if local else None,
                "local_conducted": local["conducted"] if local else None,
                "official_percentage": official,
                "local_percentage": local["percentage"] if local else None,
                "difference_pp": (
                    round(official - local["percentage"], 2)
                    if local
                    and local["percentage"] is not None
                    and official is not None
                    else None
                ),
                "status": "match" if match else "mismatch" if comparable else "review",
            }
        )
    return output


@app.get("/api/baselines")
def baselines(semester_id: int, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Semester, semester_id, user)
    ids = select(Subject.id).where(Subject.semester_id == semester_id)
    return [
        serialize(row)
        | {
            "code": db.get(Subject, row.subject_id).code,
            "name": db.get(Subject, row.subject_id).name,
        }
        for row in db.scalars(
            select(Baseline).where(
                Baseline.user_id == user.id, Baseline.subject_id.in_(ids)
            )
        )
    ]


@app.put("/api/baselines/{item_id}")
def correct_baseline(
    item_id: int,
    body: AttendanceImportRow,
    user=Depends(current_user),
    db=Depends(get_db),
):
    row = owned(db, Baseline, item_id, user)
    subject = db.get(Subject, row.subject_id)
    semester = db.get(Semester, subject.semester_id)
    profile = db.get(Profile, user.id)
    if body.code.upper() != subject.code or body.name != subject.name:
        raise HTTPException(
            422, "Correct counts only; subject identity cannot change here"
        )
    if (
        not semester.start_date
        <= body.through_date
        <= min(semester.end_date, local_now(profile).date())
    ):
        raise HTTPException(
            422, "Through-date must be within semester and not in the future"
        )
    covered = db.scalar(
        select(Attendance.id)
        .join(Occurrence)
        .where(
            Occurrence.subject_id == subject.id,
            Occurrence.starts_at
            < datetime.combine(body.through_date + timedelta(days=1), time.min),
            Attendance.status != "pending",
        )
    )
    if covered:
        raise HTTPException(
            409,
            "This correction would cover local attendance records. Review reconciliation instead.",
        )
    audit(
        db,
        user.id,
        "baseline_corrected",
        {"before": serialize(row), "after": body.model_dump()},
    )
    row.attended = body.attended
    row.conducted = body.conducted
    row.through_date = body.through_date
    db.commit()
    return serialize(row)


@app.patch("/api/reconciliation/{item_id}")
def resolve(
    item_id: int, body: Resolve, user=Depends(current_user), db=Depends(get_db)
):
    row = owned(db, Reconciliation, item_id, user)
    row.resolution = body.resolution
    row.note = body.note
    audit(db, user.id, "reconciliation_reviewed", {"id": item_id, **body.model_dump()})
    db.commit()
    return serialize(row)


@app.get("/api/notifications")
def notifications(
    semester_id: int | None = None, user=Depends(current_user), db=Depends(get_db)
):
    if semester_id:
        owned(db, Semester, semester_id, user)
        refresh(db, user.id, semester_id)
        db.commit()
    return [
        serialize(row)
        for row in db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(300)
        )
    ]


@app.patch("/api/notifications/{item_id}")
def read_notification(item_id: int, user=Depends(current_user), db=Depends(get_db)):
    row = owned(db, Notification, item_id, user)
    row.read = True
    db.commit()
    return serialize(row)


@app.post("/api/notifications/read-all")
def read_all(user=Depends(current_user), db=Depends(get_db)):
    for row in db.scalars(
        select(Notification).where(
            Notification.user_id == user.id, Notification.read == False
        )
    ):
        row.read = True
    db.commit()
    return {"ok": True}


@app.get("/api/export")
def export(
    semester_id: int,
    format: Literal["json", "csv"] = "json",
    user=Depends(current_user),
    db=Depends(get_db),
):
    semester = owned(db, Semester, semester_id, user)
    # CSV attendance export is interoperable with the import pipeline (explicit through-date).
    data = summary(db, user.id, semester_id)
    if format == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["code", "name", "attended", "conducted", "through_date"])
        today = min(local_now(db.get(Profile, user.id)).date(), semester.end_date)
        for s in data["subjects"]:
            writer.writerow(
                [s["code"], s["name"], s["attended"], s["conducted"], today]
            )
        return Response(
            stream.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="AttendTrend-attendance.csv"'
            },
        )
    ids = select(Subject.id).where(
        Subject.semester_id == semester_id, Subject.user_id == user.id
    )
    tables = {
        "subjects": Subject,
        "timetable": Timetable,
        "events": CalendarEvent,
        "classes": Occurrence,
        "attendance": Attendance,
        "baselines": Baseline,
        "reconciliation": Reconciliation,
    }
    out = {"schema_version": 1, "semester": serialize(semester), "summary": data}
    for key, model in tables.items():
        q = select(model).where(model.user_id == user.id)
        if model in (Subject, CalendarEvent):
            q = q.where(model.semester_id == semester_id)
        elif model == Attendance:
            q = q.where(
                model.occurrence_id.in_(
                    select(Occurrence.id).where(Occurrence.subject_id.in_(ids))
                )
            )
        else:
            q = q.where(model.subject_id.in_(ids))
        out[key] = [serialize(r) for r in db.scalars(q)]
    out["profile"] = serialize(db.get(Profile, user.id))
    return JSONResponse(
        out,
        headers={"Content-Disposition": 'attachment; filename="AttendTrend-data.json"'},
    )
