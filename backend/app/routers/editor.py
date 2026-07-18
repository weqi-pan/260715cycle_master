# backend/app/routers/editor.py
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.story import StoryNode, Choice

router = APIRouter(prefix="/api/editor", tags=["editor"])


@router.get("/nodes")
def list_nodes(db: Session = Depends(get_db)):
    nodes = db.query(StoryNode).order_by(StoryNode.position, StoryNode.id).all()
    return {
        "nodes": [
            {
                "id": n.id, "name": n.name, "position": n.position,
                "node_type": n.node_type, "time_label": n.time_label,
                "content": n.content, "speaker": n.speaker, "background": n.background,
            }
            for n in nodes
        ]
    }


@router.post("/nodes")
def save_node(data: dict, db: Session = Depends(get_db)):
    node_id = data.get("id")
    if not node_id:
        raise HTTPException(400, "Missing node id")

    existing = db.query(StoryNode).filter(StoryNode.id == node_id).first()
    if existing:
        for k, v in data.items():
            if k != "id" and hasattr(existing, k):
                setattr(existing, k, v)
        db.commit()
        return {"status": "updated", "id": node_id}
    else:
        node = StoryNode(
            id=node_id,
            name=data.get("name", ""),
            position=data.get("position", 0.0),
            node_type=data.get("node_type", "normal"),
            time_label=data.get("time_label"),
            content=data.get("content", ""),
            speaker=data.get("speaker"),
            background=data.get("background"),
            cycle_variants_json=json.dumps(data.get("cycle_variants", {}), ensure_ascii=False),
            color_palette=data.get("color_palette"),
            atmosphere_json=json.dumps(data.get("atmosphere", []), ensure_ascii=False),
            sensory=data.get("sensory"),
        )
        db.add(node)
        db.commit()
        return {"status": "created", "id": node_id}


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str, db: Session = Depends(get_db)):
    db.query(Choice).filter(
        (Choice.from_node_id == node_id) | (Choice.next_node_id == node_id)
    ).delete()
    db.query(StoryNode).filter(StoryNode.id == node_id).delete()
    db.commit()
    return {"status": "deleted"}


@router.get("/choices/_all")
def list_all_choices(db: Session = Depends(get_db)):
    """Return ALL choices for graph edge rendering."""
    choices = db.query(Choice).order_by(Choice.priority).all()
    return {"choices": [_choice_to_dict(c) for c in choices]}


def _choice_to_dict(c: Choice) -> dict:
    return {
        "id": c.id, "from_node_id": c.from_node_id, "text": c.text,
        "short_text": c.short_text, "next_node_id": c.next_node_id,
        "condition": c.condition,
        "effects": json.loads(c.effects_json),
        "priority": c.priority, "hint": c.hint,
        "is_hidden_when_locked": bool(c.is_hidden_when_locked),
        "transition_text": c.transition_text,
    }


@router.get("/choices/{node_id}")
def list_choices(node_id: str, db: Session = Depends(get_db)):
    choices = db.query(Choice).filter(Choice.from_node_id == node_id).order_by(Choice.priority).all()
    return {"choices": [_choice_to_dict(c) for c in choices]}


@router.post("/choices")
def save_choice(data: dict, db: Session = Depends(get_db)):
    choice_id = data.get("id")
    if not choice_id:
        raise HTTPException(400, "Missing choice id")

    existing = db.query(Choice).filter(Choice.id == choice_id).first()
    if existing:
        existing.from_node_id = data.get("from_node_id", existing.from_node_id)
        existing.text = data.get("text", existing.text)
        existing.short_text = data.get("short_text", existing.short_text)
        existing.next_node_id = data.get("next_node_id", existing.next_node_id)
        existing.condition = data.get("condition", existing.condition)
        existing.effects_json = json.dumps(data.get("effects", []), ensure_ascii=False)
        existing.priority = data.get("priority", existing.priority)
        existing.hint = data.get("hint", existing.hint)
        existing.is_hidden_when_locked = 1 if data.get("is_hidden_when_locked") else 0
        existing.transition_text = data.get("transition_text", existing.transition_text)
        db.commit()
        return {"status": "updated"}
    else:
        choice = Choice(
            id=choice_id,
            from_node_id=data.get("from_node_id", ""),
            text=data.get("text", ""),
            short_text=data.get("short_text"),
            next_node_id=data.get("next_node_id", ""),
            condition=data.get("condition"),
            effects_json=json.dumps(data.get("effects", []), ensure_ascii=False),
            priority=data.get("priority", 99),
            hint=data.get("hint"),
            is_hidden_when_locked=1 if data.get("is_hidden_when_locked") else 0,
            transition_text=data.get("transition_text"),
        )
        db.add(choice)
        db.commit()
        return {"status": "created"}


@router.delete("/choices/{choice_id}")
def delete_choice(choice_id: str, db: Session = Depends(get_db)):
    db.query(Choice).filter(Choice.id == choice_id).delete()
    db.commit()
    return {"status": "deleted"}
