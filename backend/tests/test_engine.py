# backend/tests/test_engine.py
import json
import pytest
from unittest.mock import MagicMock, patch
from app.engine.engine import GameEngine
from app.engine.graph import GraphBundle, ChoiceData
from app.schemas.game import GameState, Frame
from app.models.story import StoryNode as StoryNodeModel


def make_state(**kwargs):
    defaults = {
        "current_node_id": "A",
        "cycle_count": 1,
        "inventory": [],
        "flags": {},
        "visited_nodes": [],
        "endings_reached": [],
        "player_attributes": {"sanity": 100, "courage": 5, "insight": 3},
    }
    defaults.update(kwargs)
    return GameState(**defaults)


def make_choice(id, next_node_id, condition=None, effects=None):
    return ChoiceData(
        id=id, from_node_id="A", text="Go", short_text="Go",
        next_node_id=next_node_id, condition=condition,
        effects=effects or [], priority=1, hint=None,
        is_hidden_when_locked=False, transition_text=None,
    )


def make_bundle(node_id, choices):
    from app.engine.graph import GraphBundle
    from app.models.story import StoryNode as StoryNodeModel
    node = StoryNodeModel(
        id=node_id, name="Test", position=0.0, node_type="main",
        content="Test content", speaker=None, background=None,
        time_label=None,
    )
    return GraphBundle(node, [])


@pytest.fixture
def graph():
    node_a = MagicMock(spec=StoryNodeModel)
    node_a.id = "A"
    node_a.name = "Start"
    node_a.position = 0.0
    node_a.node_type = "main"
    node_a.time_label = "Day 1"
    node_a.content = "You are at start."
    node_a.speaker = None
    node_a.background = None
    node_a.cycle_variants_json = "{}"
    node_a.atmosphere_json = "[]"
    node_a.sensory = None
    node_a.color_palette = None
    node_a.gender_variant_json = None
    node_a.parent_node_id = None
    node_a.trigger_condition = None
    node_a.crossing_config_json = None
    node_a.warp_config_json = None
    node_a.shortcut_config_json = None
    node_a.npc_item_mapping_json = None
    node_a.scene_items_json = None

    node_b = MagicMock(spec=StoryNodeModel)
    node_b.id = "B"
    node_b.name = "Room"
    node_b.position = 25.0
    node_b.node_type = "main"
    node_b.time_label = "Day 1 Night"
    node_b.content = "You enter the room."
    node_b.speaker = None
    node_b.background = None
    node_b.cycle_variants_json = "{}"
    node_b.atmosphere_json = "[]"
    node_b.sensory = None
    node_b.color_palette = None
    node_b.gender_variant_json = None
    node_b.parent_node_id = None
    node_b.trigger_condition = None
    node_b.crossing_config_json = None
    node_b.warp_config_json = None
    node_b.shortcut_config_json = None
    node_b.npc_item_mapping_json = None
    node_b.scene_items_json = None

    choice = MagicMock()
    choice.id = "A_choice_01"
    choice.from_node_id = "A"
    choice.text = "Go to B"
    choice.short_text = "Go"
    choice.next_node_id = "B"
    choice.condition = None
    choice.effects_json = '[{"type":"set_flag","target":"moved","value":true}]'
    choice.priority = 1
    choice.hint = None
    choice.is_hidden_when_locked = 0
    choice.transition_text = None

    return {
        "A": GraphBundle(node_a, [choice]),
        "B": GraphBundle(node_b, []),
    }


def test_process_choice_basic(graph):
    engine = GameEngine()
    state = make_state(current_node_id="A")
    frame = engine.process_choice(graph, "A", "A_choice_01", state)

    assert frame.node.id == "B"
    assert frame.state.current_node_id == "B"
    assert frame.state.flags.get("moved") == True
    assert len(frame.available_choices) == 0


def test_process_choice_condition_blocked(graph):
    engine = GameEngine()
    graph["A"].choices[0] = ChoiceData(
        id="A_choice_01", from_node_id="A", text="Go", short_text="Go",
        next_node_id="B", condition="has_item:item_key",
        effects=[], priority=1, hint="Need key",
        is_hidden_when_locked=False, transition_text=None,
    )

    state = make_state(current_node_id="A", inventory=[])
    with pytest.raises(ValueError, match="Condition not met"):
        engine.process_choice(graph, "A", "A_choice_01", state)


def test_resolve_choices_includes_warp(graph):
    engine = GameEngine()
    state = make_state(current_node_id="A", flags={"taoist_chant": True})

    # Add K node with warp_config to the graph
    node_k = MagicMock(spec=StoryNodeModel)
    node_k.id = "K"
    node_k.name = "Warp Gate"
    node_k.position = 50.0
    node_k.node_type = "special"
    node_k.time_label = None
    node_k.content = "You are at the warp gate."
    node_k.speaker = None
    node_k.background = None
    node_k.cycle_variants_json = "{}"
    node_k.atmosphere_json = "[]"
    node_k.sensory = None
    node_k.color_palette = None
    node_k.gender_variant_json = None
    node_k.parent_node_id = None
    node_k.trigger_condition = None
    node_k.crossing_config_json = None
    node_k.warp_config_json = json.dumps({
        "entry_condition": "has_flag:taoist_chant",
        "entry_text": "踏入跃迁裂隙",
        "warp_targets": ["A", "B"]
    })
    node_k.shortcut_config_json = None
    node_k.npc_item_mapping_json = None
    node_k.scene_items_json = None

    bundle_k = GraphBundle(node_k, [])
    graph["K"] = bundle_k

    choices = engine.resolve_available_choices(graph, "A", state)
    choice_ids = [c.id for c in choices]
    assert "A_choice_01" in choice_ids
    has_warp = any(c.source == "special_warp" for c in choices)
    assert has_warp == True
