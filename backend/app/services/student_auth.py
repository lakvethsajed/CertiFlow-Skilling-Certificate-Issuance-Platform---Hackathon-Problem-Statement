import bcrypt
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.dependencies import legacy_now
from app.models import Role, User
from app.models import Session as LoginSession
from app.student_schemas import StudentPasswordChange


def change_password(
    db: Session, user_id: str, session_id: str, data: StudentPasswordChange
) -> None:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update(of=User)
        .execution_options(populate_existing=True)
    )
    if (
        user is None
        or user.role != Role.CANDIDATE
        or not user.is_active
        or not user.candidate_id
    ):
        raise HTTPException(401, "Please sign in again.")
    current_session = db.scalar(
        select(LoginSession.id).where(
            LoginSession.id == session_id,
            LoginSession.user_id == user.id,
            LoginSession.expires_at > legacy_now(),
        )
    )
    if not current_session:
        raise HTTPException(401, "Please sign in again.")
    current = data.current_password.encode()
    if len(current) > 72 or not bcrypt.checkpw(current, user.password_hash.encode()):
        raise HTTPException(400, "Current password is incorrect.")
    if data.password == data.current_password:
        raise HTTPException(
            400, "Choose a password different from your current password."
        )

    user.password_hash = bcrypt.hashpw(
        data.password.encode(), bcrypt.gensalt(rounds=12)
    ).decode()
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    db.commit()
