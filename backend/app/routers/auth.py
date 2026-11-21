from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete

from app.dependencies import Db, read_session, require_session
from app.models import Session as LoginSession
from app.services.authentication import (
    Credentials,
    authenticate,
    clear_session_cookie,
    start_session,
    user_data,
)

router = APIRouter(prefix="/auth")


@router.post("/login")
def login(data: Credentials, request: Request, response: Response, db: Db) -> dict:
    user = authenticate(db, request, data)
    start_session(db, response, user)
    return user_data(user)


@router.get("/session")
def optional_session(request: Request, db: Db) -> dict:
    session = read_session(request, db)
    return {"user": user_data(session.user) if session else None}


@router.get("/me")
def me(session: Annotated[LoginSession, Depends(require_session)]) -> dict:
    return user_data(session.user)


@router.post("/logout", status_code=204)
def logout(
    session: Annotated[LoginSession, Depends(require_session)], db: Db
) -> Response:
    db.execute(delete(LoginSession).where(LoginSession.id == session.id))
    db.commit()
    return clear_session_cookie()
