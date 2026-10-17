from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(default="User", min_length=1, max_length=150)
    fullName: Optional[str] = None
    role: UserRole = UserRole.PATIENT
    phone: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    full_name: Optional[str] = None
    fullName: Optional[str] = None
    role: UserRole = UserRole.PATIENT
    phone: Optional[str] = None
    dateOfBirth: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def check_names(cls, data: Any):
        if isinstance(data, dict):
            name = data.get("fullName") or data.get("full_name") or "User"
            data["full_name"] = name
            data["fullName"] = name
        return data


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    fullName: Optional[str] = None
    role: UserRole
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def sync_fullname(self):
        if not self.fullName:
            self.fullName = self.full_name
        return self


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
