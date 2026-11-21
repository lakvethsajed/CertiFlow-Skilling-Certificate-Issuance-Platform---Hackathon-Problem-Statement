from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock
from time import monotonic

import bcrypt
import jwt
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import (
    COOKIE,
    SESSION_SECONDS,
    legacy_now,
    utc_now,
)
from app.models import Role, User
from app.models import Session as LoginSession

fallback_hash = bcrypt.hashpw(b"certiflow-invalid-login", bcrypt.gensalt(rounds=12))
attempts: dict[str, deque[float]] = defaultdict(deque)
attempts_lock = Lock()


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)


def user_data(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "districtId": user.district_id,
        "centreId": user.centre_id,
        "district": {"name": user.district.name} if user.district else None,
        "centre": {
            "name": user.centre.name,
            "district": {"name": user.centre.district.name},
        }
        if user.centre
        else None,
    }


def check_rate(request: Request, *, scope: str = "login") -> None:
    now = monotonic()
    host = request.client.host if request.client else "loopback"
    key = f"{scope}:{host}"
    with attempts_lock:
        for host, times in list(attempts.items()):
            while times and times[0] <= now - 900:
                times.popleft()
            if not times:
                del attempts[host]
        if len(attempts[key]) >= 30:
            raise HTTPException(429, "Too many attempts. Try again later.")
        attempts[key].append(now)


def authenticate(
    db: Session, request: Request, data: Credentials, *, student: bool = False
) -> User:
    check_rate(request)
    password = data.password.encode()
    if len(password) > 72:
        raise HTTPException(400, "Invalid credentials format.")
    query = select(User).where(User.email == data.email.strip().lower())
    user = db.scalar(query.with_for_update(of=User) if student else query)
    hashed = user.password_hash.encode() if user else fallback_hash
    if (
        not bcrypt.checkpw(password, hashed)
        or user is None
        or not user.is_active
        or (student and (user.role != Role.CANDIDATE or not user.candidate_id))
        or (not student and user.role == Role.CANDIDATE)
    ):
        raise HTTPException(401, "Email or password is incorrect.")
    return user


def start_session(db: Session, response: Response, user: User) -> None:
    session = LoginSession(
        user_id=user.id, expires_at=legacy_now() + timedelta(seconds=SESSION_SECONDS)
    )
    db.add(session)
    db.commit()
    token = jwt.encode(
        {
            "iss": "certiflow",
            "aud": "certiflow-web",
            "sub": user.id,
            "jti": session.id,
            "iat": utc_now(),
            "exp": utc_now() + timedelta(seconds=SESSION_SECONDS),
        },
        settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="strict",
        secure=settings().node_env == "production",
        path="/api",
    )


def clear_session_cookie() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE,
        path="/api",
        httponly=True,
        samesite="strict",
        secure=settings().node_env == "production",
    )
    return response
