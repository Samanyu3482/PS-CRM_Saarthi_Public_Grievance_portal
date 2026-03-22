from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal, Union, Annotated
from enum import Enum

class RoleEnum(str, Enum):
    citizen = "citizen"
    officer = "officer"
    ministry = "ministry"
    mp_mla = "mp_mla"

class UserBase(BaseModel):
    auth0_id: str
    name: str
    email: EmailStr
    phone: str

class Citizen(UserBase):
    role: Literal[RoleEnum.citizen]
    address: str
    city: str
    state: str
    pincode: str

class Officer(UserBase):
    role: Literal[RoleEnum.officer]
    department: str
    city: str
    employee_id: str

class Ministry(UserBase):
    role: Literal[RoleEnum.ministry]
    ministry_name: str
    designation: str
    employee_id: str

class MpMla(UserBase):
    role: Literal[RoleEnum.mp_mla]
    constituency: str
    state: str
    party_name: str

# Polymorphic validation schema based on 'role'
UserCreate = Annotated[Union[Citizen, Officer, Ministry, MpMla], Field(discriminator="role")]

class UserInDB(BaseModel):
    id: str = Field(alias="_id")
    auth0_id: str
    role: RoleEnum
    name: str
    email: EmailStr
    phone: str
    
    class Config:
        populate_by_name = True
        extra = "allow"
