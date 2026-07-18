# backend/app/schemas/game.py
from pydantic import BaseModel, Field
from typing import Optional, Any


class Effect(BaseModel):
    type: str
    target: str
    value: Any


class ChoiceResult(BaseModel):
    id: str
    text: str
    short_text: Optional[str] = None
    available: bool = True
    reason: Optional[str] = None
    source: str = "static"  # "static" | "special_shortcut" | "special_warp"


class GameState(BaseModel):
    current_node_id: str
    cycle_count: int = 0
    half_cycle_count: int = 0
    inventory: list[dict] = []
    flags: dict[str, Any] = {}
    visited_nodes: list[str] = []
    endings_reached: list[str] = []
    player_attributes: dict[str, int] = Field(default_factory=lambda: {"sanity": 100, "courage": 5, "insight": 3})
    persistent_nodes: dict[str, dict] = {}  # node_id -> {items: [...], dangers: [...]}


class NodeData(BaseModel):
    id: str
    name: str
    node_type: str
    position: float
    time_label: Optional[str] = None
    content: str
    speaker: Optional[str] = None
    speaker_avatar: Optional[str] = None
    background: Optional[str] = None
    ambient: Optional[str] = None


class PersistentFound(BaseModel):
    items: list[dict] = []
    cross_surface_items: list[dict] = []
    dangers: list[dict] = []


class Frame(BaseModel):
    node: NodeData
    state: GameState
    available_choices: list[ChoiceResult] = []
    persistent_found: PersistentFound = PersistentFound()
    cycle_event: Optional[dict] = None
    transition_text: Optional[str] = None
    scene_effects: list[dict] = []  # [{type: "notify"|"shake"|"flash", ...}]


class ChooseRequest(BaseModel):
    choice_id: str
    state: GameState


class SaveGameRequest(BaseModel):
    save_id: str
    state: GameState
