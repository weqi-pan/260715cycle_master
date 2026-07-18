# backend/app/routers/saves.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/saves", tags=["saves"])

# Phase 1: minimal stub — full CRUD in Phase 2
@router.get("/")
def list_saves():
    return {"saves": [], "message": "Save system available in Phase 2"}
