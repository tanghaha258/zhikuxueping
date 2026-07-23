from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SchoolCreate(BaseModel):
    name: str
    code: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class SchoolResponse(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ClassCreate(BaseModel):
    school_id: str
    grade: str
    name: str
    head_teacher_id: Optional[str] = None


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    grade: Optional[str] = None
    head_teacher_id: Optional[str] = None


class ClassResponse(BaseModel):
    id: str
    school_id: str
    grade: str
    name: str
    head_teacher_id: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
