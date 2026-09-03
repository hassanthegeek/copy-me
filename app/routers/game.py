from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import engine
from app.models import Room
from app.models import Game, Round, Score, GameStatus, User, RoomMember
from app.schemas import GameCreate, GameResponse, RoundResponse, ScoreResponse, ScoreboardResponse
from app.auth import get_current_user
from app.words import get_random_prompt
from app.routers.websocket import canvas_locked_by

router = APIRouter(prefix="/rooms", tags=["Game"])


def schedule_broadcast(room_id: int, event_type: str, data: dict):
    """Queue a WebSocket broadcast from a sync context."""
    try:
        from app.routers.websocket import broadcast_game_event_sync
        broadcast_game_event_sync(room_id, event_type, data)
    except Exception as e:
        print(f"[GAME] Broadcast failed: {e}")


def clear_canvas_history(room_id: int):
    """Clear canvas history when a new round starts."""
    try:
        from app.routers.websocket import canvas_history
        canvas_history.pop(room_id, None)
    except Exception:
        pass


def get_room_members(room_id: int, session: Session) -> List[int]:
    """Get all user IDs in a room."""
    members = session.exec(
        select(RoomMember).where(RoomMember.room_id == room_id)
    ).all()
    return [m.user_id for m in members]


def get_or_create_score(game_id: int, user_id: int, session: Session) -> Score:
    """Get existing score or create new one for a player."""
    score = session.exec(
        select(Score).where(
            Score.game_id == game_id,
            Score.user_id == user_id
        )
    ).first()
    
    if not score:
        score = Score(game_id=game_id, user_id=user_id, points=0)
        session.add(score)
        session.commit()
        session.refresh(score)
    
    return score


@router.post("/{room_id}/game/start", response_model=GameResponse)
def start_game(room_id: int, current_user: User = Depends(get_current_user)):
    """Start a new game in a room. Only room creator can start."""
    with Session(engine) as session:
        # Check if user is member of room
        room = session.get(Room, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if room.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only the room creator can start the game")
        
        # Check if there's already an active game
        active_game = session.exec(
            select(Game).where(
                Game.room_id == room_id,
                Game.status == GameStatus.ACTIVE
            )
        ).first()
        if active_game:
            raise HTTPException(status_code=400, detail="Game already in progress")
        
        # Get all members
        member_ids = get_room_members(room_id, session)
        if len(member_ids) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 players to start")
        
        # Create new game
        game = Game(
            room_id=room_id,
            status=GameStatus.ACTIVE,
            current_round=1,
            total_rounds=3,
            created_by=current_user.id
        )
        session.add(game)
        session.commit()
        session.refresh(game)
        
        # Create first round - first member is the drawer
        prompt = get_random_prompt()
        first_drawer_id = member_ids[0]
        
        round_obj = Round(
            game_id=game.id,
            drawer_id=first_drawer_id,
            prompt=prompt,
            round_number=1
        )
        session.add(round_obj)
        
        # Initialize scores for all players
        for uid in member_ids:
            score = Score(game_id=game.id, user_id=uid, points=0)
            session.add(score)
        
        session.commit()
        session.refresh(game)
        
        print(f"[GAME] Started game {game.id} in room {room_id}")
        print(f"[GAME] Round 1: Drawer={first_drawer_id}, Prompt={prompt}")
        
        # Clear canvas for new game
        clear_canvas_history(room_id)

        # Lock canvas to the first drawer
        canvas_locked_by[room_id] = first_drawer_id
        
        # Build scoreboard
        scores = session.exec(select(Score).where(Score.game_id == game.id)).all()
        scoreboard = []
        for score in scores:
            user = session.get(User, score.user_id)
            if user:
                scoreboard.append({"user_id": user.id, "username": user.username, "points": score.points})
        
        drawer = session.get(User, first_drawer_id)
        
        # Broadcast game_started event to all users via WebSocket
        schedule_broadcast(room_id, "game_started", {
            "game_id": game.id,
            "current_round": 1,
            "total_rounds": game.total_rounds,
            "drawer_id": first_drawer_id,
            "drawer_name": drawer.username if drawer else "Unknown",
            "prompt": prompt,  # Will only be shown to drawer by frontend
            "scoreboard": scoreboard,
            "created_by": current_user.id
        })
        
        return game


@router.get("/{room_id}/game/status")
def get_game_status(room_id: int, current_user: User = Depends(get_current_user)):
    """Get current game status including round info and scores."""
    with Session(engine) as session:
        # Get active game
        game = session.exec(
            select(Game).where(
                Game.room_id == room_id,
                Game.status == GameStatus.ACTIVE
            )
        ).first()
        
        if not game:
            return {"status": "no_active_game"}
        
        # Auto-finish games stuck for more than 10 minutes
        from datetime import datetime, timedelta
        if game.created_at and (datetime.utcnow() - game.created_at) > timedelta(minutes=2):
            game.status = GameStatus.FINISHED
            session.add(game)
            session.commit()
            return {"status": "no_active_game"}
        
        # Get current round
        current_round = session.exec(
            select(Round).where(
                Round.game_id == game.id,
                Round.round_number == game.current_round
            )
        ).first()
        
        # Get scores
        scores = session.exec(
            select(Score).where(Score.game_id == game.id)
        ).all()
        
        scoreboard = []
        for score in scores:
            user = session.get(User, score.user_id)
            if user:
                scoreboard.append({
                    "user_id": user.id,
                    "username": user.username,
                    "points": score.points
                })
        
        # Sort by points descending
        scoreboard.sort(key=lambda x: x["points"], reverse=True)
        
        # Check if current user is the drawer
        is_drawer = current_round.drawer_id == current_user.id if current_round else False
        
        # Get drawer name
        drawer = session.get(User, current_round.drawer_id) if current_round else None
        drawer_name = drawer.username if drawer else "Unknown"
        
        return {
            "game_id": game.id,
            "status": game.status,
            "current_round": game.current_round,
            "total_rounds": game.total_rounds,
            "round": {
                "drawer_id": current_round.drawer_id,
                "drawer_name": drawer_name,
                "prompt": current_round.prompt if is_drawer else None,  # Only show to drawer
                "round_number": current_round.round_number,
                "winner_id": current_round.winner_id,
                "started_at": current_round.started_at.isoformat() if current_round else None
            },
            "scoreboard": scoreboard,
            "is_drawer": is_drawer
        }


@router.post("/{room_id}/game/guess")
def submit_guess(room_id: int, guess: str, current_user: User = Depends(get_current_user)):
    """Submit a guess for the current round."""
    with Session(engine) as session:
        # Get active game
        game = session.exec(
            select(Game).where(
                Game.room_id == room_id,
                Game.status == GameStatus.ACTIVE
            )
        ).first()
        
        if not game:
            raise HTTPException(status_code=400, detail="No active game")
        
        # Get current round
        current_round = session.exec(
            select(Round).where(
                Round.game_id == game.id,
                Round.round_number == game.current_round
            )
        ).first()
        
        if not current_round:
            raise HTTPException(status_code=400, detail="No current round")
        
        # Can't guess your own drawing
        if current_round.drawer_id == current_user.id:
            raise HTTPException(status_code=400, detail="Can't guess your own drawing")
        
        # Already won this round?
        if current_round.winner_id:
            raise HTTPException(status_code=400, detail="Round already finished")
        
        # Check if timer has expired (60 seconds per round)
        time_elapsed = (datetime.utcnow() - current_round.started_at).total_seconds()
        if time_elapsed > 60:
            raise HTTPException(status_code=400, detail="Time is up! Round has ended.")
        
        # Check if guess is correct (case-insensitive)
        is_correct = guess.strip().lower() == current_round.prompt.lower()
        
        if is_correct:
            # Mark winner
            current_round.winner_id = current_user.id
            current_round.ended_at = datetime.utcnow()
            session.add(current_round)
            
            # Fixed points: guesser +5, drawer +6
            guesser_points = 5
            drawer_points = 6
            
            # Award points
            guesser_score = get_or_create_score(game.id, current_user.id, session)
            guesser_score.points += guesser_points
            
            drawer_score = get_or_create_score(game.id, current_round.drawer_id, session)
            drawer_score.points += drawer_points
            
            session.commit()
            
            print(f"[GAME] {current_user.username} guessed '{current_round.prompt}' correctly!")
            print(f"[GAME] +{guesser_points} points to guesser, +{drawer_points} to drawer")
            
            # Build updated scoreboard
            scores = session.exec(select(Score).where(Score.game_id == game.id)).all()
            scoreboard = []
            for score in scores:
                user = session.get(User, score.user_id)
                if user:
                    scoreboard.append({"user_id": user.id, "username": user.username, "points": score.points})
            scoreboard.sort(key=lambda x: x["points"], reverse=True)
            
            # Broadcast correct guess to all users
            schedule_broadcast(room_id, "guess_correct", {
                "user_id": current_user.id,
                "username": current_user.username,
                "prompt": current_round.prompt,
                "guesser_points": guesser_points,
                "drawer_points": drawer_points,
                "scoreboard": scoreboard,
                "round_number": current_round.round_number
            })
            
            return {
                "correct": True,
                "prompt": current_round.prompt,
                "guesser_points": guesser_points,
                "drawer_points": drawer_points,
                "winner": current_user.username
            }
        else:
            # Broadcast wrong guess to all users
            schedule_broadcast(room_id, "guess_wrong", {
                "user_id": current_user.id,
                "username": current_user.username,
                "guess": guess
            })
            
            return {
                "correct": False,
                "guess": guess
            }


@router.post("/{room_id}/game/next-round")
def next_round(room_id: int, current_user: User = Depends(get_current_user)):
    """Move to the next round. Can only be called after round ends."""
    with Session(engine) as session:
        # Get active game
        game = session.exec(
            select(Game).where(
                Game.room_id == room_id,
                Game.status == GameStatus.ACTIVE
            )
        ).first()
        
        if not game:
            raise HTTPException(status_code=400, detail="No active game")
        
        # Get current round
        current_round = session.exec(
            select(Round).where(
                Round.game_id == game.id,
                Round.round_number == game.current_round
            )
        ).first()
        
        if not current_round:
            raise HTTPException(status_code=400, detail="No current round")
        
        # Check if current round has ended
        if not current_round.winner_id:
            raise HTTPException(status_code=400, detail="Current round hasn't ended yet")
        
        # Check if game is over
        if game.current_round >= game.total_rounds:
            game.status = GameStatus.FINISHED
            session.add(game)
            session.commit()
            
            # Build final scoreboard
            scores = session.exec(select(Score).where(Score.game_id == game.id)).all()
            scoreboard = []
            for score in scores:
                user = session.get(User, score.user_id)
                if user:
                    scoreboard.append({"user_id": user.id, "username": user.username, "points": score.points})
            scoreboard.sort(key=lambda x: x["points"], reverse=True)
            winner = scoreboard[0] if scoreboard else None
            
            # Unlock canvas when game ends
            canvas_locked_by.pop(room_id, None)

            # Broadcast game over
            schedule_broadcast(room_id, "game_over", {
                "game_id": game.id,
                "scoreboard": scoreboard,
                "winner": winner
            })
            
            print(f"[GAME] Game {game.id} finished!")
            return {"status": "game_over", "message": "All rounds completed"}
        
        # Get all members for drawer rotation
        member_ids = get_room_members(room_id, session)
        
        # Find next drawer (cycle through members)
        current_drawer_index = member_ids.index(current_round.drawer_id) if current_round.drawer_id in member_ids else 0
        next_drawer_index = (current_drawer_index + 1) % len(member_ids)
        next_drawer_id = member_ids[next_drawer_index]
        
        # Create next round
        new_round_number = game.current_round + 1
        used_prompts = [r.prompt for r in session.exec(select(Round).where(Round.game_id == game.id)).all()]
        prompt = get_random_prompt(used_prompts)
        
        new_round = Round(
            game_id=game.id,
            drawer_id=next_drawer_id,
            prompt=prompt,
            round_number=new_round_number
        )
        session.add(new_round)
        
        # Update game
        game.current_round = new_round_number
        session.add(game)
        
        session.commit()
        
        # Clear canvas for new round
        clear_canvas_history(room_id)

        # Lock canvas to new drawer
        canvas_locked_by[room_id] = next_drawer_id
        
        # Build scoreboard
        scores = session.exec(select(Score).where(Score.game_id == game.id)).all()
        scoreboard = []
        for score in scores:
            user = session.get(User, score.user_id)
            if user:
                scoreboard.append({"user_id": user.id, "username": user.username, "points": score.points})
        scoreboard.sort(key=lambda x: x["points"], reverse=True)
        
        drawer = session.get(User, next_drawer_id)
        
        # Broadcast new round to all users
        schedule_broadcast(room_id, "new_round", {
            "game_id": game.id,
            "round_number": new_round_number,
            "total_rounds": game.total_rounds,
            "drawer_id": next_drawer_id,
            "drawer_name": drawer.username if drawer else "Unknown",
            "prompt": prompt,  # Frontend will only show to drawer
            "scoreboard": scoreboard,
            "created_by": game.created_by
        })
        
        print(f"[GAME] Round {new_round_number}: Drawer={next_drawer_id}, Prompt={prompt}")
        
        return {
            "status": "new_round",
            "round_number": new_round_number,
            "drawer_id": next_drawer_id,
            "total_rounds": game.total_rounds
        }


@router.get("/{room_id}/game/scoreboard")
def get_scoreboard(room_id: int, current_user: User = Depends(get_current_user)):
    """Get final scoreboard for a finished game."""
    with Session(engine) as session:
        # Get any game (active or finished)
        game = session.exec(
            select(Game).where(Game.room_id == room_id).order_by(Game.id.desc())
        ).first()
        
        if not game:
            raise HTTPException(status_code=404, detail="No game found")
        
        # Get scores
        scores = session.exec(
            select(Score).where(Score.game_id == game.id)
        ).all()
        
        scoreboard = []
        for score in scores:
            user = session.get(User, score.user_id)
            if user:
                scoreboard.append({
                    "user_id": user.id,
                    "username": user.username,
                    "points": score.points
                })
        
        # Sort by points descending
        scoreboard.sort(key=lambda x: x["points"], reverse=True)
        
        # Find winner
        winner = scoreboard[0] if scoreboard else None
        
        return {
            "game_id": game.id,
            "status": game.status,
            "total_rounds": game.total_rounds,
            "scoreboard": scoreboard,
            "winner": winner
        }
