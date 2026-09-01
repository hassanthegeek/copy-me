from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from app.models import Role, GameStatus


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


# ---- Game Schemas ----
class GameCreate(BaseModel):
    total_rounds: int = 3


class GameResponse(BaseModel):
    id: int
    room_id: int
    status: GameStatus
    current_round: int
    total_rounds: int
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class RoundResponse(BaseModel):
    id: int
    game_id: int
    drawer_id: int
    prompt: str
    winner_id: Optional[int]
    round_number: int
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScoreResponse(BaseModel):
    id: int
    game_id: int
    user_id: int
    points: int
    created_at: datetime

    class Config:
        from_attributes = True


class ScoreboardResponse(BaseModel):
    user_id: int
    username: str
    points: int
