"""Gameplay API backed exclusively by the Story System v3 runtime."""

from fastapi import APIRouter, HTTPException

from ..engine.effects_v3 import EffectExecutionError
from ..engine.engine import GameEngine
from ..engine.story_v3_repository import StoryV3Repository
from ..engine.turn_store import TurnStore
from ..paths import STORY_BUILD_DIR, STORY_V3_DIR
from ..schemas.game import ChooseRequest, Frame, GameState, TurnRequest


router = APIRouter(prefix="/api/game", tags=["game"])

story = StoryV3Repository(STORY_V3_DIR, STORY_BUILD_DIR)
engine = GameEngine()
turns = TurnStore()

_STALE_TURN_DETAIL = "Turn is stale or already consumed."


def _runtime_error(exc: ValueError) -> HTTPException | None:
    """Map known v3 validation failures to stable client responses."""

    detail = str(exc)
    if isinstance(exc, EffectExecutionError):
        if detail.startswith("Inventory removal would go below zero:"):
            return HTTPException(status_code=400, detail=detail)
        if detail.startswith("Missing entry attribute:"):
            return HTTPException(status_code=409, detail=detail)
        return None

    not_found_prefixes = (
        "Unknown story node:",
        "Unknown inventory item:",
        "Unknown persistent item:",
        "Unknown item:",
        "Item not in inventory:",
        "Node '",
        "Choice '",
    )
    conflict_prefixes = (
        "State node mismatch:",
        "Choice already selected under repeat policy:",
        "Terminal node has no exits:",
        "Crossing interaction limit reached:",
    )
    bad_request_prefixes = (
        "Choice is locked:",
        "Item cannot be discarded:",
        "Shortcut choice requires shortcut routing:",
        "Shortcut entry condition not met",
        "Shortcut target must be exit node:",
        "Shortcut entry must come from:",
        "Warp choice requires warp routing:",
        "Warp entry condition not met",
        "Warp target is not allowed:",
    )

    if detail.startswith(not_found_prefixes):
        status_code = 404
    elif detail.startswith(conflict_prefixes):
        status_code = 409
    elif detail.startswith(bad_request_prefixes):
        status_code = 400
    else:
        return None
    return HTTPException(status_code=status_code, detail=detail)


def _consume_turn(turn_id: str) -> GameState:
    state = turns.consume(turn_id)
    if state is None:
        raise HTTPException(status_code=409, detail=_STALE_TURN_DETAIL)
    return state


@router.get("/start", response_model=Frame)
def start_game() -> Frame:
    frame = engine.start(story.snapshot)
    frame.turn_id = turns.issue(frame.state)
    return frame


@router.post("/resume", response_model=Frame)
def resume_game(state: GameState) -> Frame:
    snapshot = story.snapshot
    try:
        frame = engine.resume(snapshot, state)
    except ValueError as exc:
        mapped = _runtime_error(exc)
        if mapped is None:
            raise
        raise mapped from exc
    frame.state.entry_attributes = {
        key: frame.state.player_attributes[key]
        for key in snapshot.project.attributes
    } | frame.state.entry_attributes
    frame.turn_id = turns.issue(frame.state)
    return frame


@router.post("/choose/{node_id}", response_model=Frame)
def choose_action(node_id: str, req: ChooseRequest) -> Frame:
    state = _consume_turn(req.turn_id)
    original_state = state.model_copy(deep=True)
    try:
        frame = engine.choose(
            story.snapshot,
            state,
            node_id=node_id,
            choice_id=req.choice_id,
        )
    except ValueError as exc:
        turns.restore(req.turn_id, original_state)
        mapped = _runtime_error(exc)
        if mapped is None:
            raise
        raise mapped from exc
    except Exception:
        turns.restore(req.turn_id, original_state)
        raise
    frame.turn_id = turns.issue(
        frame.state,
        previous_turn_id=req.turn_id,
    )
    return frame


@router.post("/inventory/discard/{item_id}", response_model=Frame)
def discard_inventory_item(item_id: str, req: TurnRequest) -> Frame:
    state = _consume_turn(req.turn_id)
    original_state = state.model_copy(deep=True)
    try:
        frame = engine.discard(
            story.snapshot,
            state,
            item_id=item_id,
        )
    except ValueError as exc:
        turns.restore(req.turn_id, original_state)
        mapped = _runtime_error(exc)
        if mapped is None:
            raise
        raise mapped from exc
    except Exception:
        turns.restore(req.turn_id, original_state)
        raise
    frame.turn_id = turns.issue(
        frame.state,
        previous_turn_id=req.turn_id,
    )
    return frame
