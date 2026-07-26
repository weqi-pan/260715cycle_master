"""存档与恢复链路回归测试。"""

from app.models.story import StoryNode
from app.routers.game import _state_frame
from app.routers.saves import create_save, delete_save, load_save, update_save
from app.models.save import NodePersistentState, Save
from app.schemas.game import GameState
from app.engine.graph import GraphBundle


def test_save_round_trip_includes_persistent_nodes(isolated_db_session):
    state = GameState(
        current_node_id="E",
        cycle_count=2,
        persistent_nodes={
            "A": {
                "items": [{"id": "note", "name": "给下一轮的纸条"}],
                "dangers": [{"id": "shadow", "name": "床下黑影"}],
            }
        },
    )

    created = create_save("回归存档", state, isolated_db_session)
    loaded = load_save(created["id"], isolated_db_session)

    assert loaded.current_node_id == "E"
    assert loaded.cycle_count == 2
    assert loaded.persistent_nodes == state.persistent_nodes


def test_save_round_trip_includes_choice_history_and_visit_id(isolated_db_session):
    state = GameState(
        current_node_id="A",
        cycle_count=2,
        visit_id=7,
        choice_history={
            "A.inspect": {"count": 3, "last_cycle": 2, "last_visit_id": 7}
        },
    )

    created = create_save("选择记录", state, isolated_db_session)
    loaded = load_save(created["id"], isolated_db_session)

    assert loaded.visit_id == 7
    assert loaded.choice_history == state.choice_history


def test_update_save_replaces_removed_persistent_nodes(isolated_db_session):
    initial = GameState(
        current_node_id="A",
        persistent_nodes={"A": {"items": [{"id": "old"}], "dangers": []}},
    )
    created = create_save("覆盖测试", initial, isolated_db_session)

    updated = GameState(current_node_id="A", persistent_nodes={})
    update_save(created["id"], updated, isolated_db_session)

    assert load_save(created["id"], isolated_db_session).persistent_nodes == {}


def test_resume_frame_uses_saved_node_without_advancing_state():
    node_a = StoryNode(id="A", name="A", position=0, node_type="main", content="A")
    node_e = StoryNode(id="E", name="E", position=100, node_type="main", content="E")
    graph = {
        "A": GraphBundle(node_a, []),
        "E": GraphBundle(node_e, []),
    }
    state = GameState(current_node_id="E", cycle_count=3)

    frame = _state_frame(graph, state)

    assert frame.node.id == "E"
    assert frame.state.current_node_id == "E"
    assert frame.state.cycle_count == 3


def test_delete_save_removes_persistent_children_first(isolated_db_session):
    state = GameState(
        current_node_id="A",
        persistent_nodes={"A": {"items": [{"id": "note"}], "dangers": []}},
    )
    created = create_save("删除测试", state, isolated_db_session)

    delete_save(created["id"], isolated_db_session)

    assert isolated_db_session.query(Save).count() == 0
    assert isolated_db_session.query(NodePersistentState).count() == 0
