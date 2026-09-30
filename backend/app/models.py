from datetime import datetime, date, time, timezone
from sqlalchemy import (
    String,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime]


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    student_id: Mapped[str] = mapped_column(String(100), default="")
    institution: Mapped[str] = mapped_column(String(200), default="")
    section: Mapped[str] = mapped_column(String(40), default="")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Kolkata")
    target: Mapped[float] = mapped_column(default=75)
    safety_buffer: Mapped[float] = mapped_column(default=5)
    risk_sensitivity: Mapped[str] = mapped_column(String(10), default="balanced")
    theme: Mapped[str] = mapped_column(String(10), default="light")
    notify_risk: Mapped[bool] = mapped_column(default=True)
    notify_upcoming: Mapped[bool] = mapped_column(default=True)
    notify_imports: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        CheckConstraint("target > 0 AND target <= 100"),
        CheckConstraint("safety_buffer >= 0 AND safety_buffer <= 25"),
    )


class Semester(Base):
    __tablename__ = "semesters"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date]
    end_date: Mapped[date]
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint("end_date >= start_date"),
    )


class Instructor(Base):
    __tablename__ = "instructors"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("user_id", "name"),)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    instructor_id: Mapped[int | None] = mapped_column(
        ForeignKey("instructors.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(12), default="theory")
    planned_lectures: Mapped[int | None] = mapped_column(nullable=True)
    __table_args__ = (
        UniqueConstraint("semester_id", "code"),
        CheckConstraint("kind IN ('theory', 'practical')"),
        CheckConstraint("planned_lectures IS NULL OR planned_lectures >= 0"),
    )


class Timetable(Base):
    __tablename__ = "timetable"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int]
    start_time: Mapped[time]
    end_time: Mapped[time]
    room: Mapped[str] = mapped_column(String(100), default="")
    effective_from: Mapped[datetime | None]
    __table_args__ = (
        UniqueConstraint("subject_id", "weekday", "start_time"),
        CheckConstraint("weekday >= 0 AND weekday <= 6"),
        CheckConstraint("end_time > start_time"),
    )


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(150))
    start_date: Mapped[date]
    end_date: Mapped[date]
    kind: Mapped[str] = mapped_column(String(20), default="event")
    __table_args__ = (
        CheckConstraint("end_date >= start_date"),
        CheckConstraint("kind IN ('holiday','event','exam')"),
    )


class Occurrence(Base):
    __tablename__ = "occurrences"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    timetable_id: Mapped[int | None] = mapped_column(
        ForeignKey("timetable.id", ondelete="SET NULL")
    )
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    source_start: Mapped[datetime | None]
    room: Mapped[str] = mapped_column(String(100), default="")
    cancelled: Mapped[bool] = mapped_column(default=False)
    cancellation_reason: Mapped[str] = mapped_column(String(20), default="")
    __table_args__ = (
        UniqueConstraint("subject_id", "starts_at"),
        CheckConstraint("ends_at > starts_at"),
        Index("ix_occurrences_user_start", "user_id", "starts_at"),
    )


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("occurrences.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(10))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)
    __table_args__ = (
        CheckConstraint("status IN ('present','absent','excused','pending')"),
    )


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    preview: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class Baseline(Base):
    __tablename__ = "baselines"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), unique=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    through_date: Mapped[date]
    attended: Mapped[int]
    conducted: Mapped[int]
    __table_args__ = (CheckConstraint("attended >= 0 AND conducted >= attended"),)


class Reconciliation(Base):
    __tablename__ = "reconciliations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE")
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    through_date: Mapped[date]
    attended: Mapped[int]
    conducted: Mapped[int]
    resolution: Mapped[str] = mapped_column(String(20), default="review")
    note: Mapped[str] = mapped_column(String(500), default="")
    __table_args__ = (CheckConstraint("attended >= 0 AND conducted >= attended"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "key"),)
