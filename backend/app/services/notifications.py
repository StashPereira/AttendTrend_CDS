from datetime import timedelta
from sqlalchemy import select
from ..models import Notification, Profile, Occurrence, Subject
from .attendance import summary, local_now


def notify(db, user_id, key, kind, message):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(
        insert(Notification)
        .values(user_id=user_id, key=key, kind=kind, message=message)
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
    )


def refresh(db, user_id, semester_id):
    profile = db.get(Profile, user_id)
    now = local_now(profile)
    if profile.notify_risk:
        for s in summary(db, user_id, semester_id)["subjects"]:
            if s["risk"] in ("high", "critical"):
                notify(
                    db,
                    user_id,
                    f"risk:{s['id']}:{now.date()}:{s['risk']}",
                    "risk",
                    f"{s['name']}: {s['risk_explanation']}",
                )
            if s["percentage"] is not None and s["percentage"] < profile.target:
                required = s["recovery"]["required_consecutive"]
                notify(
                    db,
                    user_id,
                    f"below:{s['id']}:{now.date()}",
                    "recovery",
                    f"{s['name']} is below {profile.target:g}%. Required consecutive classes: {required if required is not None else 'not reachable at 100% target'}.",
                )
    if profile.notify_upcoming:
        ids = select(Subject.id).where(
            Subject.user_id == user_id, Subject.semester_id == semester_id
        )
        for occ in db.scalars(
            select(Occurrence).where(
                Occurrence.user_id == user_id,
                Occurrence.subject_id.in_(ids),
                Occurrence.cancelled == False,
                Occurrence.starts_at >= now,
                Occurrence.starts_at <= now + timedelta(hours=24),
            )
        ):
            subject = db.get(Subject, occ.subject_id)
            notify(
                db,
                user_id,
                f"upcoming:{occ.id}",
                "upcoming",
                f"{subject.name} starts {occ.starts_at:%d %b, %H:%M} {profile.timezone}.",
            )
