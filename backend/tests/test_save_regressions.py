"""Save and resume regression coverage for the v3 runtime state."""

import json

import pytest

from app.engine.engine import GameEngine
from app.models.save import NodePersistentState, Save
from app.routers.saves import create_save, delete_save, load_save, update_save
from app.schemas.game import GameState


def test_save_round_trip_includes_all_v3_runtime_state(
    isolated_db_session,
    active_v3_story,
):
    state = GameState(
        current_node_id="E",
        cycle_count=2,
        visited_nodes=["A", "D", "E"],
        persistent_nodes={
            "A": {
                "items": [{"id": "item_warning_note"}],
                "dangers": [{"id": "shadow", "name": "shadow"}],
            }
        },
        visit_id=7,
        choice_history={
            "A.inspect": {"count": 3, "last_cycle": 2, "last_visit_id": 7}
        },
        entry_attributes={"sanity": 63, "courage": 4},
        interaction_history={"crossing_E": ["npc_yan_yan"]},
        once_marks={"visit": ["heard_warning"], "session": ["met_yan_yan"]},
    )

    created = create_save("round trip", state, isolated_db_session)
    loaded = load_save(created["id"], isolated_db_session)

    assert loaded.current_node_id == "E"
    assert loaded.cycle_count == 2
    assert loaded.visited_nodes == ["A", "D", "E"]
    assert loaded.persistent_nodes["A"]["items"][0]["id"] == "item_warning_note"
    assert loaded.persistent_nodes["A"]["dangers"] == state.persistent_nodes["A"]["dangers"]
    assert loaded.visit_id == 7
    assert loaded.choice_history == state.choice_history
    assert loaded.entry_attributes == state.entry_attributes
    assert loaded.interaction_history == state.interaction_history
    assert loaded.once_marks == state.once_marks


def test_create_save_rejects_unknown_current_node(
    isolated_db_session,
    active_v3_story,
):
    with pytest.raises(ValueError, match="Unknown story node: missing"):
        create_save(
            "invalid node",
            GameState(current_node_id="missing"),
            isolated_db_session,
        )


def test_create_save_rejects_unknown_inventory_item(
    isolated_db_session,
    active_v3_story,
):
    with pytest.raises(ValueError, match="Unknown inventory item: missing_item"):
        create_save(
            "invalid inventory",
            GameState(
                current_node_id="A",
                inventory=[{"id": "missing_item"}],
            ),
            isolated_db_session,
        )


def test_create_save_fills_registry_defaults_and_clamps_attributes(
    isolated_db_session,
    active_v3_story,
):
    state = GameState(
        current_node_id="A",
        player_attributes={"sanity": 999, "courage": -5},
        flags={"taoist_chant": True},
    )

    created = create_save("normalized", state, isolated_db_session)
    loaded = load_save(created["id"], isolated_db_session)

    expected_attributes = {
        key: min(
            definition.maximum,
            max(
                definition.minimum,
                state.player_attributes.get(key, definition.default),
            ),
        )
        for key, definition in active_v3_story.project.attributes.items()
    }
    expected_flags = {
        key: state.flags.get(key, definition.default)
        for key, definition in active_v3_story.project.flags.items()
    }
    assert loaded.player_attributes == expected_attributes
    assert loaded.flags == expected_flags


def test_load_save_rejects_state_that_no_longer_matches_active_v3(
    isolated_db_session,
    active_v3_story,
):
    created = create_save(
        "stale",
        GameState(current_node_id="A"),
        isolated_db_session,
    )
    stored = isolated_db_session.get(Save, created["id"])
    assert stored is not None
    stored.current_node_id = "missing"
    isolated_db_session.commit()

    with pytest.raises(ValueError, match="Unknown story node: missing"):
        load_save(created["id"], isolated_db_session)


def test_load_save_rejects_unknown_inventory_item(
    isolated_db_session,
    active_v3_story,
):
    created = create_save(
        "stale inventory",
        GameState(current_node_id="A"),
        isolated_db_session,
    )
    stored = isolated_db_session.get(Save, created["id"])
    assert stored is not None
    stored.inventory_json = json.dumps([{"id": "missing_item"}])
    isolated_db_session.commit()

    with pytest.raises(ValueError, match="Unknown inventory item: missing_item"):
        load_save(created["id"], isolated_db_session)


def test_update_save_replaces_removed_persistent_nodes(
    isolated_db_session,
    active_v3_story,
):
    initial = GameState(
        current_node_id="A",
        persistent_nodes={
            "A": {"items": [{"id": "item_old_newspaper"}], "dangers": []}
        },
    )
    created = create_save("replace", initial, isolated_db_session)

    updated = GameState(current_node_id="A", persistent_nodes={})
    update_save(created["id"], updated, isolated_db_session)

    assert load_save(created["id"], isolated_db_session).persistent_nodes == {}


def test_resume_frame_uses_saved_node_without_advancing_state(
    canonical_v3_snapshot,
):
    state = GameState(current_node_id="E", cycle_count=3)

    frame = GameEngine().resume(canonical_v3_snapshot, state)

    assert frame.node.id == "E"
    assert frame.state.current_node_id == "E"
    assert frame.state.cycle_count == 3


def test_resume_rejects_unknown_saved_node(canonical_v3_snapshot):
    with pytest.raises(ValueError, match="Unknown story node: missing"):
        GameEngine().resume(
            canonical_v3_snapshot,
            GameState(current_node_id="missing"),
        )


def test_delete_save_removes_persistent_children_first(
    isolated_db_session,
    active_v3_story,
):
    state = GameState(
        current_node_id="A",
        persistent_nodes={
            "A": {"items": [{"id": "item_warning_note"}], "dangers": []}
        },
    )
    created = create_save("delete", state, isolated_db_session)

    delete_save(created["id"], isolated_db_session)

    assert isolated_db_session.query(Save).count() == 0
    assert isolated_db_session.query(NodePersistentState).count() == 0
