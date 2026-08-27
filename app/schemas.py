from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models import Role


# ---- Auth Schemas ----
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: Role
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Room Schemas ----
class RoomCreate(BaseModel):
    name: str


class RoomResponse(BaseModel):
    id: int
    name: str
    creator_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RoomMemberResponse(BaseModel):
    id: int
    room_id: int
    user_id: int
    joined_at: datetime

    class Config:
        from_attributes = True
