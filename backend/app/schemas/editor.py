# backend/app/schemas/editor.py
from pydantic import BaseModel
from typing import Optional
from .game import Effect


class NodeCreate(BaseModel):
    id: str
    name: str
    position: float
    node_type: str = "normal"
    time_label: Optional[str] = None
    content: str
    speaker: Optional[str] = None
    background: Optional[str] = None


class ChoiceCreate(BaseModel):
    id: str
    from_node_id: str
    text: str
    short_text: Optional[str] = None
    next_node_id: str
    condition: Optional[str] = None
    effects: list[Effect] = []
    priority: int = 99
    hint: Optional[str] = None
    is_hidden_when_locked: bool = False
