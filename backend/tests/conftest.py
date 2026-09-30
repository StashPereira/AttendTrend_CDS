import os
import tempfile

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db")
)
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="attendtrend-test-uploads-")
import pytest
from fastapi.testclient import TestClient
from app.db import engine, Base
from app.main import app
from app import models


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def register(c, email="student@example.com"):
    r = c.post(
        "/api/auth/signup",
        json={"name": "Student", "email": email, "password": "LongPassword!123"},
    )
    assert r.status_code == 201, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    return r.json()


@pytest.fixture
def account(client):
    register(client)
    return client


@pytest.fixture
def academic(account):
    semester = account.post(
        "/api/semesters",
        json={"name": "Term", "start_date": "2020-01-01", "end_date": "2020-06-30"},
    ).json()
    subject = account.post(
        "/api/subjects",
        json={
            "semester_id": semester["id"],
            "code": "M101",
            "name": "Mathematics",
            "instructor": "Dr Teacher",
            "kind": "theory",
        },
    ).json()
    return account, semester, subject
