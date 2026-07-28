"""Canonical v3 gameplay API contract tests."""

from app.engine.turn_store import TurnStore
from app.routers import game
from app.schemas.game import ChooseRequest
from fastapi import HTTPException
import pytest


@pytest.fixture(autouse=True)
def configure_game_runtime(monkeypatch, canonical_v3_snapshot):
    monkeypatch.setattr(game.story, "_snapshot", canonical_v3_snapshot)
    monkeypatch.setattr(game, "turns", TurnStore())


def test_start_frame_contains_selectable_choices_with_targets():
    frame = game.start_game()

    assert frame.available_choices
    assert any(choice.available for choice in frame.available_choices)
    assert all(choice.next_node_id for choice in frame.available_choices)


def test_stay_choice_disappears_from_real_api_frame_after_selection():
    initial = game.start_game()
    choice = next(
        item for item in initial.available_choices
        if item.next_node_id == initial.node.id
    )

    frame = game.choose_action(
        initial.node.id,
        ChooseRequest(choice_id=choice.id, turn_id=initial.turn_id),
    )

    assert choice.id not in {item.id for item in frame.available_choices}
    assert frame.turn_id != initial.turn_id

    with pytest.raises(HTTPException) as replay:
        game.choose_action(
            initial.node.id,
            ChooseRequest(choice_id=choice.id, turn_id=initial.turn_id),
        )
    assert replay.value.status_code == 409
    assert replay.value.detail == "Turn is stale or already consumed."
