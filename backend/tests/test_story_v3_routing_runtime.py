import pytest

from app.engine.engine import GameEngine
from app.schemas.game import GameState
from app.schemas.story_v3 import StoryChoiceV3, StorySnapshotV3, TerminalSpecV3


def _state_at(snapshot, node_id: str, **updates) -> GameState:
    state = GameState.new(snapshot.project).model_copy(
        update={"current_node_id": node_id, **updates}
    )
    return state


def _replace_choice(
    snapshot: StorySnapshotV3,
    node_id: str,
    choice_id: str,
    **updates,
) -> StorySnapshotV3:
    node = snapshot.nodes[node_id]
    choices = [
        choice.model_copy(update=updates) if choice.id == choice_id else choice
        for choice in node.choices
    ]
    nodes = dict(snapshot.nodes)
    nodes[node_id] = node.model_copy(update={"choices": choices})
    return snapshot.model_copy(update={"nodes": nodes})


def _terminal_snapshot(
    snapshot: StorySnapshotV3,
    terminal_type: str,
) -> StorySnapshotV3:
    choice = StoryChoiceV3.model_validate(
        {
            "id": "test_terminal_choice",
            "text": "Finish",
            "availability": {
                "condition": None,
                "locked_visibility": "show",
                "locked_reason": None,
            },
            "repeat_policy": "once_ever",
            "result": [],
            "effects": [],
            "next": {"target": "B", "mode": "travel"},
        }
    )
    nodes = dict(snapshot.nodes)
    nodes["A"] = nodes["A"].model_copy(update={"choices": [choice]})
    terminal = TerminalSpecV3(
        type=terminal_type,
        ending_id="ending_test" if terminal_type == "ending" else None,
    )
    nodes["B"] = nodes["B"].model_copy(
        update={
            "meta": nodes["B"].meta.model_copy(update={"terminal": terminal}),
        }
    )
    return snapshot.model_copy(update={"nodes": nodes})


def test_travel_advances_to_declared_target_and_visit_once(
    canonical_v3_snapshot,
):
    engine = GameEngine()
    state = _state_at(
        canonical_v3_snapshot,
        "D",
        visit_id=7,
        interaction_history={
            "crossing_E": ["npc_a_liu"],
            "other": ["npc_li_ergou"],
        },
    )

    frame = engine.choose(
        canonical_v3_snapshot,
        state,
        node_id="D",
        choice_id="D_choice_09",
    )

    assert frame.state.current_node_id == "E"
    assert frame.state.visit_id == 8
    assert frame.state.half_cycle_count == 1
    assert frame.state.interaction_history == {
        "crossing_E": [],
        "other": ["npc_li_ergou"],
    }


def test_shortcut_validates_entry_and_applies_counter_effect_once(
    canonical_v3_snapshot,
):
    engine = GameEngine()
    state = _state_at(
        canonical_v3_snapshot,
        "E",
        visit_id=3,
        flags={"know_secret_tunnel": True},
    )

    entered = engine.choose(
        canonical_v3_snapshot,
        state,
        node_id="E",
        choice_id="E_choice_11",
    )
    exited = engine.choose(
        canonical_v3_snapshot,
        entered.state,
        node_id="J",
        choice_id="J_choice_01",
    )

    assert entered.state.current_node_id == "J"
    assert entered.state.visit_id == 4
    assert exited.state.current_node_id == "A"
    assert exited.state.visit_id == 5
    assert exited.state.half_cycle_count == 1
    assert exited.state.cycle_count == 0


def test_shortcut_rechecks_routing_entry_condition(canonical_v3_snapshot):
    snapshot = _replace_choice(
        canonical_v3_snapshot,
        "E",
        "E_choice_11",
        availability=canonical_v3_snapshot.nodes["E"].choices[10]
        .availability.model_copy(update={"condition": None}),
    )

    with pytest.raises(ValueError, match="Shortcut entry condition not met"):
        GameEngine().choose(
            snapshot,
            _state_at(snapshot, "E"),
            node_id="E",
            choice_id="E_choice_11",
        )


def test_shortcut_rejects_entry_from_undeclared_source(canonical_v3_snapshot):
    choice = StoryChoiceV3.model_validate(
        {
            "id": "test_wrong_shortcut_entry",
            "text": "Enter tunnel",
            "availability": {
                "condition": None,
                "locked_visibility": "show",
                "locked_reason": None,
            },
            "repeat_policy": "always",
            "result": [],
            "effects": [],
            "next": {"target": "J", "mode": "travel"},
        }
    )
    nodes = dict(canonical_v3_snapshot.nodes)
    nodes["A"] = nodes["A"].model_copy(update={"choices": [choice]})
    snapshot = canonical_v3_snapshot.model_copy(update={"nodes": nodes})

    with pytest.raises(ValueError, match="Shortcut entry must come from: E"):
        GameEngine().choose(
            snapshot,
            _state_at(snapshot, "A", flags={"know_secret_tunnel": True}),
            node_id="A",
            choice_id="test_wrong_shortcut_entry",
        )


def test_warp_allows_declared_target_and_applies_uniform_exit_cost(
    canonical_v3_snapshot,
):
    engine = GameEngine()
    state = _state_at(
        canonical_v3_snapshot,
        "H",
        visit_id=10,
        flags={"taoist_chant": True},
    )
    sanity_max = state.player_attributes["sanity_max"]

    entered = engine.choose(
        canonical_v3_snapshot,
        state,
        node_id="H",
        choice_id="H_choice_10",
    )
    exited = engine.choose(
        canonical_v3_snapshot,
        entered.state,
        node_id="K",
        choice_id="K_choice_02",
    )

    assert exited.state.current_node_id == "A"
    assert exited.state.visit_id == 12
    assert exited.state.player_attributes["sanity_max"] == sanity_max - 1
    assert exited.state.cycle_count == 0


def test_warp_rejects_target_outside_allowed_targets(canonical_v3_snapshot):
    choice = next(
        choice
        for choice in canonical_v3_snapshot.nodes["K"].choices
        if choice.id == "K_choice_02"
    )
    snapshot = _replace_choice(
        canonical_v3_snapshot,
        "K",
        "K_choice_02",
        next=choice.next.model_copy(update={"target": "S20"}),
    )

    with pytest.raises(ValueError, match="Warp target is not allowed: S20"):
        GameEngine().choose(
            snapshot,
            _state_at(snapshot, "K", flags={"taoist_chant": True}),
            node_id="K",
            choice_id="K_choice_02",
        )


def test_crossing_limits_deep_interactions_per_visit(canonical_v3_snapshot):
    engine = GameEngine()
    state = _state_at(canonical_v3_snapshot, "E")

    first = engine.choose(
        canonical_v3_snapshot,
        state,
        node_id="E",
        choice_id="E_choice_05",
    )
    second = engine.choose(
        canonical_v3_snapshot,
        first.state,
        node_id="E",
        choice_id="E_choice_06",
    )

    assert second.state.interaction_history["crossing_E"] == [
        "npc_a_liu",
        "npc_li_ergou",
    ]
    visible = {choice.id for choice in second.available_choices}
    assert not visible.intersection(
        {
            "E_choice_05",
            "E_choice_06",
            "E_choice_07",
            "E_choice_08",
            "E_choice_09",
            "E_choice_10",
        }
    )
    with pytest.raises(ValueError, match="Crossing interaction limit reached"):
        engine.choose(
            canonical_v3_snapshot,
            second.state,
            node_id="E",
            choice_id="E_choice_07",
        )


def test_full_cycle_resets_cycle_scope_and_emits_one_event(
    canonical_v3_snapshot,
):
    state = _state_at(
        canonical_v3_snapshot,
        "H",
        cycle_count=2,
        visit_id=11,
        visited_nodes=["A", "D", "H"],
        once_marks={"cycle": ["used"], "session": ["kept"]},
        endings_reached=["ending_kept"],
    )

    frame = GameEngine().choose(
        canonical_v3_snapshot,
        state,
        node_id="H",
        choice_id="H_choice_09",
    )

    assert frame.state.current_node_id == "A"
    assert frame.state.cycle_count == 3
    assert frame.state.visit_id == 12
    assert frame.state.visited_nodes == []
    assert frame.state.once_marks == {"cycle": [], "session": ["kept"]}
    assert frame.state.endings_reached == ["ending_kept"]
    assert frame.cycle_event == {
        "type": "cycle_complete",
        "cycle_count": 3,
        "half_cycle_count": 0,
    }
    assert GameEngine().resume(canonical_v3_snapshot, frame.state).cycle_event is None


def test_h_hidden_choice_unlocks_through_authored_d_choices(
    canonical_v3_snapshot,
):
    engine = GameEngine()
    state = _state_at(canonical_v3_snapshot, "D", cycle_count=1)
    trusted = engine.choose(
        canonical_v3_snapshot,
        state,
        node_id="D",
        choice_id="D_choice_01",
    )
    fully_trusted = engine.choose(
        canonical_v3_snapshot,
        trusted.state,
        node_id="D",
        choice_id="D_choice_05",
    )
    at_h = fully_trusted.state.model_copy(update={"current_node_id": "H"})

    choice = next(
        choice
        for choice in engine.resume(canonical_v3_snapshot, at_h).available_choices
        if choice.id == "H_choice_01"
    )

    assert fully_trusted.state.player_attributes["zhang_trust"] == 3
    assert choice.available is True


def test_s20_restores_once_per_cycle_not_once_per_request(
    canonical_v3_snapshot,
):
    engine = GameEngine()
    state = _state_at(
        canonical_v3_snapshot,
        "S20",
        cycle_count=1,
        player_attributes={
            **GameState.new(canonical_v3_snapshot.project).player_attributes,
            "sanity": 20,
        },
        entry_attributes={"sanity": 65},
    )

    assert engine.resume(canonical_v3_snapshot, state).state.player_attributes[
        "sanity"
    ] == 20
    restored = engine.choose(
        canonical_v3_snapshot,
        state,
        node_id="S20",
        choice_id="S20_choice_01",
    )
    assert restored.state.player_attributes["sanity"] == 65
    with pytest.raises(ValueError, match="repeat policy"):
        engine.choose(
            canonical_v3_snapshot,
            restored.state,
            node_id="S20",
            choice_id="S20_choice_01",
        )

    next_cycle = restored.state.model_copy(
        update={
            "cycle_count": 2,
            "player_attributes": {
                **restored.state.player_attributes,
                "sanity": 15,
            },
            "entry_attributes": {"sanity": 55},
        }
    )
    again = engine.choose(
        canonical_v3_snapshot,
        next_cycle,
        node_id="S20",
        choice_id="S20_choice_01",
    )
    assert again.state.player_attributes["sanity"] == 55


@pytest.mark.parametrize("terminal_type", ["ending", "cycle_complete"])
def test_terminal_frame_is_stable_without_repeated_exit(
    canonical_v3_snapshot,
    terminal_type,
):
    snapshot = _terminal_snapshot(canonical_v3_snapshot, terminal_type)
    engine = GameEngine()

    frame = engine.choose(
        snapshot,
        _state_at(snapshot, "A"),
        node_id="A",
        choice_id="test_terminal_choice",
    )
    resumed = engine.resume(snapshot, frame.state)

    assert frame.state.current_node_id == "B"
    assert frame.available_choices == []
    assert resumed.available_choices == []
    authored_exit = snapshot.nodes["B"].choices[0]
    with pytest.raises(ValueError, match="Terminal node has no exits: B"):
        engine.choose(
            snapshot,
            frame.state,
            node_id="B",
            choice_id=authored_exit.id,
        )
    if terminal_type == "ending":
        assert frame.state.endings_reached == ["ending_test"]
        assert resumed.state.endings_reached == ["ending_test"]
        assert frame.cycle_event is None
    else:
        assert frame.state.cycle_count == 1
        assert frame.cycle_event["type"] == "cycle_complete"
        assert resumed.state.cycle_count == 1
        assert resumed.cycle_event is None
