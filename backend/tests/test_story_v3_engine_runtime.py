import pytest

from app.engine.engine import GameEngine
from app.schemas.game import GameState
from app.schemas.story_v3 import StorySnapshotV3


def make_choice(
    choice_id: str,
    *,
    target: str = "A",
    mode: str = "stay",
    condition: dict | None = None,
    locked_visibility: str = "show",
    locked_reason: str | None = None,
    repeat_policy: str = "always",
    result: list[dict] | None = None,
    effects: list[dict] | None = None,
) -> dict:
    return {
        "id": choice_id,
        "text": choice_id,
        "availability": {
            "condition": condition,
            "locked_visibility": locked_visibility,
            "locked_reason": locked_reason,
        },
        "repeat_policy": repeat_policy,
        "result": result or [],
        "effects": effects or [],
        "next": {"target": target, "mode": mode},
    }


def make_node(
    node_id: str,
    *,
    entries: list[dict] | None = None,
    choices: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 3,
        "id": node_id,
        "meta": {
            "name": f"Node {node_id}",
            "node_type": "normal",
            "position": 0,
            "time_label": None,
            "parent_node_id": None,
            "terminal": None,
        },
        "scene": {
            "background_id": "bg_room",
            "allow_no_background": False,
            "ambient_id": "audio_room",
            "palette": "ink",
        },
        "entry_sequences": entries
        or [
            {
                "id": f"{node_id}_entry",
                "blocks": [
                    {
                        "id": f"{node_id}_narration",
                        "type": "narration",
                        "text": f"Enter {node_id}",
                    }
                ],
            }
        ],
        "choices": choices or [],
    }


def make_snapshot(*, a_entries=None, a_choices=None) -> StorySnapshotV3:
    return StorySnapshotV3.model_validate(
        {
            "schema_version": 3,
            "revision": "test-runtime",
            "project": {
                "schema_version": 3,
                "entry_node_id": "A",
                "attributes": {
                    "insight": {
                        "display_name": "Insight",
                        "default": 1,
                        "minimum": 0,
                        "maximum": 10,
                    }
                },
                "flags": {
                    "unlocked": {"display_name": "Unlocked", "default": False},
                    "revealed": {"display_name": "Revealed", "default": True},
                },
                "items": {
                    "token": {
                        "display_name": "Token",
                        "discardable": True,
                        "cross_surface": False,
                    },
                    "sealed": {
                        "display_name": "Sealed",
                        "discardable": False,
                        "cross_surface": False,
                    },
                },
                "npcs": {"guide": {"display_name": "Guide"}},
                "counters": ["completed_cycles", "half_cycles"],
                "jump_modes": ["stay", "travel", "shortcut", "warp"],
            },
            "assets": {
                "schema_version": 3,
                "assets": {
                    "bg_room": {"kind": "background", "path": "bg/room.png"},
                    "audio_room": {"kind": "audio", "path": "audio/room.ogg"},
                },
            },
            "nodes": {
                "A": make_node("A", entries=a_entries, choices=a_choices),
                "B": make_node("B"),
            },
        }
    )


def test_resume_selects_first_matching_entry_and_filters_blocks():
    snapshot = make_snapshot(
        a_entries=[
            {
                "id": "locked_entry",
                "when": {
                    "type": "flag_equals",
                    "flag": "unlocked",
                    "value": True,
                },
                "blocks": [
                    {"id": "locked_text", "type": "narration", "text": "Locked"}
                ],
            },
            {
                "id": "selected_entry",
                "when": {
                    "type": "attribute_compare",
                    "attribute": "insight",
                    "operator": "gte",
                    "value": 1,
                },
                "blocks": [
                    {"id": "visible_text", "type": "narration", "text": "Visible"},
                    {
                        "id": "guide_line",
                        "type": "dialogue",
                        "speaker_id": "guide",
                        "text": "Listen.",
                        "when": {
                            "type": "flag_equals",
                            "flag": "revealed",
                            "value": True,
                        },
                    },
                    {
                        "id": "hidden_text",
                        "type": "system",
                        "text": "Hidden",
                        "when": {
                            "type": "flag_equals",
                            "flag": "unlocked",
                            "value": True,
                        },
                    },
                ],
            },
            {
                "id": "fallback_entry",
                "blocks": [
                    {"id": "fallback_text", "type": "narration", "text": "Fallback"}
                ],
            },
        ]
    )

    frame = GameEngine().resume(snapshot, GameState.new(snapshot.project))

    assert [block.id for block in frame.node.entry_blocks] == [
        "visible_text",
        "guide_line",
    ]
    assert frame.node.entry_blocks[1].speaker_id == "guide"
    assert frame.node.entry_blocks[0].speaker_id is None
    assert frame.speaker_names == {"guide": "Guide"}


def test_locked_visibility_is_authored_by_the_server():
    locked = {
        "type": "flag_equals",
        "flag": "unlocked",
        "value": True,
    }
    snapshot = make_snapshot(
        a_choices=[
            make_choice(
                "hidden_choice",
                condition=locked,
                locked_visibility="hide",
            ),
            make_choice(
                "shown_choice",
                condition=locked,
                locked_visibility="show",
                locked_reason="Need the key",
            ),
            make_choice("open_choice"),
        ]
    )

    frame = GameEngine().start(snapshot)

    assert [choice.id for choice in frame.available_choices] == [
        "shown_choice",
        "open_choice",
    ]
    shown = frame.available_choices[0]
    assert shown.available is False
    assert shown.reason == "Need the key"
    assert frame.available_choices[1].available is True


def test_choice_effects_run_before_result_block_filtering():
    snapshot = make_snapshot(
        a_choices=[
            make_choice(
                "reveal_choice",
                target="B",
                mode="travel",
                effects=[
                    {"type": "set_flag", "flag": "unlocked", "value": True}
                ],
                result=[
                    {
                        "id": "revealed_result",
                        "type": "check_result",
                        "text": "The lock opens.",
                        "when": {
                            "type": "flag_equals",
                            "flag": "unlocked",
                            "value": True,
                        },
                    },
                    {
                        "id": "hidden_result",
                        "type": "system",
                        "text": "Still locked.",
                        "when": {
                            "type": "flag_equals",
                            "flag": "unlocked",
                            "value": False,
                        },
                    },
                ],
            )
        ]
    )
    original = GameState.new(snapshot.project)

    frame = GameEngine().choose(
        snapshot,
        original,
        node_id="A",
        choice_id="reveal_choice",
    )

    assert original.current_node_id == "A"
    assert original.flags["unlocked"] is False
    assert frame.state.current_node_id == "B"
    assert frame.state.flags["unlocked"] is True
    assert frame.state.visit_id == 1
    assert [block.id for block in frame.result_blocks] == ["revealed_result"]


@pytest.mark.parametrize(
    ("policy", "same_scope_visible", "next_visit_visible", "next_cycle_visible"),
    [
        ("always", True, True, True),
        ("once_per_visit", False, True, True),
        ("once_per_cycle", False, False, True),
        ("once_ever", False, False, False),
    ],
)
def test_repeat_policies_use_their_own_scope(
    policy,
    same_scope_visible,
    next_visit_visible,
    next_cycle_visible,
):
    snapshot = make_snapshot(
        a_choices=[make_choice("repeat_choice", repeat_policy=policy)]
    )
    engine = GameEngine()
    selected = GameState.new(snapshot.project)
    selected.choice_history["repeat_choice"] = {
        "count": 1,
        "last_cycle": 2,
        "last_visit_id": 4,
    }
    selected.cycle_count = 2
    selected.visit_id = 4

    def visible(state: GameState) -> bool:
        frame = engine.resume(snapshot, state)
        return "repeat_choice" in {choice.id for choice in frame.available_choices}

    assert visible(selected) is same_scope_visible
    assert visible(selected.model_copy(update={"visit_id": 5})) is next_visit_visible
    assert visible(
        selected.model_copy(update={"visit_id": 5, "cycle_count": 3})
    ) is next_cycle_visible


def test_stay_records_choice_without_advancing_visit_or_cycle():
    snapshot = make_snapshot(
        a_choices=[
            make_choice(
                "stay_choice",
                repeat_policy="once_per_visit",
            )
        ]
    )
    state = GameState.new(snapshot.project).model_copy(
        update={"visit_id": 7, "cycle_count": 3}
    )

    frame = GameEngine().choose(
        snapshot,
        state,
        node_id="A",
        choice_id="stay_choice",
    )

    assert frame.state.current_node_id == "A"
    assert frame.state.visit_id == 7
    assert frame.state.cycle_count == 3
    assert frame.state.choice_history["stay_choice"] == {
        "count": 1,
        "last_cycle": 3,
        "last_visit_id": 7,
    }
    assert "stay_choice" not in {
        choice.id for choice in frame.available_choices
    }


def test_locked_choice_cannot_be_executed_even_when_it_is_visible():
    snapshot = make_snapshot(
        a_choices=[
            make_choice(
                "shown_choice",
                condition={
                    "type": "flag_equals",
                    "flag": "unlocked",
                    "value": True,
                },
                locked_reason="Need the key",
            )
        ]
    )

    with pytest.raises(ValueError, match="Choice is locked: shown_choice"):
        GameEngine().choose(
            snapshot,
            GameState.new(snapshot.project),
            node_id="A",
            choice_id="shown_choice",
        )


def test_discard_uses_v3_item_registry_and_keeps_the_current_visit():
    snapshot = make_snapshot()
    state = GameState.new(snapshot.project).model_copy(
        update={
            "visit_id": 4,
            "inventory": [{"id": "token", "count": 2}],
        }
    )

    frame = GameEngine().discard(snapshot, state, item_id="token")

    assert frame.state.inventory == [
        {
            "id": "token",
            "name": "Token",
            "count": 1,
            "discardable": True,
            "cross_surface": False,
        }
    ]
    assert frame.state.visit_id == 4


@pytest.mark.parametrize(
    ("item_id", "message"),
    [
        ("missing", "Unknown item: missing"),
        ("sealed", "Item cannot be discarded: sealed"),
        ("token", "Item not in inventory: token"),
    ],
)
def test_discard_rejects_invalid_requests(item_id, message):
    snapshot = make_snapshot()

    with pytest.raises(ValueError, match=message):
        GameEngine().discard(
            snapshot,
            GameState.new(snapshot.project),
            item_id=item_id,
        )


def test_canonical_ordinary_stay_choice_executes_directly_from_v3(
    canonical_v3_snapshot,
):
    engine = GameEngine()
    initial = engine.start(canonical_v3_snapshot)

    assert initial.node.id == "A"
    assert initial.node.entry_blocks
    assert "A_choice_02" in {
        choice.id
        for choice in initial.available_choices
        if choice.available
    }

    frame = engine.choose(
        canonical_v3_snapshot,
        initial.state,
        node_id="A",
        choice_id="A_choice_02",
    )

    assert frame.state.current_node_id == "A"
    assert frame.state.visit_id == 0
    assert frame.state.flags["exploring_surroundings"] is True
    assert frame.result_blocks


def test_choose_preserves_unclamped_attribute_values_between_turns():
    snapshot = make_snapshot(
        a_choices=[
            make_choice(
                "raise_insight",
                effects=[
                    {
                        "type": "modify_attribute",
                        "attribute": "insight",
                        "operation": "set",
                        "value": 15,
                        "clamp": False,
                    }
                ],
            ),
            make_choice("observe"),
        ]
    )
    engine = GameEngine()

    raised = engine.choose(
        snapshot,
        GameState.new(snapshot.project),
        node_id="A",
        choice_id="raise_insight",
    )
    observed = engine.choose(
        snapshot,
        raised.state,
        node_id="A",
        choice_id="observe",
    )

    assert observed.state.player_attributes["insight"] == 15


def test_discard_preserves_unclamped_attribute_values():
    snapshot = make_snapshot()
    state = GameState.new(snapshot.project).model_copy(
        update={
            "player_attributes": {"insight": 15},
            "inventory": [{"id": "token", "count": 1}],
        }
    )

    frame = GameEngine().discard(snapshot, state, item_id="token")

    assert frame.state.player_attributes["insight"] == 15
