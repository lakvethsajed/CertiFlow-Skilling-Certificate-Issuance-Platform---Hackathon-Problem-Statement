from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete

from app.dependencies import CandidateActor, Db, require_session
from app.models import Session as LoginSession
from app.services.authentication import (
    Credentials,
    authenticate,
    clear_session_cookie,
    start_session,
)
from app.services.student_auth import change_password
from app.student_schemas import StudentPasswordChange, StudentUser

router = APIRouter(prefix="/student/auth", tags=["Student authentication"])
CurrentSession = Annotated[LoginSession, Depends(require_session)]


@router.post("/login")
def login(
    data: Credentials, request: Request, response: Response, db: Db
) -> StudentUser:
    user = authenticate(db, request, data, student=True)
    start_session(db, response, user)
    return StudentUser(id=user.id, name=user.name, email=user.email, role=user.role)


@router.post("/change-password", status_code=204)
def update_password(
    data: StudentPasswordChange, db: Db, actor: CandidateActor, session: CurrentSession
) -> Response:
    change_password(db, actor.id, session.id, data)
    return clear_session_cookie()


@router.post("/logout", status_code=204)
def logout(db: Db, _actor: CandidateActor, session: CurrentSession) -> Response:
    db.execute(delete(LoginSession).where(LoginSession.id == session.id))
    db.commit()
    return clear_session_cookie()
