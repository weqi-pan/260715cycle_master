"""Gameplay API coverage for the canonical Story System v3 runtime."""

import pytest
from fastapi import HTTPException

from app.engine.effects_v3 import EffectExecutionError
from app.engine.turn_store import TurnStore
from app.routers import game
from app.schemas.game import ChooseRequest, GameState, TurnRequest


@pytest.fixture(autouse=True)
def configure_game_runtime(monkeypatch, canonical_v3_snapshot):
    monkeypatch.setattr(game.story, "_snapshot", canonical_v3_snapshot)
    monkeypatch.setattr(game, "turns", TurnStore())


def test_start_begins_at_snapshot_project_entry_node(canonical_v3_snapshot):
    snapshot = canonical_v3_snapshot.model_copy(
        update={
            "project": canonical_v3_snapshot.project.model_copy(
                update={"entry_node_id": "B"}
            )
        }
    )
    game.story._snapshot = snapshot

    frame = game.start_game()

    assert frame.node.id == snapshot.project.entry_node_id
    assert frame.state.current_node_id == snapshot.project.entry_node_id
    assert frame.turn_id


def test_resume_validates_v3_state_and_returns_frame(canonical_v3_snapshot):
    item_id, definition = next(iter(canonical_v3_snapshot.project.items.items()))
    state = GameState(
        current_node_id=canonical_v3_snapshot.project.entry_node_id,
        flags={},
        player_attributes={},
        inventory=[{"id": item_id, "count": 1}],
    )

    frame = game.resume_game(state)

    assert frame.node.id == state.current_node_id
    assert frame.turn_id
    assert frame.state.player_attributes == {
        key: value.default
        for key, value in canonical_v3_snapshot.project.attributes.items()
    }
    assert frame.state.inventory[0]["name"] == definition.display_name


def test_resume_fills_missing_entry_attribute_baseline_before_s20_choice(
    canonical_v3_snapshot,
):
    state = GameState.new(canonical_v3_snapshot.project)
    state.current_node_id = "S20"
    state.player_attributes["sanity"] = 23
    state.entry_attributes = {"courage": 9}

    resumed = game.resume_game(state)

    assert resumed.state.entry_attributes["sanity"] == 23
    assert resumed.state.entry_attributes["courage"] == 9
    assert game.turns.get(resumed.turn_id).entry_attributes == (
        resumed.state.entry_attributes
    )

    chosen = game.choose_action(
        "S20",
        ChooseRequest(
            choice_id="S20_choice_01",
            turn_id=resumed.turn_id,
        ),
    )

    assert chosen.state.player_attributes["sanity"] == 23
    assert chosen.result_blocks


def test_resume_rejects_unknown_story_node():
    with pytest.raises(HTTPException) as raised:
        game.resume_game(GameState(current_node_id="missing_node"))

    assert raised.value.status_code == 404
    assert raised.value.detail == "Unknown story node: missing_node"


def test_choose_rejects_path_and_turn_node_mismatch():
    initial = game.start_game()

    with pytest.raises(HTTPException) as raised:
        game.choose_action(
            "B",
            ChooseRequest(choice_id="A_choice_02", turn_id=initial.turn_id),
        )

    assert raised.value.status_code == 409
    assert "State node mismatch" in raised.value.detail
    assert game.turns.get(initial.turn_id) == initial.state


def test_duplicate_turn_consumption_does_not_execute_effects_twice():
    initial = game.start_game()
    request = ChooseRequest(choice_id="A_choice_02", turn_id=initial.turn_id)

    selected = game.choose_action(initial.node.id, request)

    assert selected.state.flags["exploring_surroundings"] is True
    assert selected.state.choice_history["A_choice_02"]["count"] == 1
    with pytest.raises(HTTPException) as replay:
        game.choose_action(initial.node.id, request)
    assert replay.value.status_code == 409
    assert replay.value.detail == "Turn is stale or already consumed."
    stored = game.turns.get(selected.turn_id)
    assert stored.flags["exploring_surroundings"] is True
    assert stored.choice_history["A_choice_02"]["count"] == 1


def test_failed_choice_restores_consumed_turn_and_original_state(monkeypatch):
    initial = game.start_game()

    def fail_after_mutation(_snapshot, state, **_kwargs):
        state.flags["mutated_before_failure"] = True
        raise RuntimeError("unexpected engine failure")

    monkeypatch.setattr(game.engine, "choose", fail_after_mutation)

    with pytest.raises(RuntimeError, match="unexpected engine failure"):
        game.choose_action(
            initial.node.id,
            ChooseRequest(
                choice_id="A_choice_02",
                turn_id=initial.turn_id,
            ),
        )

    assert game.turns.get(initial.turn_id) == initial.state


def test_unexpected_value_error_remains_a_server_failure(monkeypatch):
    initial = game.start_game()

    def fail_unexpectedly(_snapshot, _state, **_kwargs):
        raise ValueError("unexpected internal value failure")

    monkeypatch.setattr(game.engine, "choose", fail_unexpectedly)

    with pytest.raises(ValueError, match="unexpected internal value failure"):
        game.choose_action(
            initial.node.id,
            ChooseRequest(
                choice_id="A_choice_02",
                turn_id=initial.turn_id,
            ),
        )

    assert game.turns.get(initial.turn_id) == initial.state


def test_unsupported_effect_failure_remains_a_server_failure(monkeypatch):
    initial = game.start_game()

    def fail_with_authoring_invariant(_snapshot, _state, **_kwargs):
        raise EffectExecutionError("Unsupported v3 effect: BogusEffect")

    monkeypatch.setattr(
        game.engine,
        "choose",
        fail_with_authoring_invariant,
    )

    with pytest.raises(
        EffectExecutionError,
        match="Unsupported v3 effect: BogusEffect",
    ):
        game.choose_action(
            initial.node.id,
            ChooseRequest(
                choice_id="A_choice_02",
                turn_id=initial.turn_id,
            ),
        )

    assert game.turns.get(initial.turn_id) == initial.state


def test_unknown_authored_effect_item_remains_a_server_failure(monkeypatch):
    initial = game.start_game()

    def fail_with_authored_missing_item(_snapshot, _state, **_kwargs):
        raise EffectExecutionError("Unknown item: authored_missing")

    monkeypatch.setattr(
        game.engine,
        "choose",
        fail_with_authored_missing_item,
    )

    with pytest.raises(
        EffectExecutionError,
        match="Unknown item: authored_missing",
    ):
        game.choose_action(
            initial.node.id,
            ChooseRequest(
                choice_id="A_choice_02",
                turn_id=initial.turn_id,
            ),
        )

    assert game.turns.get(initial.turn_id) == initial.state


@pytest.mark.parametrize(
    ("message", "expected_status"),
    [
        ("Inventory removal would go below zero: item_token", 400),
        ("Missing entry attribute: sanity", 409),
    ],
)
def test_correctable_effect_failures_have_stable_statuses(
    monkeypatch,
    message,
    expected_status,
):
    initial = game.start_game()

    def fail_effect(_snapshot, _state, **_kwargs):
        raise EffectExecutionError(message)

    monkeypatch.setattr(game.engine, "choose", fail_effect)

    with pytest.raises(HTTPException) as raised:
        game.choose_action(
            initial.node.id,
            ChooseRequest(
                choice_id="A_choice_02",
                turn_id=initial.turn_id,
            ),
        )

    assert raised.value.status_code == expected_status
    assert raised.value.detail == message
    assert game.turns.get(initial.turn_id) == initial.state


@pytest.mark.parametrize(
    ("case", "expected_status", "message"),
    [
        ("unknown", 404, "Unknown item: missing_item"),
        ("not_owned", 404, "Item not in inventory"),
        ("non_discardable", 400, "Item cannot be discarded"),
    ],
)
def test_discard_rejects_invalid_v3_items(
    canonical_v3_snapshot,
    case,
    expected_status,
    message,
):
    if case == "unknown":
        item_id = "missing_item"
        state = GameState.new(canonical_v3_snapshot.project)
    else:
        item_id, _definition = next(
            (item_id, definition)
            for item_id, definition in canonical_v3_snapshot.project.items.items()
            if definition.discardable is (case == "not_owned")
        )
        state = GameState.new(canonical_v3_snapshot.project)
        if case == "non_discardable":
            state.inventory = [{"id": item_id, "count": 1}]
    turn_id = game.turns.issue(state)

    with pytest.raises(HTTPException) as raised:
        game.discard_inventory_item(item_id, TurnRequest(turn_id=turn_id))

    assert raised.value.status_code == expected_status
    assert message in raised.value.detail
    assert game.turns.get(turn_id) == state


def test_response_contains_v3_blocks_and_registered_npc_names(
    canonical_v3_snapshot,
):
    initial = game.start_game()
    frame = game.choose_action(
        initial.node.id,
        ChooseRequest(choice_id="A_choice_02", turn_id=initial.turn_id),
    )

    assert initial.node.entry_blocks
    assert frame.node.entry_blocks
    assert frame.result_blocks
    assert frame.speaker_names == {
        npc_id: definition.display_name
        for npc_id, definition in canonical_v3_snapshot.project.npcs.items()
    }
