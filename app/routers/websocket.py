import json
from typing import Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
from app.config import get_settings
from app.database import engine
from app.models import User, RoomMember
from sqlmodel import Session, select

settings = get_settings()
router = APIRouter()


# ---- In-memory state ----
# room_id -> { user_id: { "ws": WebSocket, "username": str } }
room_connections: Dict[int, Dict[int, dict]] = {}

# room_id -> list of draw events (canvas history)
canvas_history: Dict[int, List[dict]] = {}


def verify_token_from_query(token: str) -> Optional[int]:
    """Verify JWT token from query parameter and return user_id."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        user_id = int(sub)
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user is None:
                return None
        return user_id
    except JWTError:
        return None


async def broadcast_to_room(room_id: int, message: dict, exclude_user_id: Optional[int] = None):
    """Send a message to all connections in a room."""
    connections = room_connections.get(room_id, {})
    dead = []
    for uid, conn in connections.items():
        if uid == exclude_user_id:
            continue
        try:
            await conn["ws"].send_text(json.dumps(message))
        except Exception:
            dead.append(uid)
    # Clean up dead connections
    for uid in dead:
        connections.pop(uid, None)
        print(f"[WS] Cleaned dead connection: user {uid} in room {room_id}")
    # If room is empty, clean up
    if not connections and room_id in room_connections:
        del room_connections[room_id]


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, token: str = Query(...)):
    # ---- Authenticate ----
    user_id = verify_token_from_query(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # ---- Check if user is a member of this room ----
    with Session(engine) as session:
        membership = session.exec(
            select(RoomMember).where(
                RoomMember.room_id == room_id,
                RoomMember.user_id == user_id
            )
        ).first()
        if not membership:
            await websocket.close(code=4003, reason="Not a member of this room")
            return

        user = session.get(User, user_id)
        username = user.username

    # ---- Accept connection ----
    await websocket.accept()
    connection = {"ws": websocket, "username": username}

    if room_id not in room_connections:
        room_connections[room_id] = {}
    room_connections[room_id][user_id] = connection

    # ---- Send canvas history to new joiner ----
    if room_id in canvas_history and canvas_history[room_id]:
        try:
            await websocket.send_text(json.dumps({
                "type": "canvas_history",
                "drawings": canvas_history[room_id]
            }))
            print(f"[WS] Sent {len(canvas_history[room_id])} drawing events to {username}")
        except Exception:
            pass

    # Tell everyone someone joined
    await broadcast_to_room(room_id, {
        "type": "user_joined",
        "user_id": user_id,
        "username": username,
        "users": [
            {"user_id": uid, "username": c["username"]}
            for uid, c in room_connections[room_id].items()
        ]
    })

    print(f"[WS] {username} joined room {room_id}")

    # ---- Main message loop ----
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "draw":
                # Store in canvas history
                if room_id not in canvas_history:
                    canvas_history[room_id] = []
                canvas_history[room_id].append(data)

                # Keep history manageable (last 5000 events)
                if len(canvas_history[room_id]) > 5000:
                    canvas_history[room_id] = canvas_history[room_id][-5000:]

                # Broadcast drawing data to everyone else in the room
                await broadcast_to_room(room_id, {
                    "type": "draw",
                    "user_id": user_id,
                    "username": username,
                    "x1": data.get("x1"),
                    "y1": data.get("y1"),
                    "x2": data.get("x2"),
                    "y2": data.get("y2"),
                    "color": data.get("color"),
                    "size": data.get("size"),
                    "tool": data.get("tool", "pen")
                }, exclude_user_id=user_id)

            elif msg_type == "pong":
                # Client responded to ping, connection is alive
                pass

    except WebSocketDisconnect:
        print(f"[WS] {username} disconnected from room {room_id}")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        # ---- Cleanup ----
        connections = room_connections.get(room_id, {})
        connections.pop(user_id, None)

        # Notify others
        await broadcast_to_room(room_id, {
            "type": "user_left",
            "user_id": user_id,
            "username": username,
            "users": [
                {"user_id": uid, "username": c["username"]}
                for uid, c in connections.items()
            ]
        })

        if not connections and room_id in room_connections:
            del room_connections[room_id]


# ---- Helper: broadcast game events (called from game router) ----
async def broadcast_game_event(room_id: int, event_type: str, data: dict):
    """Broadcast a game event to all connections in a room."""
    message = {"type": event_type, **data}
    await broadcast_to_room(room_id, message)
