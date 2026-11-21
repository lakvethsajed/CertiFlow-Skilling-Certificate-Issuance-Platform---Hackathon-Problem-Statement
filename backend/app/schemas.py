from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import BatchStatus, Decision


class RevisionDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(strict=True, gt=0)
    comment: str = Field(default="", max_length=2000)

    @field_validator("comment", mode="before")
    @classmethod
    def trim_comment(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RevisionDecisionCommand(RevisionDecisionRequest):
    decision: Decision

    @model_validator(mode="after")
    def require_reason(self) -> Self:
        if self.decision in {Decision.RETURN, Decision.REJECT} and not self.comment:
            raise ValueError("Enter a reason for this decision.")
        return self


# Preserve the schema names used by Phase 3.
QualityDecisionRequest = RevisionDecisionRequest
QualityDecisionCommand = RevisionDecisionCommand


class ReviewDecision(BaseModel):
    reviewer: str
    decision: Decision
    comment: str
    created_at: datetime
    revision: int


class QualityDashboard(BaseModel):
    pending: int = Field(ge=0)
    approved: int = Field(ge=0)
    returned: int = Field(ge=0)
    rejected: int = Field(ge=0)
    activity: list["QualityActivity"]


class QualityActivity(ReviewDecision):
    batch_id: str
    batch_name: str


class QualityQueueItem(BaseModel):
    batch_id: str
    revision: int
    name: str
    centre: str
    district: str
    course: str
    candidate_count: int = Field(ge=0)
    district_approval_count: int = Field(ge=0)
    status: BatchStatus
    submitted_at: datetime
    quality_queued_at: datetime | None


class QualityQueuePage(BaseModel):
    records: list[QualityQueueItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class QualityQueueQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: Literal["pending", "approved", "returned", "rejected", "history"] = "pending"
    search: str = Field(default="", max_length=250)
    course: str | None = Field(default=None, max_length=250)
    district: str | None = Field(default=None, max_length=250)
    sort: Literal["oldest", "newest"] = "oldest"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
