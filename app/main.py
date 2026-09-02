from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.models import User, Room, RoomMember, Game, Round, Score
from app.routers import auth, rooms, websocket, game
from app.database import create_db_and_tables, engine

app = FastAPI(
    title="Burhan's Drawing App",
    description="Real-time collaborative drawing app",
    version="1.0.0"
)

# CORS - allow all origins for LAN access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(websocket.router)
app.include_router(game.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.on_event("startup")
def on_startup():
    from sqlmodel import Session, select
    from app.models import Game, GameStatus
    
    create_db_and_tables()
    
    # Clean up any stuck active games from previous sessions
    with Session(engine) as session:
        active_games = session.exec(select(Game).where(Game.status == GameStatus.ACTIVE)).all()
        for game in active_games:
            game.status = GameStatus.FINISHED
        session.commit()
        if active_games:
            print(f"Cleaned up {len(active_games)} stuck game(s) from previous session")


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
