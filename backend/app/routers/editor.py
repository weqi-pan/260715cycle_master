"""直接读写剧情 JSON v2 的可视化编辑器 API。"""

from fastapi import APIRouter, HTTPException

from ..editor.story_repository import StoryV2Editor
from ..paths import DATA_DIR

router = APIRouter(prefix="/api/editor", tags=["editor"])
repository = StoryV2Editor(DATA_DIR / "story_data_v2" / "nodes")


@router.get("/nodes")
def list_nodes():
    return {"nodes": repository.list_nodes()}


@router.post("/nodes")
def save_node(data: dict):
    try:
        result = repository.save_node(data)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    try:
        result = repository.delete_node(node_id)
        return result
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.get("/choices/_all")
def list_all_choices():
    return {"choices": repository.list_choices()}


@router.get("/choices/{node_id}")
def list_choices(node_id: str):
    return {"choices": repository.list_choices(node_id)}


@router.post("/choices")
def save_choice(data: dict):
    try:
        result = repository.save_choice(data)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/choices/{choice_id}")
def delete_choice(choice_id: str):
    try:
        result = repository.delete_choice(choice_id)
        return result
    except ValueError as exc:
        raise HTTPException(404, str(exc))
