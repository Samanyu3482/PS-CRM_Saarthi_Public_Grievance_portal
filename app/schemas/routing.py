from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class DepartmentSchema(BaseModel):
    id: str = Field(alias="_id")
    ministry: str
    department: str
    sub_departments: list[str] = []

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class OfficerSchema(BaseModel):
    id: str = Field(alias="_id")
    name: str
    email: EmailStr
    phone: str
    ministry: str
    department: str
    sub_department: Optional[str] = None
    city: str
    state: str
    employee_id: str
    current_workload: int

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }
