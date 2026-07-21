"""一次性 Turn 状态仓库测试。"""

from app.engine.turn_store import TurnStore
from app.schemas.game import GameState


def test_turn_can_only_be_consumed_once():
    store = TurnStore()
    turn_id = store.issue(GameState(current_node_id="A"))

    assert store.consume(turn_id) is not None
    assert store.consume(turn_id) is None


def test_failed_action_can_restore_same_turn():
    store = TurnStore()
    state = GameState(current_node_id="A")
    turn_id = store.issue(state)

    consumed = store.consume(turn_id)
    store.restore(turn_id, consumed)

    assert store.consume(turn_id).current_node_id == "A"
