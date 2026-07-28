"""v2 JSON 编辑器仓库测试。"""

import json
from unittest.mock import Mock

import pytest

from app.editor.story_repository import StoryV2Editor
from app.routers import editor as editor_router
from app.routers import game


def write_node(root, node_id: str, target_id: str):
    payload = {
        "schema_version": 2,
        "id": node_id,
        "meta": {"name": node_id, "node_type": "main", "position": 0},
        "scene": {},
        "entry_sequences": [{
            "id": f"{node_id}.entry.default", "when": None, "priority": 0,
            "blocks": [{
                "id": f"{node_id}.entry.01", "type": "narration", "text": node_id,
                "speaker_id": None, "when": None,
            }],
        }],
        "choices": [{
            "id": f"{node_id}to{target_id}", "label": "前往", "condition": None,
            "locked_visibility": "hide", "repeat_policy": "once_per_visit",
            "priority": 1, "result_blocks": [], "effects": [],
            "next": {"node_id": target_id, "mode": "stay" if node_id == target_id else "travel"},
        }],
        "routing": {}, "authoring": {},
    }
    (root / f"{node_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@pytest.fixture
def editor(tmp_path):
    write_node(tmp_path, "A", "B")
    write_node(tmp_path, "B", "A")
    return StoryV2Editor(tmp_path)


def test_editor_lists_v2_nodes_and_choices(editor):
    assert [node["id"] for node in editor.list_nodes()] == ["A", "B"]
    assert {choice["id"] for choice in editor.list_choices()} == {"AtoB", "BtoA"}


def test_editor_updates_node_metadata_without_flattening_content_blocks(editor):
    result = editor.save_node({"id": "A", "name": "新名称", "position": 12})

    raw = json.loads((editor.root / "A.json").read_text(encoding="utf-8"))
    assert result["status"] == "updated"
    assert raw["meta"]["name"] == "新名称"
    assert raw["entry_sequences"][0]["blocks"][0]["id"] == "A.entry.01"


def test_editor_router_write_does_not_refresh_game_runtime(editor, monkeypatch):
    monkeypatch.setattr(editor_router, "repository", editor)
    refresh = Mock(side_effect=AssertionError("v3 runtime refresh was called"))
    monkeypatch.setattr(game.story, "refresh", refresh)

    result = editor_router.save_node({"id": "A", "name": "Updated", "position": 3})

    assert result["status"] == "updated"
    refresh.assert_not_called()


def test_editor_choice_write_updates_v2_file(editor):
    editor.save_choice({
        "id": "AtoB", "from_node_id": "A", "text": "去 B",
        "next_node_id": "B", "condition": None, "effects": [], "priority": 3,
        "repeat_policy": "once_ever",
    })

    raw = json.loads((editor.root / "A.json").read_text(encoding="utf-8"))
    assert raw["choices"][0]["label"] == "去 B"
    assert raw["choices"][0]["repeat_policy"] == "once_ever"
    assert raw["choices"][0]["locked_visibility"] == "hide"


@pytest.mark.parametrize("choice_id", ["../escape", "NUL"])
def test_editor_rejects_invalid_choice_ids(editor, choice_id):
    with pytest.raises(ValueError, match="invalid story id"):
        editor.save_choice({
            "id": choice_id,
            "from_node_id": "A",
            "next_node_id": "B",
        })


def test_editor_rejects_deleting_referenced_node(editor):
    with pytest.raises(ValueError, match="referenced"):
        editor.delete_node("B")

    assert (editor.root / "B.json").exists()


def test_v2_editor_cannot_write_outside_node_root(tmp_path):
    root = tmp_path / "nodes"
    root.mkdir()
    write_node(root, "A", "A")
    editor = StoryV2Editor(root)

    with pytest.raises(ValueError, match="invalid story id"):
        editor.save_node({"id": "../manifest", "name": "escape"})

    assert not (tmp_path / "manifest.json").exists()
