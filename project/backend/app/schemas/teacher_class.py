from pydantic import BaseModel, ConfigDict


class TeacherClassBind(BaseModel):
    teacher_id: str
    class_id: str


class TeacherClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    teacher_id: str
    class_id: str
