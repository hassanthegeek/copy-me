
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Role(str, PyEnum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


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
