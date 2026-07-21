"""选项可见性与重复策略回归测试。"""

import pytest

from app.engine.engine import GameEngine
from app.engine.graph import ChoiceData, GraphBundle
from app.models.story import StoryNode
from app.schemas.game import GameState


def make_bundle(node_id: str) -> GraphBundle:
    node = StoryNode(
        id=node_id,
        name=f"Node {node_id}",
        position=0.0,
        node_type="main",
        content=f"Content {node_id}",
    )
    return GraphBundle(node, [])


def make_choice(
    choice_id: str,
    from_node_id: str,
    next_node_id: str,
    repeat_policy: str,
) -> ChoiceData:
    return ChoiceData(
        id=choice_id,
        from_node_id=from_node_id,
        text=choice_id,
        short_text=None,
        next_node_id=next_node_id,
        condition=None,
        effects=[],
        priority=1,
        hint=None,
        is_hidden_when_locked=True,
        transition_text=None,
        repeat_policy=repeat_policy,
    )


@pytest.mark.parametrize(
    ("repeat_policy", "visible_after_selection"),
    [
        ("always", True),
        ("once_per_visit", False),
        ("once_per_cycle", False),
        ("once_ever", False),
    ],
)
def test_selected_choice_visibility_follows_repeat_policy(
    repeat_policy: str, visible_after_selection: bool
):
    engine = GameEngine()
    graph = {"A": make_bundle("A")}
    choice = make_choice("A.inspect", "A", "A", repeat_policy)
    graph["A"].choices = [choice]
    state = GameState(current_node_id="A")

    frame = engine.process_choice(graph, "A", choice.id, state)

    assert (choice.id in {item.id for item in frame.available_choices}) is visible_after_selection


def test_once_per_visit_returns_only_after_leaving_and_reentering_node():
    engine = GameEngine()
    graph = {"A": make_bundle("A"), "B": make_bundle("B")}
    inspect = make_choice("A.inspect", "A", "A", "once_per_visit")
    leave = make_choice("A.to.B", "A", "B", "always")
    back = make_choice("B.to.A", "B", "A", "always")
    graph["A"].choices = [inspect, leave]
    graph["B"].choices = [back]
    state = GameState(current_node_id="A")

    engine.process_choice(graph, "A", inspect.id, state)
    assert inspect.id not in {
        item.id for item in engine.resolve_available_choices(graph, "A", state)
    }

    engine.process_choice(graph, "A", leave.id, state)
    frame = engine.process_choice(graph, "B", back.id, state)

    assert inspect.id in {item.id for item in frame.available_choices}


def test_once_per_cycle_returns_after_full_cycle():
    engine = GameEngine()
    graph = {"A": make_bundle("A"), "H": make_bundle("H")}
    inspect = make_choice("A.inspect", "A", "A", "once_per_cycle")
    to_h = make_choice("A.to.H", "A", "H", "always")
    to_a = make_choice("H.to.A", "H", "A", "always")
    graph["A"].choices = [inspect, to_h]
    graph["H"].choices = [to_a]
    state = GameState(current_node_id="A")

    engine.process_choice(graph, "A", inspect.id, state)
    engine.process_choice(graph, "A", to_h.id, state)
    frame = engine.process_choice(graph, "H", to_a.id, state)

    assert frame.state.cycle_count == 1
    assert inspect.id in {item.id for item in frame.available_choices}


def test_once_ever_remains_hidden_after_full_cycle():
    engine = GameEngine()
    graph = {"A": make_bundle("A"), "H": make_bundle("H")}
    inspect = make_choice("A.inspect", "A", "A", "once_ever")
    to_h = make_choice("A.to.H", "A", "H", "always")
    to_a = make_choice("H.to.A", "H", "A", "always")
    graph["A"].choices = [inspect, to_h]
    graph["H"].choices = [to_a]
    state = GameState(current_node_id="A")

    engine.process_choice(graph, "A", inspect.id, state)
    engine.process_choice(graph, "A", to_h.id, state)
    frame = engine.process_choice(graph, "H", to_a.id, state)

    assert inspect.id not in {item.id for item in frame.available_choices}


def test_hidden_repeat_choice_cannot_be_forged():
    engine = GameEngine()
    graph = {"A": make_bundle("A")}
    choice = make_choice("A.inspect", "A", "A", "once_ever")
    graph["A"].choices = [choice]
    state = GameState(current_node_id="A")

    engine.process_choice(graph, "A", choice.id, state)

    with pytest.raises(ValueError, match="already selected|repeat"):
        engine.process_choice(graph, "A", choice.id, state)


def test_failed_choice_does_not_consume_repeat_policy():
    engine = GameEngine()
    graph = {"A": make_bundle("A")}
    choice = make_choice("A.broken", "A", "missing", "once_ever")
    graph["A"].choices = [choice]
    state = GameState(current_node_id="A")

    with pytest.raises(ValueError, match="Target node"):
        engine.process_choice(graph, "A", choice.id, state)

    assert choice.id not in state.choice_history
