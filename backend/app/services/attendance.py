"""One calculation engine for every view. Excused/cancelled/pending do not count.
Imported baselines summarize classes THROUGH a date; local entries after that date
only are added, so imports never double count scheduled records.
"""

from datetime import datetime, time
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from zoneinfo import ZoneInfo
from sqlalchemy import select
from ..models import Subject, Occurrence, Attendance, Baseline, Profile


def local_now(profile):
    return datetime.now(ZoneInfo(profile.timezone)).replace(tzinfo=None)


def percentage(attended, conducted):
    return round(100 * attended / conducted, 2) if conducted else None


def recovery(attended, conducted, remaining, target):
    a, c, r, t = (
        Decimal(attended),
        Decimal(conducted),
        Decimal(remaining),
        Decimal(str(target)) / 100,
    )
    deficit = t * c - a
    required = (
        0
        if deficit <= 0
        else (
            None
            if t == 1
            else int((deficit / (1 - t)).to_integral_value(rounding=ROUND_CEILING))
        )
    )
    skip_now = (
        max(0, int((a / t - c).to_integral_value(rounding=ROUND_FLOOR))) if c else 0
    )
    future_required = max(
        0, int((t * (c + r) - a).to_integral_value(rounding=ROUND_CEILING))
    )
    feasible = future_required <= remaining
    return {
        "required_consecutive": required,
        "required_of_remaining": future_required,
        "recoverable": feasible,
        "safe_to_skip": min(skip_now, remaining),
        "maximum_final_absences": (
            max(0, remaining - future_required) if feasible else 0
        ),
        "best_case": percentage(attended + remaining, conducted + remaining),
        "worst_case": percentage(attended, conducted + remaining),
        "remaining": remaining,
    }


def scenario(attended, conducted, attend, miss, target):
    projected = percentage(attended + attend, conducted + attend + miss)
    return {
        "current": percentage(attended, conducted),
        "projected": projected,
        "attended": attended + attend,
        "conducted": conducted + attend + miss,
        "meets_target": projected is not None
        and Decimal(attended + attend) * 100
        >= Decimal(str(target)) * (conducted + attend + miss),
        "target": target,
    }


def subject_stats(db, subject, profile, now=None):
    now = now or local_now(profile)
    baseline = db.scalar(select(Baseline).where(Baseline.subject_id == subject.id))
    attended = (
        baseline.attended if baseline and baseline.through_date <= now.date() else 0
    )
    conducted = (
        baseline.conducted if baseline and baseline.through_date <= now.date() else 0
    )
    rows = db.execute(
        select(Occurrence, Attendance.status)
        .outerjoin(Attendance, Attendance.occurrence_id == Occurrence.id)
        .where(Occurrence.subject_id == subject.id)
        .order_by(Occurrence.starts_at, Occurrence.id)
    ).all()
    remaining = pending = excused = cancelled = 0
    history = []
    for occ, status in rows:
        if occ.cancelled:
            cancelled += 1
            continue
        if occ.ends_at > now:
            remaining += 1
            continue
        if baseline and occ.starts_at.date() <= baseline.through_date:
            continue
        if status in ("present", "absent"):
            conducted += 1
            attended += status == "present"
            history.append(
                {
                    "date": occ.starts_at.date().isoformat(),
                    "attended": attended,
                    "conducted": conducted,
                    "percentage": percentage(attended, conducted),
                    "weekday": occ.starts_at.weekday(),
                    "status": status,
                }
            )
        elif status == "excused":
            excused += 1
        else:
            pending += 1
    scheduled_remaining = remaining
    planning_warnings = []
    if subject.planned_lectures is not None:
        available = max(0, subject.planned_lectures - conducted - pending)
        remaining = min(remaining, available)
        if subject.planned_lectures < conducted + pending:
            planning_warnings.append('Semester lecture total is below conducted/pending classes. Correct the total or records; no skip dates are suggested.')
        if available != scheduled_remaining:
            planning_warnings.append('Semester total and dated timetable disagree. The smaller remaining count is used; verify totals, holidays and teaching dates.')
    else:
        planning_warnings.append('Enter total semester lectures in Data & Reconciliation → Subjects to check the timetable against your subject total.')
    calendar_target = min(100, profile.target + profile.safety_buffer)
    calendar_plan = recovery(attended, conducted, remaining, calendar_target)
    calendar_allowance = calendar_plan['safe_to_skip'] if not pending and subject.planned_lectures is not None else 0
    if pending:
        planning_warnings.append('Resolve pending attendance before using suggested skip dates.')
    p = percentage(attended, conducted)
    plan = recovery(attended, conducted, remaining, profile.target)
    # Beta(1,1) posterior predictive mean; honest deterministic bounds.
    forecast = None
    rate = (attended + 1) / (conducted + 2) if conducted else None
    if rate is not None:
        forecast = round(
            100 * (attended + remaining * rate) / (conducted + remaining), 2
        )
    method = (
        "No observations; only deterministic bounds available"
        if not conducted
        else (
            "Beta-binomial smoothed attendance rate"
            if conducted >= 10
            else "Limited history: smoothed statistical fallback"
        )
    )
    offset = (
        profile.safety_buffer
        if profile.risk_sensitivity == "cautious"
        else -profile.safety_buffer if profile.risk_sensitivity == "relaxed" else 0
    )
    threshold = max(0, min(100, profile.target + offset))
    risk = (
        "unknown"
        if p is None
        else (
            "critical"
            if not plan["recoverable"]
            else (
                "high"
                if forecast is not None and forecast < threshold
                else (
                    "medium"
                    if p < min(100, profile.target + profile.safety_buffer)
                    else "low"
                )
            )
        )
    )
    explanation = (
        "No marked conducted classes yet"
        if p is None
        else (
            "Even attending all scheduled remaining classes cannot reach target"
            if not plan["recoverable"]
            else (
                "Smoothed projection is below your risk threshold"
                if risk == "high"
                else (
                    "Attendance is within your safety buffer"
                    if risk == "medium"
                    else "Attendance and projection meet target"
                )
            )
        )
    )
    return {
        "id": subject.id,
        "name": subject.name,
        "code": subject.code,
        "kind": subject.kind,
        "planned_lectures": subject.planned_lectures,
        "scheduled_remaining": scheduled_remaining,
        "planning_warnings": planning_warnings,
        "calendar_skip_allowance": calendar_allowance,
        "calendar_target": calendar_target,
        "attended": attended,
        "conducted": conducted,
        "missed": conducted - attended,
        "percentage": p,
        "pending": pending,
        "excused": excused,
        "cancelled": cancelled,
        "on_track": conducted > 0
        and Decimal(attended) * 100 >= Decimal(str(profile.target)) * conducted,
        "recovery": plan,
        "forecast": forecast,
        "forecast_method": method,
        "risk": risk,
        "risk_explanation": explanation,
        "history": history,
        "baseline_through": baseline.through_date.isoformat() if baseline else None,
    }


def summary(db, user_id, semester_id):
    profile = db.get(Profile, user_id)
    subjects = db.scalars(
        select(Subject)
        .where(Subject.user_id == user_id, Subject.semester_id == semester_id)
        .order_by(Subject.name)
    ).all()
    stats = [subject_stats(db, subject, profile) for subject in subjects]
    a, c = sum(s["attended"] for s in stats), sum(s["conducted"] for s in stats)
    # Build cumulative daily counts in one pass, including aggregate baselines on
    # their through-date. No additional queries per chart point.
    daily = {}
    for s in stats:
        for row in s["history"]:
            counts = daily.setdefault(row["date"], [0, 0])
            counts[0] += row["status"] == "present"
            counts[1] += 1
    for baseline in db.scalars(
        select(Baseline).where(
            Baseline.user_id == user_id,
            Baseline.subject_id.in_([s.id for s in subjects]),
        )
    ):
        if baseline.through_date <= local_now(profile).date():
            counts = daily.setdefault(baseline.through_date.isoformat(), [0, 0])
            counts[0] += baseline.attended
            counts[1] += baseline.conducted
    ta = tc = 0
    trend = []
    for day, counts in sorted(daily.items()):
        ta += counts[0]
        tc += counts[1]
        trend.append({"date": day, "percentage": percentage(ta, tc)})
    weekday_counts = {i: [0, 0] for i in range(7)}
    for s in stats:
        for row in s["history"]:
            weekday_counts[row["weekday"]][1] += 1
            weekday_counts[row["weekday"]][0] += row["status"] == "present"
    weekdays = [
        {"weekday": k, "percentage": percentage(*v), "conducted": v[1]}
        for k, v in weekday_counts.items()
    ]
    return {
        "overall": {
            "attended": a,
            "conducted": c,
            "missed": c - a,
            "percentage": percentage(a, c),
            "on_track": sum(s["on_track"] for s in stats),
            "subject_count": len(stats),
            "at_risk": sum(s["risk"] in ("high", "critical") for s in stats),
            "safe_to_skip": sum(s["recovery"]["safe_to_skip"] for s in stats),
            "pending": sum(s["pending"] for s in stats),
        },
        "subjects": stats,
        "trend": trend[-100:],
        "weekdays": weekdays,
        "target": profile.target,
        "safety_buffer": profile.safety_buffer,
        "calculation_policy": "Present/absent only; excused, cancelled, pending and future classes excluded. Imported baseline covers through-date.",
    }
