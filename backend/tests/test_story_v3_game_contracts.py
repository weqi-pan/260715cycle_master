import pytest

from app.schemas.game import ContentBlockView, Frame, GameState
from app.schemas.story_v3 import FlagDefinitionV3


def test_new_state_uses_v3_project_defaults(canonical_v3_snapshot):
    project = canonical_v3_snapshot.project

    state = GameState.new(project)

    assert state.current_node_id == project.entry_node_id
    assert state.player_attributes == {
        key: definition.default
        for key, definition in project.attributes.items()
    }
    assert state.flags == {
        key: definition.default
        for key, definition in project.flags.items()
    }
    assert state.entry_attributes == {}
    assert state.interaction_history == {}
    assert state.once_marks == {}


def test_normalized_state_fills_defaults_and_clamps_attributes(
    canonical_v3_snapshot,
):
    project = canonical_v3_snapshot.project
    state = GameState(
        current_node_id="A",
        player_attributes={"sanity": 999, "courage": -5},
        flags={"started_standard_path": True},
    )

    normalized = state.normalized(project, node_ids=canonical_v3_snapshot.nodes)

    assert normalized.player_attributes["sanity"] == 100
    assert normalized.player_attributes["courage"] == 0
    assert normalized.player_attributes["insight"] == 3
    assert normalized.flags["started_standard_path"] is True
    assert normalized.flags["checked_pocket_item"] is False


def test_normalized_state_preserves_false_zero_and_empty_string_defaults(
    canonical_v3_snapshot,
):
    project = canonical_v3_snapshot.project.model_copy(deep=True)
    project.flags.update(
        {
            "int_default": FlagDefinitionV3(display_name="int", default=0),
            "text_default": FlagDefinitionV3(display_name="text", default=""),
        }
    )
    state = GameState(current_node_id="A", flags={"checked_pocket_item": False})

    normalized = state.normalized(project, node_ids=canonical_v3_snapshot.nodes)

    assert normalized.flags["checked_pocket_item"] is False
    assert normalized.flags["int_default"] == 0
    assert normalized.flags["text_default"] == ""


def test_normalized_state_rejects_unknown_current_node(canonical_v3_snapshot):
    state = GameState(current_node_id="missing_node")

    with pytest.raises(ValueError, match="Unknown story node"):
        state.normalized(
            canonical_v3_snapshot.project,
            node_ids=canonical_v3_snapshot.nodes,
        )


def test_normalized_state_rejects_unknown_inventory_item(canonical_v3_snapshot):
    state = GameState(
        current_node_id="A",
        inventory=[{"id": "missing_item", "count": 1}],
    )

    with pytest.raises(ValueError, match="Unknown inventory item"):
        state.normalized(
            canonical_v3_snapshot.project,
            node_ids=canonical_v3_snapshot.nodes,
        )


def test_normalized_state_hydrates_item_metadata_from_v3_project(
    canonical_v3_snapshot,
):
    state = GameState(
        current_node_id="A",
        inventory=[{"id": "item_qing_coin", "name": "stale", "count": 2}],
    )

    normalized = state.normalized(
        canonical_v3_snapshot.project,
        node_ids=canonical_v3_snapshot.nodes,
    )

    item = normalized.inventory[0]
    definition = canonical_v3_snapshot.project.items["item_qing_coin"]
    assert item == {
        "id": "item_qing_coin",
        "name": definition.display_name,
        "count": 2,
        "discardable": definition.discardable,
        "cross_surface": definition.cross_surface,
    }


def test_content_block_view_accepts_check_result():
    block = ContentBlockView(
        id="check-1",
        type="check_result",
        text="洞察检定成功",
        speaker_id=None,
    )

    assert block.type == "check_result"
    assert "condition" not in ContentBlockView.model_fields


def test_frame_has_no_baked_in_npc_registry():
    assert Frame.model_fields["speaker_names"].get_default(call_default_factory=True) == {}
