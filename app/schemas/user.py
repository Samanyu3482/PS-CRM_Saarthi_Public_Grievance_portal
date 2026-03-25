from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal, Union, Annotated
from enum import Enum

class RoleEnum(str, Enum):
    citizen = "citizen"
    officer = "officer"
    ministry = "ministry"
    mp_mla = "mp_mla"
    mc = "mc"
    admin = "admin"

class UserBase(BaseModel):
<<<<<<< HEAD
    auth0_id: Optional[str] = None
=======
    firebase_uid: str
>>>>>>> 6fa47c536d999062837bd1ac7f11c90cf66ee66e
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

class McMember(UserBase):
    role: Literal[RoleEnum.mc]
    department: str
    city: str
    employee_id: str

# Polymorphic validation schema based on 'role'
UserCreate = Annotated[Union[Citizen, Officer, Ministry, MpMla, McMember], Field(discriminator="role")]

class UserSignupRequest(BaseModel):
    user_data: UserCreate
    password: Optional[str] = None
    id_token: Optional[str] = None

class UserInDB(BaseModel):
    id: str = Field(alias="_id")
    firebase_uid: str
    role: RoleEnum
    name: str
    email: EmailStr
    phone: str
    
    class Config:
        populate_by_name = True
        extra = "allow"
