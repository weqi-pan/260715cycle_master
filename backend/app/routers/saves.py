# backend/app/routers/saves.py
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.save import Save
from ..schemas.game import GameState

router = APIRouter(prefix="/api/saves", tags=["saves"])

def _now():
    return datetime.now().isoformat()


@router.get("/")
def list_saves(db: Session = Depends(get_db)):
    saves = db.query(Save).order_by(Save.updated_at.desc()).all()
    return {
        "saves": [
            {
                "id": s.id,
                "save_name": s.save_name,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "current_node_id": s.current_node_id,
                "cycle_count": s.cycle_count,
            }
            for s in saves
        ]
    }


@router.post("/")
def create_save(name: str, state: GameState, db: Session = Depends(get_db)):
    sid = str(uuid.uuid4())[:8]
    now = _now()
    save = Save(
        id=sid,
        save_name=name,
        created_at=now,
        updated_at=now,
        current_node_id=state.current_node_id,
        cycle_count=state.cycle_count,
        half_cycle_count=state.half_cycle_count,
        inventory_json=json.dumps(state.inventory, ensure_ascii=False),
        flags_json=json.dumps(state.flags, ensure_ascii=False),
        visited_nodes_json=json.dumps(state.visited_nodes, ensure_ascii=False),
        player_attributes_json=json.dumps(state.player_attributes, ensure_ascii=False),
        endings_reached_json=json.dumps(state.endings_reached, ensure_ascii=False),
    )
    db.add(save)
    db.commit()
    return {"id": sid, "save_name": name, "created_at": now}


@router.put("/{save_id}")
def update_save(save_id: str, state: GameState, db: Session = Depends(get_db)):
    save = db.query(Save).filter(Save.id == save_id).first()
    if not save:
        raise HTTPException(404, "Save not found")
    save.current_node_id = state.current_node_id
    save.cycle_count = state.cycle_count
    save.half_cycle_count = state.half_cycle_count
    save.inventory_json = json.dumps(state.inventory, ensure_ascii=False)
    save.flags_json = json.dumps(state.flags, ensure_ascii=False)
    save.visited_nodes_json = json.dumps(state.visited_nodes, ensure_ascii=False)
    save.player_attributes_json = json.dumps(state.player_attributes, ensure_ascii=False)
    save.endings_reached_json = json.dumps(state.endings_reached, ensure_ascii=False)
    save.updated_at = _now()
    db.commit()
    return {"status": "ok"}


@router.delete("/{save_id}")
def delete_save(save_id: str, db: Session = Depends(get_db)):
    save = db.query(Save).filter(Save.id == save_id).first()
    if not save:
        raise HTTPException(404, "Save not found")
    db.delete(save)
    db.commit()
    return {"status": "ok"}


@router.get("/load/{save_id}")
def load_save(save_id: str, db: Session = Depends(get_db)):
    save = db.query(Save).filter(Save.id == save_id).first()
    if not save:
        raise HTTPException(404, "Save not found")
    return GameState(
        current_node_id=save.current_node_id,
        cycle_count=save.cycle_count,
        half_cycle_count=save.half_cycle_count,
        inventory=json.loads(save.inventory_json),
        flags=json.loads(save.flags_json),
        visited_nodes=json.loads(save.visited_nodes_json),
        endings_reached=json.loads(save.endings_reached_json),
        player_attributes=json.loads(save.player_attributes_json),
    )
