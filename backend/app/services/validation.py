import re
from collections import Counter
from datetime import date
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Line = Annotated[str, StringConstraints(strip_whitespace=True, max_length=250)]
DateText = Annotated[str, StringConstraints(max_length=10)]


class BatchForm(BaseModel):
    name: Line
    course: Line
    trainer: Line
    startDate: DateText
    endDate: DateText
    assessmentDate: DateText
    description: str = Field(max_length=4000)
    centre: Line | None = None
    district: Line | None = None


class Student(BaseModel):
    rowNumber: int = Field(strict=True, ge=2, le=1_000_000)
    malformed: bool = False
    student_name: Line
    student_id: Line
    email: Line
    phone_number: Line
    course_name: Line
    marks: Line
    assessment_date: Line


class Upload(BaseModel):
    name: str = Field(max_length=255, pattern=r"\.[cC][sS][vV]$")
    size: int = Field(strict=True, ge=1, le=10_000_000)
    students: list[Student] = Field(min_length=1, max_length=5000)


class BatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form: BatchForm
    upload: Upload | None
    submit: bool = Field(strict=True)
    confirmed: bool = Field(strict=True)
    version: int | None = Field(default=None, strict=True, gt=0)


def valid_date(value: str) -> bool:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def inspect_batch(form: dict, students: list[dict]) -> dict:
    findings = []
    for field, label in (
        ("name", "Batch name"),
        ("course", "Course"),
        ("trainer", "Trainer"),
    ):
        if not form[field].strip():
            findings.append(f"{label} is required.")
    for field, label in (
        ("startDate", "Training start date"),
        ("endDate", "Training end date"),
        ("assessmentDate", "Assessment date"),
    ):
        if not valid_date(form[field]):
            findings.append(f"{label} is invalid.")
    if form["startDate"] > form["endDate"]:
        findings.append("Training end date precedes the start date.")
    if form["endDate"] > form["assessmentDate"]:
        findings.append("Assessment precedes the training end date.")
    if not students:
        findings.append("At least one candidate is required.")
    technical = []
    district = []
    ids = Counter(student["student_id"].lower() for student in students)
    for student in students:
        errors = []
        if student.get("malformed"):
            errors.append("Column count does not match the header.")
        if not student["student_name"]:
            errors.append("Student name is missing.")
        if not student["student_id"]:
            errors.append("Student ID is missing.")
        elif ids[student["student_id"].lower()] > 1:
            errors.append("Duplicate student ID.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", student["email"]):
            errors.append("Invalid email address.")
        if not re.fullmatch(
            r"(?:\+91)?[6-9][0-9]{9}", re.sub(r"[\s()-]", "", student["phone_number"])
        ):
            errors.append("Invalid phone number.")
        if not student["course_name"]:
            errors.append("Course name is missing.")
        elif (
            form["course"] and student["course_name"].lower() != form["course"].lower()
        ):
            errors.append("Course does not match the batch course.")
        if (
            not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", student["marks"])
            or float(student["marks"]) > 100
        ):
            errors.append("Marks must be between 0 and 100.")
        assessment = student["assessment_date"]
        if not valid_date(assessment):
            errors.append("Assessment date must be a valid YYYY-MM-DD date.")
        elif (
            valid_date(form["assessmentDate"]) and assessment != form["assessmentDate"]
        ):
            district.append(
                {
                    "rowNumber": student["rowNumber"],
                    "message": "Candidate assessment date differs from the batch assessment date.",
                }
            )
        if errors:
            technical.append({"rowNumber": student["rowNumber"], "errors": errors})
    return {
        "technical": technical,
        "batchFindings": findings,
        "districtFindings": district,
    }


def validate_upload(data: BatchInput) -> tuple[dict, list[dict]]:
    form = data.form.model_dump(exclude={"centre", "district"})
    students = (
        [student.model_dump() for student in data.upload.students]
        if data.upload
        else []
    )
    if len({student["rowNumber"] for student in students}) != len(students):
        raise HTTPException(422, "Candidate row numbers must be unique.")
    validation = inspect_batch(form, students)
    if validation["technical"] or (
        data.submit and (not data.confirmed or validation["batchFindings"])
    ):
        raise HTTPException(
            422,
            {
                "message": "Correct the validation findings and confirm the submission.",
                "details": validation,
            },
        )
    for student in students:
        student["email"] = student["email"].lower()
    return form, students
