"""Deterministic migration coverage for current Story System v2 content."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pytest

from app.domain.items import ITEM_NAMES
from app.domain.npcs import NPC_NAMES
from app.engine.story_v2_loader import StoryV2Loader
from app.paths import STORY_DATA_V2_DIR
from app.schemas.story_v2 import StoryEffectV2, StoryNodeV2
from app.schemas.story_v3 import StoryChoiceV3, StorySnapshotV3
from app.story.compiler import StoryCompiler
from app.story.identifiers import validate_story_id
from app.story.v2_migration import (
    migrate_project,
    migrate_v2_effect,
    migrate_v2_node,
    parse_v2_condition,
)


V2_NODES = StoryV2Loader().nodes
V2_ROOT = STORY_DATA_V2_DIR
CANONICAL_V3_ROOT = V2_ROOT.parent / "story_v3"

_FLAG_REFERENCE_RE = re.compile(
    r"(?:has_flag:|flag:)([A-Za-z][A-Za-z0-9_-]*)"
)
_ITEM_REFERENCE_RE = re.compile(
    r"has_item:([A-Za-z][A-Za-z0-9_-]*)"
)


def _migrate_project(destination: Path) -> None:
    migrate_project(V2_ROOT, destination)


def _compile_migration(destination: Path) -> StorySnapshotV3:
    _migrate_project(destination)
    compilation = StoryCompiler().compile(destination)
    assert compilation.diagnostics == ()
    return compilation.require_success()


def _choice(story: StorySnapshotV3, choice_id: str) -> StoryChoiceV3:
    return next(
        choice
        for node in story.nodes.values()
        for choice in node.choices
        if choice.id == choice_id
    )


def _total_content_blocks(story: StorySnapshotV3) -> int:
    return sum(
        sum(len(sequence.blocks) for sequence in node.entry_sequences)
        + sum(len(choice.result) for choice in node.choices)
        for node in story.nodes.values()
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _all_json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _all_json_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_json_objects(nested)


def _expected_project_registries() -> tuple[set[str], set[str], set[str]]:
    flags: set[str] = set()
    items = set(ITEM_NAMES)
    npcs = set(NPC_NAMES)

    def collect_condition(expression: str | None) -> None:
        if expression is None:
            return
        flags.update(_FLAG_REFERENCE_RE.findall(expression))
        items.update(_ITEM_REFERENCE_RE.findall(expression))

    for node in V2_NODES.values():
        for sequence in node.entry_sequences:
            collect_condition(sequence.when)
            for block in sequence.blocks:
                collect_condition(block.when)
                if block.speaker_id is not None:
                    npcs.add(block.speaker_id)

        for choice in node.choices:
            collect_condition(choice.condition)
            for block in choice.result_blocks:
                collect_condition(block.when)
                if block.speaker_id is not None:
                    npcs.add(block.speaker_id)
            for effect in choice.effects:
                if effect.type == "set_flag" and effect.target is not None:
                    flags.add(effect.target)
                elif (
                    effect.type in {"add_item", "remove_item", "leave_item"}
                    and effect.target is not None
                ):
                    items.add(effect.target)

        for routing_name in ("shortcut", "warp"):
            routing = getattr(node.routing, routing_name)
            if routing is not None:
                collect_condition(routing.get("entry_condition"))
        if node.routing.crossing is not None:
            npcs.update(node.routing.crossing.get("available_npcs", []))

        npcs.update(node.authoring.npcs_present)
        items.update(
            entry["item_id"] for entry in node.authoring.scene_items
        )
        mapping = node.authoring.npc_item_mapping
        if isinstance(mapping, list):
            for entry in mapping:
                npcs.add(entry["npc_id"])
                items.add(entry["item_id"])
                required_flag = entry.get("flag")
                if required_flag is not None:
                    flags.add(required_flag)

    # v3 explicitly repairs the v2 flag/attribute collision for this value.
    flags.discard("zhang_trust")
    return flags, items, npcs


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
        choice.id for choice in source.choices
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


@pytest.mark.parametrize(
    "source_id",
    [
        pytest.param("CON", id="windows-device-name"),
        pytest.param("1.bad", id="non-letter-prefix"),
        pytest.param("A" * 65, id="over-64-characters"),
    ],
)
def test_migrate_v2_node_makes_every_entry_id_safe_and_deterministic(
    source_id,
):
    source = V2_NODES["A"].model_copy(deep=True)
    source.entry_sequences[0].id = source_id

    first = migrate_v2_node(source)
    second = migrate_v2_node(source)
    migrated_id = first.entry_sequences[0].id

    assert validate_story_id(migrated_id) == migrated_id
    assert second.entry_sequences[0].id == migrated_id
    assert first.id == source.id
    assert [choice.id for choice in first.choices] == [
        choice.id for choice in source.choices
    ]


def test_migrate_v2_node_keeps_colliding_content_block_slugs_distinct():
    source = V2_NODES["A"].model_copy(deep=True)
    source.entry_sequences[0].blocks[0].id = "a.b"
    source.entry_sequences[0].blocks[1].id = "a+b"

    migrated = migrate_v2_node(source)
    block_ids = [
        block.id
        for sequence in migrated.entry_sequences
        for block in sequence.blocks
    ]

    assert block_ids[0] != block_ids[1]
    assert all(
        validate_story_id(block_id) == block_id
        for block_id in block_ids
    )
    assert migrated.id == source.id
    assert {choice.id for choice in migrated.choices} == {
        choice.id for choice in source.choices
    }


def test_full_migration_preserves_real_corpus_counts(tmp_path: Path):
    story = _compile_migration(tmp_path / "story_v3")

    assert len(story.nodes) == 30
    assert sum(len(node.choices) for node in story.nodes.values()) == 143
    assert _total_content_blocks(story) == 846


def test_migration_applies_known_story_repairs(tmp_path: Path):
    story = _compile_migration(tmp_path / "story_v3")

    assert story.nodes["S10"].meta.parent_node_id == "F"
    assert story.nodes["S13"].meta.parent_node_id == "G"
    assert story.nodes["S14"].meta.parent_node_id == "G"
    assert story.nodes["S19"].meta.parent_node_id == "H"
    assert _choice(story, "S19_choice_02").next.target == "H"
    assert story.nodes["S20"].meta.parent_node_id == "H"
    assert _choice(story, "S20_choice_02").next.target == "H"
    assert _choice(story, "S2_choice_03").next.target == "A"
    assert _choice(story, "S3_choice_03").next.target == "B"
    assert _choice(story, "S4_choice_03").next.target == "B"
    assert _choice(story, "S5_choice_01").next.target == "C"
    assert _choice(story, "S5_choice_03").next.target == "C"
    assert _choice(story, "S6_choice_03").next.target == "C"
    assert _choice(story, "S15_choice_03").next.target == "G"

    restoration = _choice(story, "S20_choice_01")
    assert restoration.repeat_policy == "once_per_cycle"
    assert [effect.model_dump() for effect in restoration.effects] == [
        {
            "type": "restore_entry_attribute",
            "attribute": "sanity",
        }
    ]

    trust_effect = _choice(story, "D_choice_05").effects[0]
    assert trust_effect.type == "modify_attribute"
    assert trust_effect.attribute == "zhang_trust"
    assert trust_effect.operation == "set"
    assert trust_effect.value == 3


def test_migration_uses_one_based_current_cycle_for_first_run_content(
    tmp_path: Path,
):
    story = _compile_migration(tmp_path / "story_v3")
    first_run = next(
        sequence
        for sequence in story.nodes["D"].entry_sequences
        if sequence.id == "D_entry_cycle_1"
    )

    assert first_run.when is not None
    assert first_run.when.model_dump() == {
        "type": "counter_compare",
        "counter": "current_cycle",
        "operator": "eq",
        "value": 1,
    }


def test_migration_builds_typed_crossing_shortcut_and_warp_routing(
    tmp_path: Path,
):
    story = _compile_migration(tmp_path / "story_v3")

    crossing = story.nodes["E"].routing
    assert crossing is not None
    assert crossing.type == "crossing"
    assert crossing.max_deep_interactions == 2
    assert [entry.model_dump() for entry in crossing.deep_interactions] == [
        {"choice_id": "E_choice_05", "npc_id": "npc_a_liu"},
        {"choice_id": "E_choice_06", "npc_id": "npc_li_ergou"},
        {"choice_id": "E_choice_07", "npc_id": "npc_liu_qisheng"},
        {"choice_id": "E_choice_08", "npc_id": "npc_huijue"},
        {"choice_id": "E_choice_09", "npc_id": "npc_shen_banxian"},
        {"choice_id": "E_choice_10", "npc_id": "npc_deleng"},
    ]

    shortcut = story.nodes["J"].routing
    assert shortcut is not None
    assert shortcut.type == "shortcut"
    assert shortcut.entry_condition.model_dump() == {
        "type": "any",
        "conditions": [
            {
                "type": "flag_equals",
                "flag": "know_secret_tunnel",
                "value": True,
            },
            {
                "type": "item",
                "item_id": "item_tunnel_map",
                "present": True,
            },
        ],
    }
    assert shortcut.entry_node_id == "E"
    assert shortcut.exit_node_id == "A"
    assert [effect.model_dump() for effect in shortcut.counter_effects] == [
        {
            "type": "modify_counter",
            "counter": "half_cycles",
            "operation": "add",
            "value": 1,
        }
    ]

    warp = story.nodes["K"].routing
    assert warp is not None
    assert warp.type == "warp"
    assert warp.allowed_targets == ["A", "B", "C", "D", "E", "F", "G", "H"]
    assert [
        choice.id
        for choice in story.nodes["K"].choices
        if choice.next.mode == "warp"
    ] == [f"K_choice_{index:02d}" for index in range(2, 10)]
    assert [effect.model_dump() for effect in warp.exit_effects] == [
        {
            "type": "modify_attribute",
            "attribute": "sanity_max",
            "operation": "add",
            "value": -1,
            "clamp": True,
        }
    ]


def test_migration_has_one_exact_shortcut_choice(tmp_path: Path):
    story = _compile_migration(tmp_path / "story_v3")

    assert [
        (choice.id, choice.next.mode, choice.next.target)
        for node in story.nodes.values()
        for choice in node.choices
        if choice.next.mode == "shortcut"
    ] == [("J_choice_01", "shortcut", "A")]


def test_migration_has_eight_exact_warp_choices(tmp_path: Path):
    story = _compile_migration(tmp_path / "story_v3")

    assert [
        (choice.id, choice.next.mode, choice.next.target)
        for node in story.nodes.values()
        for choice in node.choices
        if choice.next.mode == "warp"
    ] == [
        ("K_choice_02", "warp", "A"),
        ("K_choice_03", "warp", "B"),
        ("K_choice_04", "warp", "C"),
        ("K_choice_05", "warp", "D"),
        ("K_choice_06", "warp", "E"),
        ("K_choice_07", "warp", "F"),
        ("K_choice_08", "warp", "G"),
        ("K_choice_09", "warp", "H"),
    ]


def test_migration_preserves_choice_order_and_locked_visibility(
    tmp_path: Path,
):
    story = _compile_migration(tmp_path / "story_v3")

    for node_id, source in V2_NODES.items():
        migrated = story.nodes[node_id]
        assert [choice.id for choice in migrated.choices] == [
            choice.id for choice in source.choices
        ]
        assert [
            choice.availability.locked_visibility
            for choice in migrated.choices
        ] == [choice.locked_visibility for choice in source.choices]


def test_migration_emits_closed_runtime_data_and_explicit_scenes(
    tmp_path: Path,
):
    destination = tmp_path / "story_v3"
    story = _compile_migration(destination)

    assert all(
        node.scene.background_id is not None
        or node.scene.allow_no_background
        for node in story.nodes.values()
    )
    for path in sorted(destination.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        objects = list(_all_json_objects(payload))
        assert all("priority" not in value for value in objects)
        assert all("linked_sub_nodes" not in value for value in objects)
        assert all("trigger_condition" not in value for value in objects)
        assert all(
            not isinstance(value.get("condition"), str)
            and not isinstance(value.get("when"), str)
            and not isinstance(value.get("entry_condition"), str)
            for value in objects
        )

    for node_id, source in V2_NODES.items():
        assert story.nodes[node_id].authoring.trigger_description == (
            source.meta.trigger_condition
        )


def test_migration_builds_complete_typed_project_registries(tmp_path: Path):
    story = _compile_migration(tmp_path / "story_v3")
    project = story.project
    expected_flags, expected_items, expected_npcs = (
        _expected_project_registries()
    )

    assert project.entry_node_id == "A"
    assert set(project.attributes) == {
        "sanity",
        "sanity_max",
        "courage",
        "insight",
        "zhang_trust",
    }
    assert all(
        isinstance(value, int)
        for definition in project.attributes.values()
        for value in (
            definition.default,
            definition.minimum,
            definition.maximum,
        )
    )
    assert expected_items - set(ITEM_NAMES) == {"A_note_from_H"}
    assert expected_npcs - set(NPC_NAMES) == {"player"}
    assert set(project.flags) == expected_flags
    assert set(project.items) == expected_items
    assert set(project.npcs) == expected_npcs
    assert project.counters == ["completed_cycles", "half_cycles"]
    assert project.jump_modes == ["stay", "travel", "shortcut", "warp"]


def test_committed_canonical_tree_matches_fresh_migration(tmp_path: Path):
    destination = tmp_path / "story_v3"
    _migrate_project(destination)
    fresh = _tree_bytes(destination)
    committed = _tree_bytes(CANONICAL_V3_ROOT)
    committed.pop("story-node-v3.schema.json")

    assert len(fresh) == 32
    assert fresh == committed


def test_running_migration_twice_is_byte_identical(tmp_path: Path):
    destination = tmp_path / "story_v3"
    _migrate_project(destination)
    first = _tree_bytes(destination)

    _migrate_project(destination)

    assert _tree_bytes(destination) == first
    assert len(first) == 32


def test_migration_removes_only_stale_json_node_files(tmp_path: Path):
    destination = tmp_path / "story_v3"
    nodes = destination / "nodes"
    nodes.mkdir(parents=True)
    stale_node = nodes / "ORPHAN.json"
    unrelated_file = nodes / "editor-notes.txt"
    stale_node.write_text("{}", encoding="utf-8")
    unrelated_file.write_text("keep", encoding="utf-8")

    _migrate_project(destination)

    assert not stale_node.exists()
    assert unrelated_file.read_text(encoding="utf-8") == "keep"
    assert StoryCompiler().compile(destination).diagnostics == ()


def test_migration_cli_writes_a_compilable_temporary_project(tmp_path: Path):
    command = importlib.import_module("backend.scripts.migrate_story_v3")
    destination = tmp_path / "story_v3"

    assert command.main(
        ["--source", str(V2_ROOT), "--destination", str(destination)]
    ) == 0
    assert StoryCompiler().compile(destination).diagnostics == ()
