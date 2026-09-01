
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Role(str, PyEnum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class GameStatus(str, PyEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"


# ---- User Model ----
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: Role = Field(default=Role.USER)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    owned_rooms: List["Room"] = Relationship(back_populates="creator")
    memberships: List["RoomMember"] = Relationship(back_populates="user")


# ---- Room Model ----
class Room(SQLModel, table=True):
    __tablename__ = "rooms"

    id: Optional[int] = Field(primary_key=True)
    name: str
    creator_id: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    creator: Optional[User] = Relationship(back_populates="owned_rooms")
    members: List["RoomMember"] = Relationship(back_populates="room")


# ---- Room Member Model (junction table) ----
class RoomMember(SQLModel, table=True):
    __tablename__ = "room_members"

    id: Optional[int] = Field(primary_key=True)
    room_id: int = Field(foreign_key="rooms.id")
    user_id: int = Field(foreign_key="users.id")
    joined_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    room: Optional[Room] = Relationship(back_populates="members")
    user: Optional[User] = Relationship(back_populates="memberships")


# ---- Game Model ----
class Game(SQLModel, table=True):
    __tablename__ = "games"

    id: Optional[int] = Field(primary_key=True)
    room_id: int = Field(foreign_key="rooms.id")
    status: GameStatus = Field(default=GameStatus.WAITING)
    current_round: int = Field(default=0)
    total_rounds: int = Field(default=3)
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    rounds: List["Round"] = Relationship(back_populates="game")
    scores: List["Score"] = Relationship(back_populates="game")


# ---- Round Model ----
class Round(SQLModel, table=True):
    __tablename__ = "rounds"

    id: Optional[int] = Field(primary_key=True)
    game_id: int = Field(foreign_key="games.id")
    drawer_id: int = Field(foreign_key="users.id")
    prompt: str
    winner_id: Optional[int] = Field(foreign_key="users.id", default=None)
    round_number: int
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = Field(default=None)

    # Relationships
    game: Optional[Game] = Relationship(back_populates="rounds")


# ---- Score Model ----
class Score(SQLModel, table=True):
    __tablename__ = "scores"

    id: Optional[int] = Field(primary_key=True)
    game_id: int = Field(foreign_key="games.id")
    user_id: int = Field(foreign_key="users.id")
    points: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    game: Optional[Game] = Relationship(back_populates="scores")
