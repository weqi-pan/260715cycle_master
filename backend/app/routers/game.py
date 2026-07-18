# backend/app/routers/game.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..engine.graph import GraphLoader
from ..engine.engine import GameEngine
from ..schemas.game import Frame, ChooseRequest, GameState, NodeData

router = APIRouter(prefix="/api/game", tags=["game"])
loader = GraphLoader()
engine = GameEngine()


def _get_graph(db: Session):
    """Load graph fresh per request (Phase 1 simplification)."""
    return loader.load_all(db)


def _start_frame(graph, state):
    """Special handler: /start is not from a choice, but initialization."""
    bundle = graph["A"]
    state.current_node_id = "A"
    available = engine.resolve_available_choices(graph, "A", state)
    return Frame(
        node=NodeData(
            id=bundle.id, name=bundle.name, node_type=bundle.node_type,
            position=bundle.position, time_label=bundle.time_label,
            content=engine._resolve_content(bundle, state),
            speaker=bundle.speaker, background=bundle.background,
        ),
        state=state,
        available_choices=available,
    )


@router.get("/start", response_model=Frame)
def start_game(db: Session = Depends(get_db)):
    graph = _get_graph(db)
    state = GameState(current_node_id="A")
    return _start_frame(graph, state)


@router.post("/choose/{node_id}", response_model=Frame)
def choose_action(node_id: str, req: ChooseRequest, db: Session = Depends(get_db)):
    graph = _get_graph(db)
    state = GameState(current_node_id=node_id)
    try:
        frame = engine.process_choice(graph, node_id, req.choice_id, state)
        return frame
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
