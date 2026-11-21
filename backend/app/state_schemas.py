from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import BatchStatus
from app.schemas import ReviewDecision, RevisionDecisionCommand, RevisionDecisionRequest


class StateDecisionRequest(RevisionDecisionRequest):
    """The reviewer is resolved from the authenticated session."""


class StateDecisionCommand(RevisionDecisionCommand):
    """The service supplies the action from the route."""


class StateActivity(ReviewDecision):
    batch_id: str
    batch_name: str


class StateDashboard(BaseModel):
    pending: int = Field(ge=0)
    approved: int = Field(ge=0)
    returned: int = Field(ge=0)
    rejected: int = Field(ge=0)
    certificates_generated: int = Field(ge=0)
    certificates_pending: int = Field(ge=0)
    delayed: int = Field(ge=0)
    activity: list[StateActivity]


class StateQueueItem(BaseModel):
    batch_id: str
    revision: int = Field(gt=0)
    name: str
    centre: str
    district: str
    course: str
    candidate_count: int = Field(ge=0)
    district_approval_count: int = Field(ge=0)
    quality_status: Literal["NOT_REQUIRED", "APPROVED"]
    state_queued_at: datetime | None
    status: BatchStatus


class StateQueuePage(BaseModel):
    records: list[StateQueueItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class StateQueueQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: Literal[
        "pending", "approved", "returned", "rejected", "delayed", "history"
    ] = "pending"
    search: str = Field(default="", max_length=250)
    course: str | None = Field(default=None, max_length=250)
    district: str | None = Field(default=None, max_length=250)
    sort: Literal["oldest", "newest"] = "oldest"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class CertificateReadiness(BaseModel):
    final_approved: bool
    expected: int = Field(ge=0)
    generated: int = Field(ge=0)
    pending: int = Field(ge=0)
    failed: int = Field(ge=0)


class StateDecisionResult(BaseModel):
    batch_id: str
    revision: int = Field(gt=0)
    status: BatchStatus
    review: ReviewDecision
    issuance_requested: bool
