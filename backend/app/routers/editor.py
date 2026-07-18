# backend/app/routers/editor.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/editor", tags=["editor"])

# Phase 1: minimal stub — full editor in Phase 3
@router.get("/nodes")
def list_nodes():
    return {"nodes": [], "message": "Editor available in Phase 3"}
