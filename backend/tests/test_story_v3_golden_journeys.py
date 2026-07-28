"""纯 v3 切换前必须保持稳定的 canonical 剧情契约。"""

from app.schemas.story_v3 import (
    AttributeCompareCondition,
    CrossingRoutingV3,
    ModifyAttributeEffect,
    RestoreEntryAttributeEffect,
    ShortcutRoutingV3,
    WarpRoutingV3,
)


def _choice(story, node_id: str, choice_id: str):
    return next(
        choice for choice in story.nodes[node_id].choices if choice.id == choice_id
    )


def test_canonical_story_shape(canonical_v3_snapshot):
    story = canonical_v3_snapshot

    assert story.project.entry_node_id == "A"
    assert len(story.nodes) == 30
    assert sum(len(node.choices) for node in story.nodes.values()) == 143
    assert sum(
        sum(len(sequence.blocks) for sequence in node.entry_sequences)
        + sum(len(choice.result) for choice in node.choices)
        for node in story.nodes.values()
    ) == 846


def test_h_hidden_choice_has_an_authored_trust_unlock_path(canonical_v3_snapshot):
    story = canonical_v3_snapshot
    trust_effect = _choice(story, "D", "D_choice_05").effects[0]
    trust_condition = _choice(
        story, "H", "H_choice_01"
    ).availability.condition

    assert isinstance(trust_effect, ModifyAttributeEffect)
    assert trust_effect.attribute == "zhang_trust"
    assert trust_effect.operation == "set"
    assert trust_effect.value == 3
    assert isinstance(trust_condition, AttributeCompareCondition)
    assert trust_condition.attribute == "zhang_trust"
    assert trust_condition.operator == "gte"
    assert trust_condition.value == 3


def test_crossing_shortcut_and_warp_routes_are_typed(canonical_v3_snapshot):
    story = canonical_v3_snapshot
    crossing = story.nodes["E"].routing
    shortcut = story.nodes["J"].routing
    warp = story.nodes["K"].routing

    assert isinstance(crossing, CrossingRoutingV3)
    assert crossing.max_deep_interactions == 2
    assert [item.choice_id for item in crossing.deep_interactions] == [
        "E_choice_05",
        "E_choice_06",
        "E_choice_07",
        "E_choice_08",
        "E_choice_09",
        "E_choice_10",
    ]

    assert isinstance(shortcut, ShortcutRoutingV3)
    assert shortcut.entry_node_id == "E"
    assert shortcut.exit_node_id == "A"

    assert isinstance(warp, WarpRoutingV3)
    assert warp.allowed_targets == [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
    ]


def test_k_warp_has_one_uniform_exit_cost(canonical_v3_snapshot):
    warp = canonical_v3_snapshot.nodes["K"].routing

    assert isinstance(warp, WarpRoutingV3)
    assert len(warp.exit_effects) == 1
    cost = warp.exit_effects[0]
    assert isinstance(cost, ModifyAttributeEffect)
    assert cost.attribute == "sanity_max"
    assert cost.operation == "add"
    assert cost.value == -1
    assert cost.clamp is True


def test_s20_restores_entry_sanity_once_per_cycle(canonical_v3_snapshot):
    choice = _choice(canonical_v3_snapshot, "S20", "S20_choice_01")

    assert choice.repeat_policy == "once_per_cycle"
    assert choice.next.mode == "stay"
    assert choice.next.target == "S20"
    assert len(choice.effects) == 1
    restoration = choice.effects[0]
    assert isinstance(restoration, RestoreEntryAttributeEffect)
    assert restoration.attribute == "sanity"
