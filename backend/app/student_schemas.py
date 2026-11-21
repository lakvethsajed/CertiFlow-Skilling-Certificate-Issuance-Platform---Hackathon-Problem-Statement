from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models import Role

Token = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{43}$")]


class ActivationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActivationStudent(ActivationInput):
    student_id: str = Field(min_length=1, max_length=250)

    @field_validator("student_id", mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ActivationVerification(ActivationStudent):
    activation_code: str = Field(min_length=16, max_length=24)

    @field_validator("activation_code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class ActivationGrant(BaseModel):
    grant: Token


class NewPassword(ActivationInput):
    password: str = Field(min_length=12, max_length=72)
    confirm_password: str = Field(min_length=12, max_length=72)

    @model_validator(mode="after")
    def validate_password(self) -> "NewPassword":
        if len(self.password.encode()) > 72:
            raise ValueError("Password exceeds the 72-byte limit.")
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class ActivationPassword(NewPassword):
    grant: Token


class StudentPasswordChange(NewPassword):
    current_password: str = Field(min_length=1, max_length=72)


class StudentUser(BaseModel):
    id: str
    name: str
    email: str
    role: Role


class StudentProfile(BaseModel):
    student_id: str
    name: str
    email: str
    phone_number: str | None = None
    course: str | None = None
    total_issued: int = Field(ge=0)


class StudentCertificate(BaseModel):
    id: str
    number: str
    course: str
    assessment_date: str
    issued_at: datetime
    status: Literal["ACTIVE", "CANCELLED"]


class StudentCertificatePage(BaseModel):
    records: list[StudentCertificate]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
