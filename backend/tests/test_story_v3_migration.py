"""Deterministic migration coverage for current Story System v2 content."""

from __future__ import annotations

from typing import Any

import pytest

from app.engine.story_v2_loader import StoryV2Loader
from app.schemas.story_v2 import StoryEffectV2, StoryNodeV2
from app.story.v2_migration import (
    migrate_v2_effect,
    migrate_v2_node,
    parse_v2_condition,
)


V2_NODES = StoryV2Loader().nodes


def _current_conditions() -> list[Any]:
    cases: list[Any] = []
    for node_id, node in V2_NODES.items():
        for sequence in node.entry_sequences:
            if sequence.when:
                cases.append(
                    pytest.param(
                        sequence.when,
                        id=f"{node_id}:entry:{sequence.id}",
                    )
                )
            for block in sequence.blocks:
                if block.when:
                    cases.append(
                        pytest.param(
                            block.when,
                            id=f"{node_id}:entry-block:{block.id}",
                        )
                    )
        for choice in node.choices:
            if choice.condition:
                cases.append(
                    pytest.param(
                        choice.condition,
                        id=f"{node_id}:choice:{choice.id}",
                    )
                )
            for block in choice.result_blocks:
                if block.when:
                    cases.append(
                        pytest.param(
                            block.when,
                            id=f"{node_id}:result-block:{block.id}",
                        )
                    )
        for routing_name in ("shortcut", "warp"):
            routing = getattr(node.routing, routing_name)
            if routing and routing.get("entry_condition"):
                cases.append(
                    pytest.param(
                        routing["entry_condition"],
                        id=f"{node_id}:routing:{routing_name}",
                    )
                )
    return cases


def _current_effects() -> list[Any]:
    return [
        pytest.param(
            effect,
            node.id,
            choice.id,
            id=f"{node.id}:{choice.id}:{index}",
        )
        for node in V2_NODES.values()
        for choice in node.choices
        for index, effect in enumerate(choice.effects)
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "cycle==1",
            {
                "type": "counter_compare",
                "counter": "current_cycle",
                "operator": "eq",
                "value": 1,
            },
        ),
        (
            "half_cycle>=2",
            {
                "type": "counter_compare",
                "counter": "half_cycles",
                "operator": "gte",
                "value": 2,
            },
        ),
        (
            "has_item:item_beads",
            {"type": "item", "item_id": "item_beads", "present": True},
        ),
        (
            "not:has_item:item_beads",
            {
                "type": "not",
                "condition": {
                    "type": "item",
                    "item_id": "item_beads",
                    "present": True,
                },
            },
        ),
        (
            "has_flag:river_crossed",
            {"type": "flag_equals", "flag": "river_crossed", "value": True},
        ),
        (
            "flag:trust_level=5",
            {"type": "flag_equals", "flag": "trust_level", "value": 5},
        ),
        (
            "attr:courage>=8",
            {
                "type": "attribute_compare",
                "attribute": "courage",
                "operator": "gte",
                "value": 8,
            },
        ),
        ("at_node:E", {"type": "at_node", "node_id": "E"}),
    ],
)
def test_parse_v2_atomic_condition(source, expected):
    condition = parse_v2_condition(source)
    assert condition is not None
    assert condition.model_dump() == expected


def test_parse_nested_v2_condition():
    condition = parse_v2_condition(
        "or:has_flag:taoist_chant,(and:attr:courage>=8,cycle>=3)"
    )
    assert condition is not None
    assert condition.type == "any"
    assert condition.conditions[1].type == "all"


@pytest.mark.parametrize(
    ("source", "expected_operator"),
    [
        ("attr:courage<8", "lt"),
        ("attr:courage<=8", "lte"),
        ("attr:courage==8", "eq"),
        ("attr:courage!=8", "ne"),
        ("attr:courage>=8", "gte"),
        ("attr:courage>8", "gt"),
    ],
)
def test_parse_v2_condition_maps_every_comparison_operator(
    source,
    expected_operator,
):
    condition = parse_v2_condition(source)
    assert condition is not None
    assert condition.operator == expected_operator


@pytest.mark.parametrize("source", [None, "", "   "])
def test_parse_empty_v2_condition_as_absent(source):
    assert parse_v2_condition(source) is None


@pytest.mark.parametrize(
    "source",
    [
        "python:state.clear()",
        "and:",
        "and:has_flag:ready,",
        "or:(has_flag:ready",
        "attr:courage>=fast",
    ],
)
def test_parse_v2_condition_rejects_unknown_or_malformed_syntax(source):
    with pytest.raises(ValueError, match="condition"):
        parse_v2_condition(source)


@pytest.mark.parametrize("source", _current_conditions())
def test_every_current_machine_condition_parses(source):
    condition = parse_v2_condition(source)
    assert condition is not None
    assert not isinstance(condition.model_dump(), str)


def test_condition_fixture_covers_all_current_nodes_and_runtime_locations():
    assert len(V2_NODES) == 30
    assert len(_current_conditions()) == 100


@pytest.mark.parametrize(
    ("source", "node_id", "choice_id", "expected"),
    [
        (
            StoryEffectV2(type="add_item", target="item_beads", value=2),
            "E",
            "E_choice_01",
            {
                "type": "inventory",
                "item_id": "item_beads",
                "operation": "add",
                "quantity": 2,
            },
        ),
        (
            StoryEffectV2(type="remove_item", target="item_beads", value=1),
            "K",
            "K_choice_01",
            {
                "type": "inventory",
                "item_id": "item_beads",
                "operation": "remove",
                "quantity": 1,
            },
        ),
        (
            StoryEffectV2(type="heal", target="sanity", value=3),
            "A",
            "A_choice_01",
            {
                "type": "modify_attribute",
                "attribute": "sanity",
                "operation": "add",
                "value": 3,
                "clamp": True,
            },
        ),
        (
            StoryEffectV2(type="damage", target="sanity", value=3),
            "A",
            "A_choice_01",
            {
                "type": "modify_attribute",
                "attribute": "sanity",
                "operation": "add",
                "value": -3,
                "clamp": True,
            },
        ),
        (
            StoryEffectV2(type="set_flag", target="river_crossed", value=True),
            "F",
            "F_choice_01",
            {"type": "set_flag", "flag": "river_crossed", "value": True},
        ),
        (
            StoryEffectV2(type="set_flag", target="zhang_trust", value=2),
            "D",
            "D_choice_05",
            {
                "type": "modify_attribute",
                "attribute": "zhang_trust",
                "operation": "set",
                "value": 2,
                "clamp": True,
            },
        ),
        (
            StoryEffectV2(
                type="leave_item",
                target="A_note_from_H",
                value="A_note_from_H",
            ),
            "H",
            "H_choice_04",
            {
                "type": "persist_node_item",
                "node_id": "H",
                "item_id": "A_note_from_H",
            },
        ),
    ],
)
def test_migrate_each_v2_effect_family(
    source,
    node_id,
    choice_id,
    expected,
):
    migrated = migrate_v2_effect(
        source,
        node_id=node_id,
        choice_id=choice_id,
    )
    assert migrated.model_dump() == expected


def test_migrate_v2_effect_rejects_unknown_type():
    source = StoryEffectV2(type="run_script", target="state", value="clear")
    with pytest.raises(ValueError, match="run_script.*A.*A_choice_01"):
        migrate_v2_effect(source, node_id="A", choice_id="A_choice_01")


@pytest.mark.parametrize(
    ("effect", "node_id", "choice_id"),
    _current_effects(),
)
def test_every_current_v2_effect_migrates(effect, node_id, choice_id):
    migrated = migrate_v2_effect(
        effect,
        node_id=node_id,
        choice_id=choice_id,
    )
    assert migrated.type in {
        "inventory",
        "modify_attribute",
        "set_flag",
        "persist_node_item",
    }


def test_effect_fixture_covers_every_current_effect_type():
    current_types = {
        effect.type
        for node in V2_NODES.values()
        for choice in node.choices
        for effect in choice.effects
    }
    assert current_types == {
        "add_item",
        "damage",
        "heal",
        "leave_item",
        "remove_item",
        "set_flag",
    }
    assert len(_current_effects()) == 110


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(node, id=node.id)
        for node in V2_NODES.values()
    ],
)
def test_every_current_v2_node_migrates_to_closed_v3(source: StoryNodeV2):
    migrated = migrate_v2_node(source)

    assert migrated.schema_version == 3
    assert migrated.id == source.id
    assert len(migrated.entry_sequences) == len(source.entry_sequences)
    assert len(migrated.choices) == len(source.choices)
    assert [choice.id for choice in migrated.choices] == [
        choice.id
        for choice in sorted(
            source.choices,
            key=lambda choice: (choice.priority, choice.id),
        )
    ]
    assert all("priority" not in choice.model_dump() for choice in migrated.choices)


def test_migrate_v2_node_converts_all_nested_conditions_and_local_ids():
    source = V2_NODES["A"]
    migrated = migrate_v2_node(source)

    cycle_two = next(
        sequence
        for sequence in migrated.entry_sequences
        if sequence.id == "A_entry_cycle_2"
    )
    conditional_result = next(
        block
        for choice in migrated.choices
        if choice.id == "A_choice_05"
        for block in choice.result
        if block.when is not None
    )

    assert cycle_two.when.type == "counter_compare"
    assert conditional_result.when.type == "flag_equals"
    assert next(
        choice
        for choice in migrated.choices
        if choice.id == "A_choice_01"
    ).availability.condition is None
    assert next(
        choice
        for choice in migrated.choices
        if choice.id == "A_choice_03"
    ).availability.condition.type == "flag_equals"
    assert all(
        "." not in block.id and "+" not in block.id
        for sequence in migrated.entry_sequences
        for block in sequence.blocks
    )


def test_migrate_v2_node_preserves_trigger_description_as_authoring_text():
    migrated = migrate_v2_node(V2_NODES["S1"])
    assert migrated.authoring.trigger_description == (
        V2_NODES["S1"].meta.trigger_condition
    )
