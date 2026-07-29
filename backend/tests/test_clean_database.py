"""Clean-database persistence tests.

Story content is published separately from player saves.  A new save database
must therefore accept validated story identifiers before any legacy story rows
exist.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.save import NodePersistentState
from app.models.story import StoryNode
from app.routers.saves import create_save, load_save
from app.schemas.game import GameState


def test_clean_database_can_create_and_load_save_without_story_rows(
    isolated_db_session,
    active_v3_story,
):
    state = GameState(current_node_id="A")

    created = create_save("clean install", state, isolated_db_session)
    loaded = load_save(created["id"], isolated_db_session)

    assert loaded.current_node_id == "A"
    assert isolated_db_session.query(StoryNode).count() == 0


def test_clean_database_can_store_node_state_without_story_rows(
    isolated_db_session,
    active_v3_story,
):
    state = GameState(
        current_node_id="A",
        persistent_nodes={
            "A": {
                "items": [{"id": "item_warning_note"}],
                "dangers": [],
            }
        },
    )

    created = create_save("node state", state, isolated_db_session)

    stored = (
        isolated_db_session.query(NodePersistentState)
        .filter(NodePersistentState.save_id == created["id"])
        .one()
    )
    assert stored.node_id == "A"
    assert isolated_db_session.query(StoryNode).count() == 0


def test_node_state_still_requires_an_existing_save(isolated_db_session):
    isolated_db_session.add(
        NodePersistentState(
            save_id="missing-save",
            node_id="A",
            items_json="[]",
            dangers_json="[]",
        )
    )

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        isolated_db_session.commit()
