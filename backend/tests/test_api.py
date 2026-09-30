from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Attendance, Audit, Document
from app.worker import process_one
from .conftest import register


def add_class(c, subject, day="2020-01-06", start="09:00", end="10:00"):
    r = c.post(
        "/api/classes",
        json={
            "subject_id": subject["id"],
            "starts_at": day + "T" + start,
            "ends_at": day + "T" + end,
            "room": "A1",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_auth_csrf_logout(client):
    assert client.get("/api/auth/me").status_code == 401
    register(client)
    assert client.get("/api/auth/me").json()["name"] == "Student"
    client.headers.pop("X-CSRF-Token")
    assert (
        client.post(
            "/api/semesters",
            json={"name": "Bad", "start_date": "2020-01-01", "end_date": "2020-02-01"},
        ).status_code
        == 403
    )
    client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf"]
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "student@example.com", "password": "WrongPassword123"},
        ).status_code
        == 401
    )
    r = client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "LongPassword!123"},
    )
    assert r.status_code == 200


def test_origin_and_password_revocation(account):
    assert (
        account.post(
            "/api/auth/logout", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    another = TestClient(app)
    r = another.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "LongPassword!123"},
    )
    another.headers["X-CSRF-Token"] = r.json()["csrf"]
    r = account.post(
        "/api/auth/password",
        json={
            "current_password": "LongPassword!123",
            "new_password": "NewLongPassword123",
        },
    )
    assert r.status_code == 200
    assert another.get("/api/auth/me").status_code == 401


def test_owner_isolation(academic):
    c, semester, subject = academic
    occurrence = add_class(c, subject)
    with TestClient(app) as other:
        register(other, "other@example.com")
        for path in [
            f"/api/subjects?semester_id={semester['id']}",
            f"/api/summary?semester_id={semester['id']}",
            f"/api/export?semester_id={semester['id']}",
        ]:
            assert other.get(path).status_code == 404
        assert (
            other.put(
                "/api/attendance",
                json={
                    "records": [
                        {"occurrence_id": occurrence["id"], "status": "present"}
                    ]
                },
            ).status_code
            == 404
        )
        assert other.delete("/api/subjects/" + str(subject["id"])).status_code == 404
        assert (
            other.post(
                "/api/what-if",
                json={"subject_id": subject["id"], "attend": 1, "miss": 0},
            ).status_code
            == 404
        )


def test_attendance_exclusions_atomicity_and_edit(academic):
    c, semester, subject = academic
    ids = [add_class(c, subject, f"2020-01-{d:02d}")["id"] for d in range(6, 11)]
    assert (
        c.put(
            "/api/attendance",
            json={
                "records": [
                    {"occurrence_id": i, "status": s}
                    for i, s in zip(
                        ids, ["present", "absent", "excused", "cancelled", "pending"]
                    )
                ]
            },
        ).status_code
        == 200
    )
    s = c.get("/api/summary", params={"semester_id": semester["id"]}).json()
    assert s["overall"]["attended"] == 1 and s["overall"]["conducted"] == 2
    assert s["overall"]["percentage"] == 50
    assert s["subjects"][0]["excused"] == 1
    assert s["subjects"][0]["cancelled"] == 1
    assert s["subjects"][0]["pending"] == 1
    assert (
        c.put(
            "/api/attendance",
            json={
                "records": [
                    {"occurrence_id": ids[0], "status": "absent"},
                    {"occurrence_id": 999999, "status": "present"},
                ]
            },
        ).status_code
        == 404
    )
    assert (
        c.get("/api/summary", params={"semester_id": semester["id"]}).json()["overall"][
            "attended"
        ]
        == 1
    )
    assert c.delete("/api/attendance/" + str(ids[1])).status_code == 200
    assert (
        c.get("/api/summary", params={"semester_id": semester["id"]}).json()["overall"][
            "percentage"
        ]
        == 100
    )
    with SessionLocal() as db:
        assert db.query(Audit).count() >= 6


def test_future_and_scenarios(account):
    today = datetime.now().date()
    r = account.post(
        "/api/semesters",
        json={
            "name": "Now",
            "start_date": str(today),
            "end_date": str(today + timedelta(days=30)),
        },
    )
    subject = account.post(
        "/api/subjects",
        json={"semester_id": r.json()["id"], "name": "Physics", "code": "P101"},
    ).json()
    occ = add_class(account, subject, str(today + timedelta(days=1)))
    assert (
        account.put(
            "/api/attendance",
            json={"records": [{"occurrence_id": occ["id"], "status": "present"}]},
        ).status_code
        == 422
    )
    summary = account.get("/api/summary", params={"semester_id": r.json()["id"]}).json()
    assert (
        summary["overall"]["conducted"] == 0
        and summary["overall"]["percentage"] is None
    )
    assert summary["subjects"][0]["forecast"] is None
    assert summary["subjects"][0]["risk"] == "unknown"
    assert (
        account.post(
            "/api/what-if", json={"subject_id": subject["id"], "attend": 1}
        ).json()["projected"]
        == 100
    )
    assert (
        account.post(
            "/api/what-if", json={"subject_id": subject["id"], "attend": 2}
        ).status_code
        == 422
    )


def test_duplicates_validation_and_schedule(academic):
    c, semester, subject = academic
    assert (
        c.post(
            "/api/subjects",
            json={"semester_id": semester["id"], "name": "Duplicate", "code": "m101"},
        ).status_code
        == 409
    )
    assert (
        c.post(
            "/api/semesters",
            json={
                "name": "Invalid",
                "start_date": "2020-02-02",
                "end_date": "2020-01-01",
            },
        ).status_code
        == 422
    )
    r = c.post(
        "/api/timetable",
        json={
            "subject_id": subject["id"],
            "weekday": 0,
            "start_time": "09:00",
            "end_time": "10:00",
            "room": "R1",
        },
    )
    assert r.status_code == 201, r.text
    before = c.get("/api/classes", params={"semester_id": semester["id"]}).json()
    assert len(before) == 26
    assert (
        c.post("/api/semesters/" + str(semester["id"]) + "/generate").json()["created"]
        == 0
    )
    assert (
        c.post(
            "/api/timetable",
            json={
                "subject_id": subject["id"],
                "weekday": 0,
                "start_time": "09:30",
                "end_time": "10:30",
            },
        ).status_code
        == 409
    )
    event = c.post(
        "/api/events",
        json={
            "semester_id": semester["id"],
            "title": "Holiday",
            "start_date": "2020-01-06",
            "end_date": "2020-01-06",
            "kind": "holiday",
        },
    )
    assert event.status_code == 201
    rows = c.get("/api/classes", params={"semester_id": semester["id"]}).json()
    assert rows[0]["status"] == "cancelled"
    c.delete("/api/events/" + str(event.json()["id"]))
    assert (
        c.get("/api/classes", params={"semester_id": semester["id"]}).json()[0][
            "status"
        ]
        == "pending"
    )


def upload_csv(c, semester, kind, text):
    r = c.post(
        "/api/documents",
        data={"semester_id": semester["id"], "kind": kind},
        files={"file": ("import.csv", text, "text/csv")},
    )
    assert r.status_code == 201, r.text
    assert process_one()
    r = c.get("/api/documents/" + str(r.json()["id"]))
    assert r.json()["status"] == "review", r.text
    return r.json()


def test_import_baseline_reconciliation_and_no_overwrite(academic):
    c, semester, subject = academic
    d = upload_csv(
        c,
        semester,
        "attendance",
        "code,name,attended,conducted,through_date\nM101,Mathematics,8,10,2020-01-31\n",
    )
    assert "path" not in d
    body = {"rows": d["preview"]["rows"], "mode": "baseline"}
    assert c.post(f"/api/documents/{d['id']}/confirm", json=body).status_code == 200
    assert c.post(f"/api/documents/{d['id']}/confirm", json=body).status_code == 409
    old = add_class(c, subject, "2020-01-06")
    assert (
        c.put(
            "/api/attendance",
            json={"records": [{"occurrence_id": old["id"], "status": "present"}]},
        ).status_code
        == 409
    )
    new = add_class(c, subject, "2020-02-03")
    c.put(
        "/api/attendance",
        json={"records": [{"occurrence_id": new["id"], "status": "present"}]},
    )
    assert (
        c.get("/api/summary", params={"semester_id": semester["id"]}).json()["overall"][
            "attended"
        ]
        == 9
    )
    d2 = upload_csv(
        c,
        semester,
        "attendance",
        "code,name,attended,conducted,through_date\nM101,Mathematics,7,10,2020-01-31\n",
    )
    assert (
        c.post(
            f"/api/documents/{d2['id']}/confirm",
            json={"rows": d2["preview"]["rows"], "mode": "baseline"},
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/api/documents/{d2['id']}/confirm",
            json={"rows": d2["preview"]["rows"], "mode": "reconciliation"},
        ).status_code
        == 200
    )
    rec = c.get("/api/reconciliation", params={"semester_id": semester["id"]}).json()[0]
    assert rec["status"] == "mismatch" and rec["difference_pp"] == -10
    assert (
        c.patch(
            "/api/reconciliation/" + str(rec["id"]),
            json={"resolution": "keep_local", "note": "Review completed"},
        ).status_code
        == 200
    )
    assert (
        c.get("/api/summary", params={"semester_id": semester["id"]}).json()["overall"][
            "attended"
        ]
        == 9
    )
    assert c.get(
        "/api/export", params={"semester_id": semester["id"], "format": "csv"}
    ).text.startswith("code,name,attended,conducted,through_date")
    assert (
        c.get("/api/export", params={"semester_id": semester["id"]}).json()[
            "baselines"
        ][0]["attended"]
        == 8
    )


def test_import_atomic_rollback_and_local_conflict(academic):
    c, semester, subject = academic
    occ = add_class(c, subject)
    c.put(
        "/api/attendance",
        json={"records": [{"occurrence_id": occ["id"], "status": "present"}]},
    )
    d = upload_csv(
        c,
        semester,
        "attendance",
        "code,name,attended,conducted,through_date\nM101,Mathematics,2,3,2020-01-31\n",
    )
    assert (
        c.post(
            f"/api/documents/{d['id']}/confirm", json={"rows": d["preview"]["rows"]}
        ).status_code
        == 409
    )
    bad = [
        {
            "code": "NEW",
            "name": "New subject",
            "attended": 1,
            "conducted": 2,
            "through_date": "2020-01-31",
        },
        d["preview"]["rows"][0],
    ]
    assert (
        c.post(f"/api/documents/{d['id']}/confirm", json={"rows": bad}).status_code
        == 409
    )
    assert (
        len(c.get("/api/subjects", params={"semester_id": semester["id"]}).json()) == 1
    )
    assert c.get("/api/documents/" + str(d["id"])).json()["status"] == "review"


def test_upload_validation_and_access(academic):
    c, semester, subject = academic
    for filename, content in [
        ("malware.exe", b"bad"),
        ("wrong.pdf", b"bad"),
        ("bad.png", b"bad"),
        ("empty.csv", b""),
    ]:
        assert (
            c.post(
                "/api/documents",
                data={"semester_id": semester["id"], "kind": "attendance"},
                files={"file": (filename, content)},
            ).status_code
            == 422
        )
    d = upload_csv(
        c,
        semester,
        "attendance",
        "code,name,attended,conducted,through_date\nM101,Mathematics,1,2,2020-01-31\n",
    )
    with TestClient(app) as other:
        register(other, "other@example.com")
        assert other.get("/api/documents/" + str(d["id"])).status_code == 404
        assert other.delete("/api/documents/" + str(d["id"])).status_code == 404


def test_notifications_are_real_and_deduplicated(academic):
    c, semester, subject = academic
    occ = add_class(c, subject)
    c.put(
        "/api/attendance",
        json={"records": [{"occurrence_id": occ["id"], "status": "absent"}]},
    )
    first = c.get("/api/notifications", params={"semester_id": semester["id"]}).json()
    second = c.get("/api/notifications", params={"semester_id": semester["id"]}).json()
    assert len(first) == len(second) > 0
    assert c.patch("/api/notifications/" + str(first[0]["id"])).json()["read"]
    assert c.post("/api/notifications/read-all").status_code == 200
    assert all(
        n["read"]
        for n in c.get(
            "/api/notifications", params={"semester_id": semester["id"]}
        ).json()
    )


def test_regeneration_does_not_recreate_rescheduled_class(academic):
    c, semester, subject = academic
    r = c.post(
        "/api/timetable",
        json={
            "subject_id": subject["id"],
            "weekday": 0,
            "start_time": "09:00",
            "end_time": "10:00",
        },
    )
    assert r.status_code == 201
    rows = c.get("/api/classes", params={"semester_id": semester["id"]}).json()
    first = rows[0]
    r = c.put(
        "/api/classes/" + str(first["id"]),
        json={
            "subject_id": subject["id"],
            "starts_at": "2020-01-07T11:00",
            "ends_at": "2020-01-07T12:00",
            "room": "Moved",
        },
    )
    assert r.status_code == 200, r.text
    c.post("/api/semesters/" + str(semester["id"]) + "/generate")
    changed = c.get("/api/classes", params={"semester_id": semester["id"]}).json()
    assert len(changed) == len(rows)
    assert not any(row["starts_at"] == "2020-01-06T09:00:00" for row in changed)
    assert any(row["starts_at"] == "2020-01-07T11:00:00" for row in changed)


def test_holiday_never_overwrites_marked_records(academic):
    c, semester, subject = academic
    c.post(
        "/api/timetable",
        json={
            "subject_id": subject["id"],
            "weekday": 0,
            "start_time": "09:00",
            "end_time": "10:00",
        },
    )
    first = c.get("/api/classes", params={"semester_id": semester["id"]}).json()[0]
    c.put(
        "/api/attendance",
        json={"records": [{"occurrence_id": first["id"], "status": "present"}]},
    )
    c.post(
        "/api/events",
        json={
            "semester_id": semester["id"],
            "title": "Late holiday",
            "start_date": "2020-01-06",
            "end_date": "2020-01-06",
            "kind": "holiday",
        },
    )
    assert (
        c.get("/api/classes", params={"semester_id": semester["id"]}).json()[0][
            "status"
        ]
        == "present"
    )


def test_timetable_and_calendar_import_confirmation(academic):
    c, semester, subject = academic
    d = upload_csv(
        c,
        semester,
        "timetable",
        "code,name,weekday,start_time,end_time,room\nM101,Mathematics,Monday,09:00,10:00,A1\n",
    )
    assert (
        c.post(
            f"/api/documents/{d['id']}/confirm", json={"rows": d["preview"]["rows"]}
        ).status_code
        == 200
    )
    assert (
        len(c.get("/api/classes", params={"semester_id": semester["id"]}).json()) == 26
    )
    d = upload_csv(
        c,
        semester,
        "calendar",
        "title,start_date,end_date,kind\nHoliday,2020-01-06,2020-01-06,holiday\n",
    )
    assert (
        c.post(
            f"/api/documents/{d['id']}/confirm", json={"rows": d["preview"]["rows"]}
        ).status_code
        == 200
    )
    assert (
        c.get("/api/classes", params={"semester_id": semester["id"]}).json()[0][
            "status"
        ]
        == "cancelled"
    )


def test_login_throttle(client):
    for _ in range(12):
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "missing@example.com", "password": "SomePassword123"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "SomePassword123"},
        ).status_code
        == 429
    )


def test_explicit_baseline_correction_and_conflict(academic):
    c, semester, subject = academic
    d = upload_csv(
        c,
        semester,
        "attendance",
        "code,name,attended,conducted,through_date\nM101,Mathematics,8,10,2020-01-31\n",
    )
    c.post(f"/api/documents/{d['id']}/confirm", json={"rows": d["preview"]["rows"]})
    baseline = c.get("/api/baselines", params={"semester_id": semester["id"]}).json()[0]
    body = {
        "code": "M101",
        "name": "Mathematics",
        "attended": 9,
        "conducted": 10,
        "through_date": "2020-01-31",
    }
    assert c.put("/api/baselines/" + str(baseline["id"]), json=body).status_code == 200
    assert (
        c.get("/api/summary", params={"semester_id": semester["id"]}).json()["overall"][
            "percentage"
        ]
        == 90
    )
    occ = add_class(c, subject, "2020-02-03")
    c.put(
        "/api/attendance",
        json={"records": [{"occurrence_id": occ["id"], "status": "present"}]},
    )
    body["through_date"] = "2020-02-04"
    assert c.put("/api/baselines/" + str(baseline["id"]), json=body).status_code == 409
    assert (
        c.get("/api/summary", params={"semester_id": semester["id"]}).json()["overall"][
            "attended"
        ]
        == 10
    )


def test_edit_events_semesters_and_slots(academic):
    c, semester, subject = academic
    assert (
        c.put(
            "/api/semesters/" + str(semester["id"]),
            json={
                "name": "Renamed term",
                "start_date": "2020-01-01",
                "end_date": "2020-06-30",
            },
        ).status_code
        == 200
    )
    slot = c.post(
        "/api/timetable",
        json={
            "subject_id": subject["id"],
            "weekday": 0,
            "start_time": "09:00",
            "end_time": "10:00",
        },
    ).json()
    event = c.post(
        "/api/events",
        json={
            "semester_id": semester["id"],
            "title": "Holiday",
            "start_date": "2020-01-06",
            "end_date": "2020-01-06",
            "kind": "holiday",
        },
    ).json()
    assert (
        c.put(
            "/api/events/" + str(event["id"]),
            json={
                "semester_id": semester["id"],
                "title": "Moved holiday",
                "start_date": "2020-01-13",
                "end_date": "2020-01-13",
                "kind": "holiday",
            },
        ).status_code
        == 200
    )
    rows = c.get("/api/classes", params={"semester_id": semester["id"]}).json()
    assert rows[0]["status"] == "pending" and rows[1]["status"] == "cancelled"
    assert (
        c.put(
            "/api/timetable/" + str(slot["id"]),
            json={
                "subject_id": subject["id"],
                "weekday": 1,
                "start_time": "11:00",
                "end_time": "12:00",
            },
        ).status_code
        == 200
    )
    # Historic occurrences are preserved when recurring definitions change.
    rows = c.get("/api/classes", params={"semester_id": semester["id"]}).json()
    assert any(r["starts_at"] == "2020-01-06T09:00:00" for r in rows)
    assert not any(r["starts_at"] == "2020-01-07T11:00:00" for r in rows)
    # Editing a recurring definition must not create fictitious past classes,
    # including when the user explicitly regenerates the schedule later.
    c.post('/api/semesters/'+str(semester['id'])+'/generate')
    regenerated = c.get('/api/classes', params={'semester_id':semester['id']}).json()
    assert len(regenerated) == len(rows)
    assert (
        c.put(
            "/api/semesters/" + str(semester["id"]),
            json={
                "name": "Too short",
                "start_date": "2020-02-01",
                "end_date": "2020-06-30",
            },
        ).status_code
        == 409
    )


def test_future_slot_edit_preserves_manual_reschedule(account):
    today = datetime.now().date()
    start = today + timedelta(days=1)
    semester = account.post('/api/semesters', json={
        'name': 'Future term', 'start_date': str(start),
        'end_date': str(start + timedelta(days=20)),
    }).json()
    subject = account.post('/api/subjects', json={
        'semester_id': semester['id'], 'name': 'Physics', 'code': 'P101',
    }).json()
    slot = account.post('/api/timetable', json={
        'subject_id': subject['id'], 'weekday': start.weekday(),
        'start_time': '09:00', 'end_time': '10:00', 'room': 'A1',
    }).json()
    rows = account.get('/api/classes', params={'semester_id': semester['id']}).json()
    moved = rows[0]
    assert account.put('/api/classes/'+str(moved['id']), json={
        'subject_id': subject['id'], 'starts_at': str(start)+'T12:00',
        'ends_at': str(start)+'T13:00', 'room': 'Moved',
    }).status_code == 200
    assert account.put('/api/timetable/'+str(slot['id']), json={
        'subject_id': subject['id'], 'weekday': start.weekday(),
        'start_time': '09:00', 'end_time': '10:00', 'room': 'A2',
    }).status_code == 200
    account.post('/api/semesters/'+str(semester['id'])+'/generate')
    changed = account.get('/api/classes', params={'semester_id':semester['id']}).json()
    assert len(changed) == len(rows)
    assert any(r['id'] == moved['id'] and r['room'] == 'Moved' for r in changed)
    assert not any(r['starts_at'] == str(start)+'T09:00:00' for r in changed)
    account.delete('/api/timetable/'+str(slot['id']))
    remaining = account.get('/api/classes', params={'semester_id':semester['id']}).json()
    assert len(remaining) == 1 and remaining[0]['id'] == moved['id']

