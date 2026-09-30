from datetime import timedelta
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select, delete, func
from .config import settings
from .db import get_db
from .models import AuthSession, User, LoginAttempt, utcnow

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (VerifyMismatchError, VerificationError):
        return False


def throttle(db, request, email):
    # Use socket peer, never trust arbitrary X-Forwarded-For. Configure trusted proxy in Uvicorn.
    peer = request.client.host if request.client else "unknown"
    cutoff = utcnow() - timedelta(minutes=15)
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    keys = [digest("ip:" + peer), digest("email:" + email.lower())]
    for key, limit in zip(keys, [80, 12]):
        count = db.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(LoginAttempt.key == key)
        )
        if count >= limit:
            db.commit()
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    for key in keys:
        db.add(LoginAttempt(key=key))
    db.commit()


def issue_session(db, response: Response, user):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=digest(token),
            user_id=user.id,
            csrf=csrf,
            expires=utcnow() + timedelta(hours=settings().session_hours),
        )
    )
    db.commit()
    response.set_cookie(
        "attendtrend_session",
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        max_age=settings().session_hours * 3600,
        path="/api",
    )
    return {"id": user.id, "email": user.email, "name": user.name, "csrf": csrf}


def current_user(request: Request, db=Depends(get_db)):
    token = request.cookies.get("attendtrend_session", "")
    session = db.get(AuthSession, digest(token)) if token else None
    if not session or session.expires <= utcnow():
        raise HTTPException(401, "Please sign in")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(
            request.headers.get("X-CSRF-Token", ""), session.csrf
        ):
            raise HTTPException(403, "Invalid CSRF token")
    request.state.auth_session = session
    return db.get(User, session.user_id)
