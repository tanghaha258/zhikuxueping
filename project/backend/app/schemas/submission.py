from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SubmissionCreate(BaseModel):
    task_id: str
    content: Optional[str] = None
    file_urls: list[str] = []


class SubmissionUpdate(BaseModel):
    content: Optional[str] = None
    file_urls: Optional[list[str]] = None
    status: Optional[str] = None
    score: Optional[int] = None
    comment: Optional[str] = None


class SubmissionResponse(BaseModel):
    id: str
    task_id: str
    student_id: str
    content: Optional[str] = None
    file_urls: Optional[list] = None
    status: str
    score: Optional[int] = None
    comment: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubmissionImportItem(BaseModel):
    student_id: str
    file_url: str
    content: Optional[str] = None


class SubmissionImportRequest(BaseModel):
    task_id: str
    items: list[SubmissionImportItem]
