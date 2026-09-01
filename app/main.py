from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.models import User, Room, RoomMember, Game, Round, Score
from app.routers import auth, rooms, websocket, game
from app.database import create_db_and_tables

app = FastAPI(
    title="Burhan's Drawing App",
    description="Real-time collaborative drawing app",
    version="1.0.0"
)

# Include routers
app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(websocket.router)
app.include_router(game.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
