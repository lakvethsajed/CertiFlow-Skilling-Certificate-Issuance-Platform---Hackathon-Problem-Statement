from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database import create_database_engine
from app.models import Role, User
from app.models import Session as LoginSession

COOKIE = "certiflow_session"
SESSION_SECONDS = 8 * 60 * 60


def utc_now() -> datetime:
    return datetime.now(UTC)


def legacy_now() -> datetime:
    return utc_now().replace(tzinfo=None)


@lru_cache
def engine() -> Engine:
    return create_database_engine(settings().database_url.get_secret_value())


def get_db() -> Iterator[Session]:
    with Session(engine(), expire_on_commit=False) as db:
        yield db


Db = Annotated[Session, Depends(get_db)]


def read_session(request: Request, db: Session) -> LoginSession | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        claims = jwt.decode(
            token,
            settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer="certiflow",
            audience="certiflow-web",
            options={"require": ["exp", "sub", "jti"]},
        )
    except jwt.InvalidTokenError:
        return None
    session = db.get(LoginSession, claims["jti"])
    if (
        session
        and session.user_id == claims["sub"]
        and session.user.is_active
        and session.expires_at > legacy_now()
    ):
        return session
    return None


def require_session(request: Request, db: Db) -> LoginSession:
    session = read_session(request, db)
    if not session:
        raise HTTPException(401, "Please sign in.")
    return session


def require_role(role: Role) -> Callable:
    def authorize(session: Annotated[LoginSession, Depends(require_session)]) -> User:
        user = session.user
        if (
            user.role != role
            or (role == Role.DISTRICT_OFFICER and not user.district_id)
            or (role == Role.TRAINING_CENTRE and not user.centre_id)
            or (role == Role.CANDIDATE and not user.candidate_id)
        ):
            raise HTTPException(403, "This account does not have access.")
        return user

    return authorize


CentreActor = Annotated[User, Depends(require_role(Role.TRAINING_CENTRE))]
DistrictActor = Annotated[User, Depends(require_role(Role.DISTRICT_OFFICER))]
QualityActor = Annotated[User, Depends(require_role(Role.QUALITY_TEAM))]
StateActor = Annotated[User, Depends(require_role(Role.STATE_OFFICE))]
CandidateActor = Annotated[User, Depends(require_role(Role.CANDIDATE))]
