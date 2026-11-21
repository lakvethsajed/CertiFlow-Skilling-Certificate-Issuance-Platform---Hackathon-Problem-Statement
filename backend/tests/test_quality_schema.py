import os
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession

from app.database import create_database_engine
from app.models import (
    Batch,
    BatchRevision,
    Decision,
    District,
    QualityReview,
    Role,
    TrainingCentre,
    User,
)
from app.schemas import QualityDashboard, QualityDecisionCommand, QualityDecisionRequest


@pytest.mark.parametrize("decision", ["RETURN", "REJECT"])
def test_reason_required_for_negative_decision(decision: str) -> None:
    with pytest.raises(ValidationError, match="Enter a reason"):
        QualityDecisionCommand(revision=1, comment=" \t ", decision=decision)


def test_request_keeps_decision_out_of_body() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        QualityDecisionRequest.model_validate({"revision": 1, "decision": "APPROVE"})
    with pytest.raises(ValidationError, match="valid integer"):
        QualityDecisionRequest.model_validate({"revision": "1"})
    assert QualityDecisionCommand(revision=1, decision=Decision.APPROVE).comment == ""
    assert QualityDashboard(pending=0, approved=0, returned=0, rejected=0, activity=[])


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Provide a migrated test database"
)
def test_postgres_enforces_review_constraints() -> None:
    engine = create_database_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with DatabaseSession(engine) as session:
            district = District(id=str(uuid4()), name="Migration test district")
            centre = TrainingCentre(
                id=str(uuid4()), name="Migration test centre", district=district
            )
            batch = Batch(centre=centre)
            revision = BatchRevision(batch=batch, number=1, form={})
            reviewer = User(
                email=f"{uuid4()}@example.test",
                name="Migration test reviewer",
                password_hash="unused test value",
                role=Role.QUALITY_TEAM,
            )
            session.add_all([revision, reviewer])
            session.flush()

            with (
                pytest.raises(
                    IntegrityError, match="QualityReview_decision_comment_check"
                ),
                session.begin_nested(),
            ):
                session.add(
                    QualityReview(
                        revision_id=revision.id,
                        reviewer=reviewer,
                        decision=Decision.RETURN,
                        comment=" \n ",
                    )
                )
                session.flush()

            session.add(
                QualityReview(
                    revision_id=revision.id,
                    reviewer=reviewer,
                    decision=Decision.APPROVE,
                )
            )
            session.flush()

            another_reviewer = User(
                email=f"{uuid4()}@example.test",
                name="Second migration test reviewer",
                password_hash="unused test value",
                role=Role.QUALITY_TEAM,
            )
            session.add(another_reviewer)
            session.flush()
            with (
                pytest.raises(IntegrityError, match="QualityReview_pkey"),
                session.begin_nested(),
            ):
                session.add(
                    QualityReview(
                        revision_id=revision.id,
                        reviewer=another_reviewer,
                        decision=Decision.REJECT,
                        comment="Assessment requires review.",
                    )
                )
                session.flush()
            session.rollback()
    finally:
        engine.dispose()
