"""Executable contract tests for the closed Story System v3 authoring schema."""

from copy import deepcopy

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.story_v3 import (
    AssetDefinitionV3,
    AssetCatalogV3,
    AttributeDefinitionV3,
    ConditionV3,
    StoryNodeV3,
    StoryProjectV3,
    StorySnapshotV3,
    TerminalSpecV3,
)


def make_node_v3(
    *,
    choice_ids: list[str] | None = None,
    entry_ids: list[str] | None = None,
) -> dict:
    choices = choice_ids or ["inspect"]
    entries = entry_ids or ["default"]
    return {
        "schema_version": 3,
        "id": "A",
        "meta": {
            "name": "Atrium",
            "node_type": "normal",
            "position": 0,
            "terminal": None,
        },
        "scene": {
            "background_id": None,
            "allow_no_background": True,
        },
        "entry_sequences": [
            {
                "id": entry_id,
                "when": None,
                "blocks": [
                    {
                        "id": f"{entry_id}_narration",
                        "type": "narration",
                        "text": f"Entry {entry_id}",
                        "when": None,
                    }
                ],
            }
            for entry_id in entries
        ],
        "choices": [
            {
                "id": choice_id,
                "text": f"Choose {choice_id}",
                "availability": {
                    "condition": {
                        "type": "flag_equals",
                        "flag": "door_open",
                        "value": True,
                    },
                    "locked_visibility": "hide",
                    "locked_reason": None,
                },
                "repeat_policy": "once_per_visit",
                "result": [
                    {
                        "id": f"{choice_id}_result",
                        "type": "dialogue",
                        "speaker_id": "guide",
                        "text": f"Result {choice_id}",
                        "when": None,
                    }
                ],
                "effects": [
                    {
                        "type": "modify_attribute",
                        "attribute": "trust",
                        "operation": "add",
                        "value": 1,
                    }
                ],
                "next": {"target": "A", "mode": "stay"},
            }
            for choice_id in choices
        ],
        "routing": {
            "type": "crossing",
            "trigger_time": "midnight",
            "target_era": "past",
            "max_deep_interactions": 1,
            "deep_interactions": [
                {"choice_id": choices[0], "npc_id": "guide"}
            ],
        },
        "authoring": {},
    }


def test_schema_version_is_required():
    payload = make_node_v3()
    payload.pop("schema_version")
    with pytest.raises(ValidationError, match="schema_version"):
        StoryNodeV3.model_validate(payload)


def test_unknown_fields_are_rejected():
    payload = make_node_v3()
    payload["routing"]["fake_runtime_option"] = True
    with pytest.raises(ValidationError, match="extra"):
        StoryNodeV3.model_validate(payload)


def test_choice_order_is_array_order():
    node = StoryNodeV3.model_validate(
        make_node_v3(choice_ids=["later", "first"])
    )
    assert [choice.id for choice in node.choices] == ["later", "first"]
    assert all("priority" not in choice.model_dump() for choice in node.choices)


def test_entry_sequence_order_is_array_order():
    node = StoryNodeV3.model_validate(
        make_node_v3(entry_ids=["fallback", "specific"])
    )
    assert [entry.id for entry in node.entry_sequences] == [
        "fallback",
        "specific",
    ]
    assert all(
        "priority" not in entry.model_dump() for entry in node.entry_sequences
    )


def test_condition_requires_known_discriminator():
    payload = make_node_v3()
    payload["choices"][0]["availability"]["condition"] = {
        "type": "python",
        "code": "True",
    }
    with pytest.raises(ValidationError):
        StoryNodeV3.model_validate(payload)


def test_effect_requires_known_discriminator():
    payload = make_node_v3()
    payload["choices"][0]["effects"] = [
        {"type": "python", "code": "state.clear()"}
    ]
    with pytest.raises(ValidationError):
        StoryNodeV3.model_validate(payload)


def test_recursive_condition_tree_is_typed():
    condition = TypeAdapter(ConditionV3).validate_python(
        {
            "type": "all",
            "conditions": [
                {
                    "type": "attribute_compare",
                    "attribute": "trust",
                    "operator": "gte",
                    "value": 3,
                },
                {
                    "type": "not",
                    "condition": {
                        "type": "item",
                        "item_id": "forbidden_key",
                        "present": True,
                    },
                },
            ],
        }
    )
    assert condition.type == "all"
    assert condition.conditions[1].type == "not"
    assert condition.conditions[1].condition.type == "item"


def test_v3_rejects_string_conditions():
    payload = make_node_v3()
    payload["choices"][0]["availability"]["condition"] = "cycle>=2"
    with pytest.raises(ValidationError):
        StoryNodeV3.model_validate(payload)


def test_stay_must_target_owner():
    payload = make_node_v3()
    payload["choices"][0]["next"] = {"target": "B", "mode": "stay"}
    with pytest.raises(ValidationError, match="stay"):
        StoryNodeV3.model_validate(payload)


def test_dialogue_requires_speaker_id():
    payload = make_node_v3()
    payload["choices"][0]["result"][0].pop("speaker_id")
    with pytest.raises(ValidationError, match="speaker_id"):
        StoryNodeV3.model_validate(payload)


def test_non_dialogue_block_rejects_speaker_id():
    payload = make_node_v3()
    payload["entry_sequences"][0]["blocks"][0]["speaker_id"] = "guide"
    with pytest.raises(ValidationError, match="speaker_id|extra"):
        StoryNodeV3.model_validate(payload)


def test_content_block_ids_are_unique_within_node():
    payload = make_node_v3()
    payload["choices"][0]["result"][0]["id"] = (
        payload["entry_sequences"][0]["blocks"][0]["id"]
    )
    with pytest.raises(ValidationError, match="block ids"):
        StoryNodeV3.model_validate(payload)


def test_scene_must_explicitly_allow_missing_background():
    payload = make_node_v3()
    payload["scene"].pop("allow_no_background")
    with pytest.raises(ValidationError, match="allow_no_background"):
        StoryNodeV3.model_validate(payload)


def test_node_must_explicitly_declare_terminal_state():
    payload = make_node_v3()
    payload["meta"].pop("terminal")
    with pytest.raises(ValidationError, match="terminal"):
        StoryNodeV3.model_validate(payload)


@pytest.mark.parametrize(
    "routing",
    [
        {
            "type": "crossing",
            "trigger_time": "midnight",
            "target_era": "past",
            "max_deep_interactions": 1,
            "deep_interactions": [{"choice_id": "inspect", "npc_id": "guide"}],
        },
        {
            "type": "shortcut",
            "entry_condition": {
                "type": "at_node",
                "node_id": "A",
            },
            "entry_node_id": "A",
            "exit_node_id": "B",
            "counter_effects": [
                {
                    "type": "modify_counter",
                    "counter": "completed_cycles",
                    "operation": "add",
                    "value": 1,
                }
            ],
        },
        {
            "type": "warp",
            "entry_condition": {
                "type": "counter_compare",
                "counter": "current_cycle",
                "operator": "gte",
                "value": 2,
            },
            "allowed_targets": ["B"],
            "exit_effects": [
                {
                    "type": "inventory",
                    "item_id": "token",
                    "operation": "remove",
                    "quantity": 1,
                }
            ],
        },
    ],
)
def test_routing_variants_are_typed(routing):
    payload = make_node_v3()
    payload["routing"] = routing
    assert StoryNodeV3.model_validate(payload).routing.type == routing["type"]


def test_unknown_routing_variant_is_rejected():
    payload = make_node_v3()
    payload["routing"] = {"type": "script", "code": "go('B')"}
    with pytest.raises(ValidationError):
        StoryNodeV3.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("id",), "../A"),
        (("choices", 0, "id"), "NUL"),
        (("choices", 0, "effects", 0, "attribute"), "trust.score"),
    ],
)
def test_story_ids_use_the_shared_validator(path, value):
    payload = make_node_v3()
    cursor = payload
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value
    with pytest.raises(ValidationError, match="invalid story id"):
        StoryNodeV3.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        pytest.param(
            StoryProjectV3,
            {
                "schema_version": 3,
                "entry_node_id": "A",
                "attributes": {},
                "flags": {},
                "items": {},
                "npcs": {},
                "counters": [],
                "jump_modes": [],
                "runtime_hook": "unsafe",
            },
            id="project-root",
        ),
        pytest.param(
            AttributeDefinitionV3,
            {
                "display_name": "Trust",
                "default": 0,
                "minimum": 0,
                "maximum": 10,
                "runtime_formula": "dynamic",
            },
            id="project-registry-value",
        ),
        pytest.param(
            AssetCatalogV3,
            {
                "schema_version": 3,
                "assets": {},
                "cdn_base_url": "https://example.invalid",
            },
            id="asset-catalog-root",
        ),
        pytest.param(
            AssetDefinitionV3,
            {
                "kind": "background",
                "path": "backgrounds/atrium.webp",
                "browser_url": "https://example.invalid/atrium.webp",
            },
            id="asset-definition",
        ),
        pytest.param(
            TerminalSpecV3,
            {
                "type": "ending",
                "ending_id": "atrium_ending",
                "runtime_callback": "roll_credits",
            },
            id="terminal-metadata",
        ),
        pytest.param(
            StorySnapshotV3,
            {
                "schema_version": 3,
                "revision": "sha256-test",
                "project": {
                    "schema_version": 3,
                    "entry_node_id": "A",
                    "attributes": {},
                    "flags": {},
                    "items": {},
                    "npcs": {},
                    "counters": [],
                    "jump_modes": [],
                },
                "assets": {"schema_version": 3, "assets": {}},
                "nodes": {},
                "mutable": True,
            },
            id="snapshot-root",
        ),
    ],
)
def test_public_v3_contract_boundaries_reject_unknown_fields(model, payload):
    with pytest.raises(ValidationError, match="extra"):
        model.model_validate(payload)


def test_project_assets_terminal_and_snapshot_are_closed_typed_models():
    project = StoryProjectV3.model_validate(
        {
            "schema_version": 3,
            "entry_node_id": "A",
            "attributes": {
                "trust": {
                    "display_name": "Trust",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 10,
                }
            },
            "flags": {
                "door_open": {
                    "display_name": "Door open",
                    "default": False,
                }
            },
            "items": {
                "token": {
                    "display_name": "Token",
                    "discardable": True,
                    "cross_surface": False,
                }
            },
            "npcs": {"guide": {"display_name": "Guide"}},
            "counters": ["completed_cycles", "half_cycles"],
            "jump_modes": ["stay", "travel", "shortcut", "warp"],
        }
    )
    assets = AssetCatalogV3.model_validate(
        {
            "schema_version": 3,
            "assets": {
                "atrium_bg": {
                    "kind": "background",
                    "path": "backgrounds/atrium.webp",
                }
            },
        }
    )
    terminal_node = make_node_v3()
    terminal_node["meta"]["terminal"] = {
        "type": "ending",
        "ending_id": "atrium_ending",
    }
    snapshot = StorySnapshotV3.model_validate(
        {
            "schema_version": 3,
            "revision": "sha256-test",
            "project": project.model_dump(),
            "assets": assets.model_dump(),
            "nodes": {"A": terminal_node},
        }
    )

    assert snapshot.project.entry_node_id == "A"
    assert snapshot.assets.assets["atrium_bg"].path.endswith(".webp")
    assert snapshot.nodes["A"].meta.terminal.type == "ending"


def test_snapshot_rejects_invalid_node_dictionary_key():
    valid = make_node_v3()
    payload = {
        "schema_version": 3,
        "revision": "sha256-test",
        "project": {
            "schema_version": 3,
            "entry_node_id": "A",
            "attributes": {},
            "flags": {},
            "items": {},
            "npcs": {},
            "counters": [],
            "jump_modes": [],
        },
        "assets": {"schema_version": 3, "assets": {}},
        "nodes": {"../A": deepcopy(valid)},
    }
    with pytest.raises(ValidationError, match="invalid story id"):
        StorySnapshotV3.model_validate(payload)
