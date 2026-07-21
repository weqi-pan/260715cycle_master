"""真实 v2 图的游戏 API 契约测试。"""

from app.routers.game import choose_action, start_game
from app.schemas.game import ChooseRequest
from fastapi import HTTPException
import pytest


def test_start_frame_contains_only_selectable_choices():
    frame = start_game()

    assert frame.available_choices
    assert all(choice.available for choice in frame.available_choices)
    assert all(choice.next_node_id for choice in frame.available_choices)


def test_stay_choice_disappears_from_real_api_frame_after_selection():
    initial = start_game()
    choice = next(
        item for item in initial.available_choices
        if item.next_node_id == initial.node.id
    )

    frame = choose_action(
        initial.node.id,
        ChooseRequest(choice_id=choice.id, turn_id=initial.turn_id),
    )

    assert choice.id not in {item.id for item in frame.available_choices}
    assert frame.turn_id != initial.turn_id

    with pytest.raises(HTTPException) as replay:
        choose_action(
            initial.node.id,
            ChooseRequest(choice_id=choice.id, turn_id=initial.turn_id),
        )
    assert replay.value.status_code == 409
