"""道具元数据与服务端背包动作测试。"""

import pytest

from app.engine.engine import GameEngine
from app.schemas.game import GameState, TurnRequest
from app.routers.game import discard_inventory_item, turns


def test_add_item_uses_canonical_metadata():
    state = GameState(current_node_id="A")

    GameEngine()._apply_effects(
        [{"type": "add_item", "target": "item_qing_coin", "value": 1}],
        state,
        "A",
    )

    assert state.inventory == [{
        "id": "item_qing_coin",
        "name": "清代顺治通宝",
        "count": 1,
        "discardable": True,
        "cross_surface": True,
    }]


def test_unknown_item_effect_is_rejected():
    state = GameState(current_node_id="A")

    with pytest.raises(ValueError, match="Unknown item"):
        GameEngine()._apply_effects(
            [{"type": "add_item", "target": "item_not_defined", "value": 1}],
            state,
            "A",
        )


def test_discard_inventory_item_is_validated_by_server():
    state = GameState(
        current_node_id="A",
        inventory=[{
            "id": "item_qing_coin", "name": "清代顺治通宝", "count": 2,
            "discardable": True, "cross_surface": True,
        }],
    )

    turn_id = turns.issue(state)
    frame = discard_inventory_item("item_qing_coin", TurnRequest(turn_id=turn_id))

    assert frame.state.inventory[0]["count"] == 1


def test_non_discardable_item_is_rejected_by_server():
    state = GameState(
        current_node_id="A",
        inventory=[{"id": "item_old_key", "name": "锈蚀铜钥匙", "count": 1}],
    )

    with pytest.raises(Exception, match="cannot be discarded"):
        discard_inventory_item(
            "item_old_key", TurnRequest(turn_id=turns.issue(state))
        )


def test_legacy_inventory_item_is_hydrated_from_catalog():
    state = GameState(
        current_node_id="A",
        inventory=[{"id": "item_qing_coin", "name": "旧名称", "count": 1}],
    )

    assert state.inventory[0]["name"] == "清代顺治通宝"
    assert state.inventory[0]["discardable"] is True
    assert state.inventory[0]["cross_surface"] is True
