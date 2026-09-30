from datetime import datetime, timedelta
from sqlalchemy import select
from fastapi import HTTPException
from ..models import (
    Subject,
    Semester,
    Timetable,
    CalendarEvent,
    Occurrence,
    Attendance,
    Profile,
)
from .attendance import local_now


def regenerate(db, user_id, semester_id, after=None, entry_id=None):
    semester = db.get(Semester, semester_id)
    subjects = db.scalars(
        select(Subject).where(
            Subject.user_id == user_id, Subject.semester_id == semester_id
        )
    ).all()
    ids = [s.id for s in subjects]
    events = db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.semester_id == semester_id,
            CalendarEvent.kind == "holiday",
        )
    ).all()
    entries = db.scalars(
        select(Timetable).where(
            Timetable.user_id == user_id, Timetable.subject_id.in_(ids)
        )
    ).all()
    existing = db.scalars(
        select(Occurrence).where(Occurrence.subject_id.in_(ids))
    ).all()
    index = {(o.subject_id, o.starts_at): o for o in existing}
    moved = {(o.timetable_id, o.source_start) for o in existing if o.source_start}
    marked = set(
        db.scalars(
            select(Attendance.occurrence_id).where(
                Attendance.user_id == user_id, Attendance.status != "pending"
            )
        )
    )
    generated = 0
    for entry in entries:
        if entry_id is not None and entry.id != entry_id:
            continue
        day = semester.start_date
        while day <= semester.end_date:
            if day.weekday() == entry.weekday:
                start = datetime.combine(day, entry.start_time)
                cutoff = max(
                    [value for value in (after, entry.effective_from) if value is not None],
                    default=None,
                )
                if cutoff is not None and datetime.combine(day, entry.end_time) <= cutoff:
                    day += timedelta(days=1)
                    continue
                holiday = any(e.start_date <= day <= e.end_date for e in events)
                if (entry.id, start) in moved:
                    day += timedelta(days=1)
                    continue
                row = index.get((entry.subject_id, start))
                if row is None:
                    row = Occurrence(
                        user_id=user_id,
                        subject_id=entry.subject_id,
                        timetable_id=entry.id,
                        starts_at=start,
                        ends_at=datetime.combine(day, entry.end_time),
                        room=entry.room,
                        cancelled=holiday,
                        cancellation_reason="holiday" if holiday else "",
                    )
                    db.add(row)
                    index[(entry.subject_id, start)] = row
                    generated += 1
                elif (
                    row.timetable_id == entry.id
                    and not row.source_start
                    and row.id not in marked
                    and row.cancellation_reason in ("", "holiday")
                ):
                    row.cancelled = holiday
                    row.cancellation_reason = "holiday" if holiday else ""
                    row.ends_at = datetime.combine(day, entry.end_time)
                    row.room = entry.room
            day += timedelta(days=1)
    db.flush()
    return generated


def validate_overlap(db, user_id, subject, weekday, start, end, exclude=None):
    subject_ids = select(Subject.id).where(
        Subject.user_id == user_id, Subject.semester_id == subject.semester_id
    )
    query = select(Timetable).where(
        Timetable.subject_id.in_(subject_ids),
        Timetable.weekday == weekday,
        Timetable.start_time < end,
        Timetable.end_time > start,
    )
    if exclude:
        query = query.where(Timetable.id != exclude)
    if db.scalar(query):
        raise HTTPException(409, "This timetable slot overlaps an existing class")


def delete_timetable(db, entry):
    now = local_now(db.get(Profile, entry.user_id))
    marked = set(
        db.scalars(
            select(Attendance.occurrence_id).where(Attendance.user_id == entry.user_id)
        )
    )
    for row in db.scalars(
        select(Occurrence).where(Occurrence.timetable_id == entry.id)
    ):
        if (
            row.ends_at > now
            and row.id not in marked
            and not row.source_start
            and row.cancellation_reason != 'manual'
        ):
            db.delete(row)
        else:
            row.timetable_id = None
    db.flush()
    db.delete(entry)
