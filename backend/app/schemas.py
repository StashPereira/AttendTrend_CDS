from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    EmailStr,
    model_validator,
    field_validator,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Strict):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class Signup(Credentials):
    name: str = Field(min_length=1, max_length=100)


class ProfileInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    student_id: str = Field(default="", max_length=100)
    institution: str = Field(default="", max_length=200)
    section: str = Field(default="", max_length=40)
    timezone: str = "Asia/Kolkata"
    target: float = Field(default=75, gt=0, le=100)
    safety_buffer: float = Field(default=5, ge=0, le=25)
    risk_sensitivity: Literal["cautious", "balanced", "relaxed"] = "balanced"
    theme: Literal["light", "dark", "system"] = "light"
    notify_risk: bool = True
    notify_upcoming: bool = True
    notify_imports: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown IANA timezone")
        return value


class PasswordChange(Strict):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class SemesterInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def dates(self):
        if (
            self.end_date < self.start_date
            or (self.end_date - self.start_date).days > 730
        ):
            raise ValueError("Semester must span 0–730 days")
        return self


class SubjectInput(Strict):
    planned_lectures: int | None = Field(default=None, ge=0, le=10000)
    semester_id: int
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=40)
    instructor: str = Field(default="", max_length=100)
    kind: Literal["theory", "practical"] = "theory"

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v):
        return v.upper().strip()


class TimetableInput(Strict):
    subject_id: int
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    room: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def times(self):
        if (
            self.end_time <= self.start_time
            or self.start_time.tzinfo
            or self.end_time.tzinfo
        ):
            raise ValueError("Use local times; end must follow start")
        return self


class EventInput(Strict):
    semester_id: int
    title: str = Field(min_length=1, max_length=150)
    start_date: date
    end_date: date
    kind: Literal["holiday", "exam", "event"] = "event"

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End must follow start")
        return self


class OccurrenceInput(Strict):
    subject_id: int
    starts_at: datetime
    ends_at: datetime
    room: str = Field(default="", max_length=100)
    cancelled: bool = False

    @model_validator(mode="after")
    def times(self):
        if (
            self.starts_at.tzinfo
            or self.ends_at.tzinfo
            or self.ends_at <= self.starts_at
        ):
            raise ValueError("Use local datetimes; end must follow start")
        return self


class Mark(Strict):
    occurrence_id: int
    status: Literal["present", "absent", "excused", "cancelled", "pending"]


class Marks(Strict):
    records: list[Mark] = Field(min_length=1, max_length=300)


class Scenario(Strict):
    subject_id: int
    attend: int = Field(default=0, ge=0, le=10000)
    miss: int = Field(default=0, ge=0, le=10000)
    target: float | None = Field(default=None, gt=0, le=100)


class AttendanceImportRow(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=150)
    attended: int = Field(ge=0, le=100000)
    conducted: int = Field(ge=0, le=100000)
    through_date: date
    kind: Literal['theory', 'practical'] = 'theory'
    instructor: str = Field(default='', max_length=100)

    @model_validator(mode="after")
    def counts(self):
        if self.attended > self.conducted:
            raise ValueError("Attended cannot exceed conducted")
        return self


class TimetableImportRow(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=150)
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    room: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def times(self):
        if (
            self.start_time.tzinfo
            or self.end_time.tzinfo
            or self.end_time <= self.start_time
        ):
            raise ValueError("Use local times; end must follow start")
        return self


class CalendarImportRow(Strict):
    title: str = Field(min_length=1, max_length=150)
    start_date: date
    end_date: date
    kind: Literal["holiday", "event", "exam"]

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End must follow start")
        return self


class ImportConfirm(Strict):
    rows: list[dict] = Field(min_length=1, max_length=1000)
    mode: Literal["baseline", "reconciliation"] = "baseline"


class Resolve(Strict):
    resolution: Literal["keep_local", "acknowledged"]
    note: str = Field(default="", max_length=500)
