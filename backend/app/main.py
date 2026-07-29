"""FastAPI entry point for the pure Story System v3 demo."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .paths import ASSETS_DIR
from .routers import game, saves


app = FastAPI(title="Cycle Master API", version="0.4.0")

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(game.router)
app.include_router(saves.router)


@app.on_event("startup")
def on_startup() -> None:
    """Load the active v3 snapshot and initialize persistence tables."""

    game.story.refresh()
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
