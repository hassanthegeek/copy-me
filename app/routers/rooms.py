from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlmodel import Session, select
from app.database import engine
from app.models import Room, RoomMember, User
from app.schemas import RoomCreate, RoomResponse, RoomMemberResponse
from app.auth import get_current_user

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(room: RoomCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        new_room = Room(name=room.name, creator_id=current_user.id)
        session.add(new_room)
        session.commit()
        session.refresh(new_room)

        room_id = new_room.id
        room_name = new_room.name
        creator_id = new_room.creator_id
        room_created_at = new_room.created_at

        # Auto-add creator as a member
        membership = RoomMember(room_id=new_room.id, user_id=current_user.id)
        session.add(membership)
        session.commit()

        return {"id": room_id, "name": room_name, "creator_id": creator_id, "created_at": room_created_at}


@router.get("/", response_model=List[RoomResponse])
def list_rooms(current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        rooms = session.exec(select(Room)).all()
        return [{"id": r.id, "name": r.name, "creator_id": r.creator_id, "created_at": r.created_at} for r in rooms]


@router.post("/{room_id}/join", response_model=RoomMemberResponse)
def join_room(room_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        # Check if room exists
        room = session.get(Room, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        # Check if already a member
        existing = session.exec(
            select(RoomMember).where(
                RoomMember.room_id == room_id,
                RoomMember.user_id == current_user.id
            )
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Already a member of this room")

        membership = RoomMember(room_id=room_id, user_id=current_user.id)
        session.add(membership)
        session.commit()
        session.refresh(membership)
        return {"id": membership.id, "room_id": membership.room_id, "user_id": membership.user_id, "joined_at": membership.joined_at}


@router.get("/{room_id}/members", response_model=List[RoomMemberResponse])
def get_room_members(room_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        members = session.exec(
            select(RoomMember).where(RoomMember.room_id == room_id)
        ).all()
        return [{"id": m.id, "room_id": m.room_id, "user_id": m.user_id, "joined_at": m.joined_at} for m in members]


@router.delete("/{room_id}")
def delete_room(room_id: int, current_user: User = Depends(get_current_user)):
    """Delete a room. Only the creator can delete it."""
    with Session(engine) as session:
        room = session.get(Room, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        
        # Only creator can delete
        if room.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only the room creator can delete it")
        
        # Delete all members first
        members = session.exec(select(RoomMember).where(RoomMember.room_id == room_id)).all()
        for member in members:
            session.delete(member)
        
        # Delete the room
        session.delete(room)
        session.commit()
        
        return {"message": "Room deleted"}
