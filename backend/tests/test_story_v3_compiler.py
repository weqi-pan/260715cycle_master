"""Whole-project compiler tests for Story System v3."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.story.compiler import StoryCompilation, StoryCompiler
from app.story.diagnostics import StoryCompileError, StoryDiagnostic
from app.story.publisher import (
    StoryRevisionConflict,
    StoryRevisionIntegrityError,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORY_V3_ROOT = PROJECT_ROOT / "data" / "story_v3"


def _run_compile_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.scripts.compile_story_v3",
            *args,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_json(path: Path, payload: dict, *, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _choice(
    choice_id: str,
    target: str,
    *,
    mode: str = "travel",
    condition: dict | None = None,
    effects: list[dict] | None = None,
    result: list[dict] | None = None,
) -> dict:
    return {
        "id": choice_id,
        "text": f"Choose {choice_id}",
        "availability": {
            "condition": condition,
            "locked_visibility": "show",
            "locked_reason": None,
        },
        "repeat_policy": "once_per_visit",
        "result": result or [],
        "effects": effects or [],
        "next": {"target": target, "mode": mode},
    }


def _node(
    node_id: str,
    *,
    choices: list[dict] | None = None,
    terminal: bool = False,
    node_type: str = "main",
    parent_node_id: str | None = None,
) -> dict:
    return {
        "schema_version": 3,
        "id": node_id,
        "meta": {
            "name": node_id,
            "node_type": node_type,
            "position": 0,
            "parent_node_id": parent_node_id,
            "terminal": (
                {"type": "ending", "ending_id": f"{node_id}_ending"}
                if terminal
                else None
            ),
        },
        "scene": {
            "background_id": "atrium_bg",
            "allow_no_background": False,
            "ambient_id": None,
        },
        "entry_sequences": [
            {
                "id": f"{node_id}_entry_default",
                "when": None,
                "blocks": [
                    {
                        "id": f"{node_id}_intro",
                        "type": "narration",
                        "text": f"Enter {node_id}",
                        "when": None,
                    }
                ],
            }
        ],
        "choices": choices or [],
        "routing": None,
        "authoring": {},
    }


def _write_node(root: Path, payload: dict, *, filename: str | None = None) -> None:
    _write_json(root / "nodes" / (filename or f"{payload['id']}.json"), payload)


def _mutate_json(path: Path, mutate) -> None:
    payload = _read_json(path)
    mutate(payload)
    _write_json(path, payload)


def _codes(compilation: StoryCompilation) -> set[str]:
    return {diagnostic.code for diagnostic in compilation.diagnostics}


def _error_codes(compilation: StoryCompilation) -> set[str]:
    return {
        diagnostic.code
        for diagnostic in compilation.diagnostics
        if diagnostic.severity == "error"
    }


def _code_locations(compilation: StoryCompilation) -> set[tuple[str, str]]:
    return {
        (diagnostic.code, diagnostic.location)
        for diagnostic in compilation.diagnostics
    }


@pytest.fixture
def story_root(tmp_path: Path) -> Path:
    root = tmp_path / "story_v3"
    _write_json(
        root / "project.json",
        {
            "schema_version": 3,
            "entry_node_id": "A",
            "attributes": {
                "trust": {
                    "display_name": "Trust",
                    "default": 1,
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
        },
    )
    _write_json(
        root / "assets.json",
        {
            "schema_version": 3,
            "assets": {
                "atrium_bg": {
                    "kind": "background",
                    "path": "resources/atrium.bin",
                },
                "ambient": {
                    "kind": "audio",
                    "path": "resources/ambient.bin",
                },
            },
        },
    )
    resources = root / "resources"
    resources.mkdir(parents=True)
    (resources / "atrium.bin").write_bytes(b"background")
    (resources / "ambient.bin").write_bytes(b"audio")
    _write_node(root, _node("A", choices=[_choice("A_to_B", "B")]))
    _write_node(root, _node("B", terminal=True))
    return root


def test_diagnostic_is_immutable():
    diagnostic = StoryDiagnostic(
        code="STORY_TEST",
        severity="error",
        message="test",
        location="project.json",
    )

    with pytest.raises(FrozenInstanceError):
        diagnostic.code = "CHANGED"


def test_valid_project_compiles_to_snapshot(story_root: Path):
    compilation = StoryCompiler().compile(story_root)

    snapshot = compilation.require_success()
    assert compilation.diagnostics == ()
    assert snapshot.project.entry_node_id == "A"
    assert list(snapshot.nodes) == ["A", "B"]
    assert len(snapshot.revision) == 64


def test_require_success_raises_structured_compile_error(story_root: Path):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"][0]["next"].update(target="MISSING"),
    )

    compilation = StoryCompiler().compile(story_root)

    with pytest.raises(StoryCompileError) as raised:
        compilation.require_success()
    assert raised.value.diagnostics == compilation.diagnostics
    assert "STORY_TARGET_MISSING" in {
        diagnostic.code for diagnostic in raised.value.diagnostics
    }


def test_compiler_rejects_missing_target(story_root: Path):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"][0]["next"].update(target="MISSING"),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_TARGET_MISSING",
        "nodes/A.json#/choices/0/next/target",
    ) in _code_locations(result)


def test_compiler_rejects_unreachable_node(story_root: Path):
    _write_node(story_root, _node("ORPHAN", terminal=True))

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_NODE_UNREACHABLE",
        "nodes/ORPHAN.json#/id",
    ) in _code_locations(result)


def test_compiler_rejects_parent_that_disagrees_with_incoming_edge(
    story_root: Path,
):
    sub_node = _node(
        "S1",
        choices=[_choice("S1_to_B", "B")],
        node_type="normal",
        parent_node_id="B",
    )
    _write_node(story_root, sub_node)
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node.update(
            choices=[_choice("A_to_S1", "S1")]
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert "STORY_PARENT_MISMATCH" in _error_codes(result)
    assert "STORY_RETURN_TARGET_MISMATCH" in _error_codes(result)


def test_normal_sub_node_requires_declared_parent(story_root: Path):
    sub_node = _node(
        "S1",
        choices=[_choice("S1_return", "A")],
        node_type="normal",
        parent_node_id=None,
    )
    _write_node(story_root, sub_node)
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"].append(_choice("A_to_S1", "S1")),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_PARENT_MISMATCH",
        "nodes/S1.json#/meta/parent_node_id",
    ) in _code_locations(result)


def test_normal_sub_node_rejects_multiple_incoming_owners(
    story_root: Path,
):
    sub_node = _node(
        "S1",
        choices=[_choice("S1_return", "A")],
        node_type="normal",
        parent_node_id="A",
    )
    _write_node(story_root, sub_node)
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"].append(_choice("A_to_S1", "S1")),
    )
    _mutate_json(
        story_root / "nodes" / "B.json",
        lambda node: node.update(
            choices=[_choice("B_to_S1", "S1")],
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_PARENT_AMBIGUOUS",
        "nodes/S1.json#/meta/parent_node_id",
    ) in _code_locations(result)


def test_self_loop_is_not_counted_as_sub_node_owner(story_root: Path):
    sub_node = _node(
        "S1",
        choices=[
            _choice("S1_wait", "S1", mode="stay"),
            _choice("S1_return", "A"),
        ],
        node_type="normal",
        parent_node_id="A",
    )
    _write_node(story_root, sub_node)
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"].append(_choice("A_to_S1", "S1")),
    )

    result = StoryCompiler().compile(story_root)

    assert "STORY_PARENT_AMBIGUOUS" not in _codes(result)
    assert "STORY_PARENT_MISMATCH" not in _codes(result)
    assert "STORY_RETURN_TARGET_MISMATCH" not in _codes(result)
    result.require_success()


def test_compiler_requires_sub_node_return_to_owner(story_root: Path):
    sub_node = _node(
        "S1",
        choices=[_choice("S1_to_B", "B")],
        node_type="normal",
        parent_node_id="A",
    )
    _write_node(story_root, sub_node)
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"].append(_choice("A_to_S1", "S1")),
    )

    result = StoryCompiler().compile(story_root)

    assert "STORY_RETURN_TARGET_MISMATCH" in _error_codes(result)


def test_compiler_rejects_each_sub_node_edge_that_bypasses_owner(
    story_root: Path,
):
    sub_node = _node(
        "S1",
        choices=[
            _choice("S1_return", "A"),
            _choice("S1_bypass", "B"),
        ],
        node_type="normal",
        parent_node_id="A",
    )
    _write_node(story_root, sub_node)
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"].append(_choice("A_to_S1", "S1")),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_RETURN_TARGET_MISMATCH",
        "nodes/S1.json#/choices/1/next/target",
    ) in _code_locations(result)


def test_compiler_rejects_condition_outside_attribute_domain(
    story_root: Path,
):
    _mutate_json(
        story_root / "project.json",
        lambda project: project["attributes"]["trust"].update(maximum=2),
    )
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"][0]["availability"].update(
            condition={
                "type": "attribute_compare",
                "attribute": "trust",
                "operator": "gte",
                "value": 3,
            }
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_CONDITION_IMPOSSIBLE",
        "nodes/A.json#/choices/0/availability/condition",
    ) in _code_locations(result)


def test_compiler_hash_is_independent_of_json_formatting(story_root: Path):
    first = StoryCompiler().compile(story_root).require_success().revision
    for path in story_root.rglob("*.json"):
        _write_json(path, _read_json(path), indent=4)

    second = StoryCompiler().compile(story_root).require_success().revision

    assert second == first


def test_revision_is_canonical_manifest_checksum(story_root: Path):
    snapshot = StoryCompiler().compile(story_root).require_success()
    payload = {
        "schema_version": 3,
        "project": snapshot.project.model_dump(mode="json"),
        "assets": snapshot.assets.model_dump(mode="json"),
        "nodes": {
            node_id: node.model_dump(mode="json")
            for node_id, node in snapshot.nodes.items()
        },
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert snapshot.revision == hashlib.sha256(canonical).hexdigest()


def test_compiler_rejects_duplicate_global_choice_ids(story_root: Path):
    _mutate_json(
        story_root / "nodes" / "B.json",
        lambda node: node.update(
            choices=[_choice("A_to_B", "B", mode="stay")]
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_CHOICE_ID_DUPLICATE",
        "nodes/B.json#/choices/0/id",
    ) in _code_locations(result)


def test_compiler_rejects_duplicate_global_block_ids(story_root: Path):
    _mutate_json(
        story_root / "nodes" / "B.json",
        lambda node: node["entry_sequences"][0]["blocks"][0].update(
            id="A_intro"
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_BLOCK_ID_DUPLICATE",
        "nodes/B.json#/entry_sequences/0/blocks/0/id",
    ) in _code_locations(result)


def test_compiler_rejects_node_id_defined_by_multiple_files(story_root: Path):
    duplicate = _node("A", terminal=True)
    _write_node(story_root, duplicate, filename="COPY.json")

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_NODE_ID_DUPLICATE",
        "nodes/COPY.json#/id",
    ) in _code_locations(result)


def test_compiler_requires_unconditional_default_entry(story_root: Path):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["entry_sequences"][0].update(
            when={
                "type": "flag_equals",
                "flag": "door_open",
                "value": True,
            }
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_DEFAULT_ENTRY_MISSING",
        "nodes/A.json#/entry_sequences",
    ) in _code_locations(result)


def test_compiler_rejects_missing_project_entry_node(story_root: Path):
    _mutate_json(
        story_root / "project.json",
        lambda project: project.update(entry_node_id="MISSING"),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ENTRY_MISSING",
        "project.json#/entry_node_id",
    ) in _code_locations(result)


@pytest.mark.parametrize(
    ("mutate", "location"),
    [
        pytest.param(
            lambda node: node["choices"][0]["availability"].update(
                condition={
                    "type": "flag_equals",
                    "flag": "missing_flag",
                    "value": True,
                }
            ),
            "nodes/A.json#/choices/0/availability/condition/flag",
            id="condition-flag",
        ),
        pytest.param(
            lambda node: node["choices"][0].update(
                effects=[
                    {
                        "type": "inventory",
                        "item_id": "missing_item",
                        "operation": "add",
                        "quantity": 1,
                    }
                ]
            ),
            "nodes/A.json#/choices/0/effects/0/item_id",
            id="effect-item",
        ),
        pytest.param(
            lambda node: node["entry_sequences"][0]["blocks"].append(
                {
                    "id": "guide_line",
                    "type": "dialogue",
                    "speaker_id": "missing_npc",
                    "text": "Hello",
                    "when": None,
                }
            ),
            "nodes/A.json#/entry_sequences/0/blocks/1/speaker_id",
            id="dialogue-speaker",
        ),
    ],
)
def test_compiler_rejects_missing_registry_references(
    story_root: Path,
    mutate,
    location: str,
):
    _mutate_json(story_root / "nodes" / "A.json", mutate)

    result = StoryCompiler().compile(story_root)

    assert ("STORY_REGISTRY_REFERENCE_MISSING", location) in _code_locations(
        result
    )


def test_compiler_rejects_resource_path_that_escapes_root(story_root: Path):
    _mutate_json(
        story_root / "assets.json",
        lambda assets: assets["assets"]["atrium_bg"].update(
            path="../outside.bin"
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ASSET_PATH_INVALID",
        "assets.json#/assets/atrium_bg/path",
    ) in _code_locations(result)


@pytest.mark.parametrize(
    "asset_path",
    [
        pytest.param("/absolute/asset.bin", id="posix-absolute"),
        pytest.param(r"C:\absolute\asset.bin", id="windows-drive-absolute"),
        pytest.param(r"C:drive-relative\asset.bin", id="windows-drive-relative"),
        pytest.param(
            "\\\\server\\share\\asset.bin",
            id="windows-unc",
        ),
        pytest.param(r"\root-relative\asset.bin", id="windows-root-relative"),
        pytest.param(
            "resources/../resources/atrium.bin",
            id="posix-parent-segment-inside-root",
        ),
        pytest.param(
            r"resources\..\resources\atrium.bin",
            id="windows-parent-segment-inside-root",
        ),
    ],
)
def test_compiler_rejects_cross_platform_unsafe_asset_path_syntax(
    story_root: Path,
    asset_path: str,
):
    _mutate_json(
        story_root / "assets.json",
        lambda assets: assets["assets"]["atrium_bg"].update(
            path=asset_path
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ASSET_PATH_INVALID",
        "assets.json#/assets/atrium_bg/path",
    ) in _code_locations(result)


def test_compiler_rejects_missing_resource_file(story_root: Path):
    (story_root / "resources" / "atrium.bin").unlink()

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ASSET_FILE_MISSING",
        "assets.json#/assets/atrium_bg/path",
    ) in _code_locations(result)


def test_compiler_rejects_missing_or_wrong_kind_scene_asset(
    story_root: Path,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["scene"].update(
            background_id="missing_asset",
            ambient_id="atrium_bg",
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ASSET_MISSING",
        "nodes/A.json#/scene/background_id",
    ) in _code_locations(result)
    assert (
        "STORY_ASSET_KIND_MISMATCH",
        "nodes/A.json#/scene/ambient_id",
    ) in _code_locations(result)


def test_compiler_rejects_filename_and_node_id_mismatch(story_root: Path):
    (story_root / "nodes" / "A.json").rename(
        story_root / "nodes" / "WRONG.json"
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_NODE_FILENAME_MISMATCH",
        "nodes/WRONG.json#/id",
    ) in _code_locations(result)


def test_compiler_rejects_reachable_non_terminal_dead_end(story_root: Path):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node.update(choices=[]),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_NODE_DEAD_END",
        "nodes/A.json#/choices",
    ) in _code_locations(result)


def test_compiler_turns_invalid_json_into_structured_diagnostic(
    story_root: Path,
):
    (story_root / "nodes" / "A.json").write_text("{", encoding="utf-8")

    result = StoryCompiler().compile(story_root)

    assert result.snapshot is None
    assert (
        "STORY_JSON_INVALID",
        "nodes/A.json",
    ) in _code_locations(result)
    assert all(diagnostic.severity == "error" for diagnostic in result.diagnostics)


def test_compiler_turns_schema_error_into_structured_diagnostic(
    story_root: Path,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"][0]["next"].update(mode="teleport"),
    )

    result = StoryCompiler().compile(story_root)

    assert result.snapshot is None
    assert (
        "STORY_SOURCE_INVALID",
        "nodes/A.json#/choices/0/next/mode",
    ) in _code_locations(result)


def test_compiler_turns_node_directory_enumeration_failure_into_diagnostic(
    story_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    original_glob = Path.glob

    def fail_node_enumeration(path: Path, pattern: str):
        if path == story_root / "nodes":
            raise PermissionError("denied")
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", fail_node_enumeration)

    try:
        result = StoryCompiler().compile(story_root)
    except PermissionError:
        pytest.fail("node directory enumeration escaped StoryCompiler.compile")

    assert result.snapshot is None
    assert _code_locations(result) == {
        ("STORY_SOURCE_READ_FAILED", "nodes")
    }


def test_compiler_stops_after_node_read_failure(
    story_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"][0]["next"].update(target="MISSING"),
    )
    original_read_text = Path.read_text

    def fail_node_read(
        path: Path,
        *args,
        **kwargs,
    ):
        if path == story_root / "nodes" / "B.json":
            raise PermissionError("denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_node_read)

    result = StoryCompiler().compile(story_root)

    assert result.snapshot is None
    assert _code_locations(result) == {
        ("STORY_SOURCE_READ_FAILED", "nodes/B.json")
    }


def test_compiler_validates_crossing_choice_and_npc_references(
    story_root: Path,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node.update(
            routing={
                "type": "crossing",
                "trigger_time": "midnight",
                "target_era": "past",
                "max_deep_interactions": 1,
                "deep_interactions": [
                    {
                        "choice_id": "missing_choice",
                        "npc_id": "missing_npc",
                    }
                ],
            }
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ROUTING_CHOICE_MISSING",
        "nodes/A.json#/routing/deep_interactions/0/choice_id",
    ) in _code_locations(result)
    assert (
        "STORY_REGISTRY_REFERENCE_MISSING",
        "nodes/A.json#/routing/deep_interactions/0/npc_id",
    ) in _code_locations(result)


def test_compiler_validates_warp_targets_and_exit_cost_references(
    story_root: Path,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node.update(
            choices=[_choice("A_warp", "B", mode="warp")],
            routing={
                "type": "warp",
                "entry_condition": {
                    "type": "flag_equals",
                    "flag": "door_open",
                    "value": True,
                },
                "allowed_targets": ["MISSING"],
                "exit_effects": [
                    {
                        "type": "modify_attribute",
                        "attribute": "missing_attribute",
                        "operation": "add",
                        "value": -1,
                        "clamp": True,
                    }
                ],
                "sacrifice_target": None,
            },
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ROUTING_TARGET_MISSING",
        "nodes/A.json#/routing/allowed_targets/0",
    ) in _code_locations(result)
    assert (
        "STORY_WARP_TARGET_NOT_ALLOWED",
        "nodes/A.json#/choices/0/next/target",
    ) in _code_locations(result)
    assert (
        "STORY_REGISTRY_REFERENCE_MISSING",
        "nodes/A.json#/routing/exit_effects/0/attribute",
    ) in _code_locations(result)


def test_compiler_validates_shortcut_endpoints_and_condition_references(
    story_root: Path,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node.update(
            routing={
                "type": "shortcut",
                "entry_condition": {
                    "type": "at_node",
                    "node_id": "MISSING_CONDITION_NODE",
                },
                "entry_node_id": "MISSING_ENTRY",
                "exit_node_id": "MISSING_EXIT",
                "counter_effects": [],
            }
        ),
    )

    result = StoryCompiler().compile(story_root)

    locations = _code_locations(result)
    assert (
        "STORY_REGISTRY_REFERENCE_MISSING",
        "nodes/A.json#/routing/entry_condition/node_id",
    ) in locations
    assert (
        "STORY_ROUTING_TARGET_MISSING",
        "nodes/A.json#/routing/entry_node_id",
    ) in locations
    assert (
        "STORY_ROUTING_TARGET_MISSING",
        "nodes/A.json#/routing/exit_node_id",
    ) in locations


@pytest.mark.parametrize(
    ("mode", "routing"),
    [
        pytest.param(
            "warp",
            {
                "type": "shortcut",
                "entry_condition": {
                    "type": "flag_equals",
                    "flag": "door_open",
                    "value": True,
                },
                "entry_node_id": "A",
                "exit_node_id": "B",
                "counter_effects": [],
            },
            id="warp-choice-shortcut-routing",
        ),
        pytest.param(
            "shortcut",
            {
                "type": "warp",
                "entry_condition": {
                    "type": "flag_equals",
                    "flag": "door_open",
                    "value": True,
                },
                "allowed_targets": ["B"],
                "exit_effects": [
                    {
                        "type": "modify_attribute",
                        "attribute": "trust",
                        "operation": "add",
                        "value": -1,
                        "clamp": True,
                    }
                ],
                "sacrifice_target": None,
            },
            id="shortcut-choice-warp-routing",
        ),
        pytest.param(
            "warp",
            {
                "type": "crossing",
                "trigger_time": "midnight",
                "target_era": "past",
                "max_deep_interactions": 1,
                "deep_interactions": [
                    {"choice_id": "A_special", "npc_id": "guide"}
                ],
            },
            id="special-choice-crossing-routing",
        ),
    ],
)
def test_compiler_rejects_special_choice_routing_variant_mismatch(
    story_root: Path,
    mode: str,
    routing: dict,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node.update(
            choices=[_choice("A_special", "B", mode=mode)],
            routing=routing,
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_ROUTING_MISMATCH",
        "nodes/A.json#/choices/0/next/mode",
    ) in _code_locations(result)


def test_compiler_rejects_choice_mode_not_declared_by_project(
    story_root: Path,
):
    _mutate_json(
        story_root / "project.json",
        lambda project: project.update(
            jump_modes=["stay", "shortcut", "warp"]
        ),
    )

    result = StoryCompiler().compile(story_root)

    assert (
        "STORY_JUMP_MODE_UNDECLARED",
        "nodes/A.json#/choices/0/next/mode",
    ) in _code_locations(result)


def test_compile_cli_strict_publishes_canonical_story_and_reuses_revision(
    tmp_path: Path,
):
    build_root = tmp_path / "build"

    first = _run_compile_cli(
        "--source",
        str(STORY_V3_ROOT),
        "--build-root",
        str(build_root),
        "--strict",
    )

    pointer = json.loads(
        (build_root / "current.json").read_text(encoding="utf-8")
    )
    revision = pointer["revision"]
    expected_summary = {
        "choice_count": 143,
        "content_block_count": 846,
        "node_count": 30,
        "revision": revision,
    }
    revision_root = build_root / "revisions" / revision
    snapshot_path = revision_root / "story.snapshot.json"
    manifest_path = revision_root / "manifest.json"
    old_timestamp = 1_000_000_000
    os.utime(snapshot_path, ns=(old_timestamp, old_timestamp))
    os.utime(manifest_path, ns=(old_timestamp, old_timestamp))

    second = _run_compile_cli(
        "--source",
        str(STORY_V3_ROOT),
        "--build-root",
        str(build_root),
        "--strict",
    )

    expected_stdout = (
        json.dumps(expected_summary, ensure_ascii=False, sort_keys=True) + "\n"
    )
    assert first.returncode == 0, first.stderr
    assert first.stdout == expected_stdout
    assert first.stderr == ""
    assert second.returncode == 0, second.stderr
    assert second.stdout == expected_stdout
    assert second.stderr == ""
    assert [path.name for path in (build_root / "revisions").iterdir()] == [
        revision
    ]
    assert snapshot_path.stat().st_mtime_ns == old_timestamp
    assert manifest_path.stat().st_mtime_ns == old_timestamp


def test_compile_cli_failure_prints_stable_diagnostics_without_activating(
    story_root: Path,
    tmp_path: Path,
):
    _mutate_json(
        story_root / "nodes" / "A.json",
        lambda node: node["choices"][0]["next"].update(target="MISSING"),
    )
    build_root = tmp_path / "build"

    result = _run_compile_cli(
        "--source",
        str(story_root),
        "--build-root",
        str(build_root),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        json.dumps(
            {
                "code": "STORY_TARGET_MISSING",
                "location": "nodes/A.json#/choices/0/next/target",
                "message": "Choice target 'MISSING' does not name a node.",
                "severity": "error",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        json.dumps(
            {
                "code": "STORY_NODE_UNREACHABLE",
                "location": "nodes/B.json#/id",
                "message": "Node 'B' is unreachable from project entry.",
                "severity": "error",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    ]
    assert not (build_root / "current.json").exists()


@pytest.mark.parametrize(
    "build_relative",
    [
        pytest.param(Path("."), id="same-as-source"),
        pytest.param(Path("nodes") / "build", id="nested-under-source"),
    ],
)
def test_compile_cli_rejects_build_root_inside_source_without_mutation(
    story_root: Path,
    build_relative: Path,
):
    source_before = _tree_bytes(story_root)
    build_root = story_root / build_relative

    result = _run_compile_cli(
        "--source",
        str(story_root),
        "--build-root",
        str(build_root),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        json.dumps(
            {
                "code": "STORY_BUILD_ROOT_OVERLAP",
                "location": "--build-root",
                "message": (
                    "Story build root must not be the source root "
                    "or a descendant of it."
                ),
                "severity": "error",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    assert "Traceback" not in result.stderr
    assert _tree_bytes(story_root) == source_before
    assert not (build_root / "current.json").exists()
    assert not (build_root / "revisions").exists()


def test_compile_cli_rejects_overlap_before_compiler_construction(
    story_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    from backend.scripts import compile_story_v3

    class UnexpectedCompiler:
        def __init__(self):
            pytest.fail("overlap reached compiler construction")

    monkeypatch.setattr(
        compile_story_v3,
        "StoryCompiler",
        UnexpectedCompiler,
    )

    returncode = compile_story_v3.main(
        [
            "--source",
            str(story_root),
            "--build-root",
            str(story_root / "nodes" / "build"),
        ]
    )

    captured = capsys.readouterr()
    assert returncode == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "code": "STORY_BUILD_ROOT_OVERLAP",
        "location": "--build-root",
        "message": (
            "Story build root must not be the source root "
            "or a descendant of it."
        ),
        "severity": "error",
    }


def test_compile_cli_rejects_resolved_build_alias_inside_source(
    story_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    from backend.scripts import compile_story_v3

    source_before = _tree_bytes(story_root)
    source_alias = tmp_path / "source_alias"
    try:
        source_alias.symlink_to(story_root, target_is_directory=True)
    except NotImplementedError as exc:
        pytest.skip(f"directory symlink creation is unavailable: {exc}")
    except OSError as exc:
        unsupported = (
            exc.errno in {errno.EACCES, errno.ENOSYS, errno.EPERM}
            or getattr(exc, "winerror", None) == 1314
        )
        if not unsupported:
            raise
        pytest.skip(f"directory symlink creation is unavailable: {exc}")
    aliased_build_root = source_alias / "nodes" / "build"

    class UnexpectedCompiler:
        def __init__(self):
            pytest.fail("resolved overlap reached compiler construction")

    monkeypatch.setattr(
        compile_story_v3,
        "StoryCompiler",
        UnexpectedCompiler,
    )

    returncode = compile_story_v3.main(
        [
            "--source",
            str(story_root),
            "--build-root",
            str(aliased_build_root),
        ]
    )

    captured = capsys.readouterr()
    assert returncode == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "code": "STORY_BUILD_ROOT_OVERLAP",
        "location": "--build-root",
        "message": (
            "Story build root must not be the source root "
            "or a descendant of it."
        ),
        "severity": "error",
    }
    assert _tree_bytes(story_root) == source_before
    assert not (story_root / "nodes" / "build").exists()


def test_compile_cli_allows_sibling_build_root(
    story_root: Path,
):
    source_before = _tree_bytes(story_root)
    build_root = story_root.parent / "build"

    result = _run_compile_cli(
        "--source",
        str(story_root),
        "--build-root",
        str(build_root),
        "--strict",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["node_count"] == 2
    assert (build_root / "current.json").exists()
    assert _tree_bytes(story_root) == source_before


def test_compile_cli_corrupt_active_pointer_is_stable_failure(
    story_root: Path,
    tmp_path: Path,
):
    build_root = tmp_path / "build"
    initial = _run_compile_cli(
        "--source",
        str(story_root),
        "--build-root",
        str(build_root),
    )
    assert initial.returncode == 0, initial.stderr
    pointer_path = build_root / "current.json"
    corrupt_pointer = b'{"revision":"not-a-revision"}'
    pointer_path.write_bytes(corrupt_pointer)

    result = _run_compile_cli(
        "--source",
        str(story_root),
        "--build-root",
        str(build_root),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        json.dumps(
            {
                "code": "STORY_ACTIVE_REVISION_INVALID",
                "location": "build/current.json",
                "message": "Active story revision could not be verified.",
                "severity": "error",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    assert "Traceback" not in result.stderr
    assert pointer_path.read_bytes() == corrupt_pointer


def test_compile_cli_active_pointer_io_failure_is_stable_and_preserves_pointer(
    story_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    from backend.scripts import compile_story_v3

    build_root = tmp_path / "build"
    assert (
        compile_story_v3.main(
            [
                "--source",
                str(story_root),
                "--build-root",
                str(build_root),
            ]
        )
        == 0
    )
    capsys.readouterr()
    pointer_path = build_root / "current.json"
    pointer_before = pointer_path.read_bytes()

    def fail_current_revision(self):
        raise OSError("permission denied")

    monkeypatch.setattr(
        compile_story_v3.StoryPublisher,
        "current_revision",
        fail_current_revision,
    )

    try:
        returncode = compile_story_v3.main(
            [
                "--source",
                str(story_root),
                "--build-root",
                str(build_root),
            ]
        )
    except OSError:
        pytest.fail("active pointer I/O failure escaped compile CLI")

    captured = capsys.readouterr()
    assert returncode == 1
    assert captured.out == ""
    assert captured.err == (
        json.dumps(
            {
                "code": "STORY_ACTIVE_REVISION_IO_FAILED",
                "location": "build/current.json",
                "message": "Active story revision could not be read.",
                "severity": "error",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    assert "Traceback" not in captured.err
    assert pointer_path.read_bytes() == pointer_before


@pytest.mark.parametrize(
    ("failure", "expected_diagnostic"),
    [
        pytest.param(
            StoryRevisionConflict(
                expected="0" * 64,
                actual="f" * 64,
            ),
            {
                "code": "STORY_PUBLISH_CONFLICT",
                "location": "build/current.json",
                "message": "Active story revision changed during publication.",
                "severity": "error",
            },
            id="conflict",
        ),
        pytest.param(
            StoryRevisionIntegrityError("invalid revision"),
            {
                "code": "STORY_PUBLISH_INTEGRITY_FAILED",
                "location": "build/revisions",
                "message": "Published story revision failed integrity verification.",
                "severity": "error",
            },
            id="integrity",
        ),
        pytest.param(
            OSError("disk full"),
            {
                "code": "STORY_PUBLISH_IO_FAILED",
                "location": "build",
                "message": "Story publication could not be completed.",
                "severity": "error",
            },
            id="io",
        ),
    ],
)
def test_compile_cli_publication_failure_is_stable_and_preserves_pointer(
    story_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: Exception,
    expected_diagnostic: dict,
):
    from backend.scripts import compile_story_v3

    build_root = tmp_path / "build"
    assert (
        compile_story_v3.main(
            [
                "--source",
                str(story_root),
                "--build-root",
                str(build_root),
            ]
        )
        == 0
    )
    capsys.readouterr()
    pointer_path = build_root / "current.json"
    pointer_before = pointer_path.read_bytes()

    def fail_publish(self, compilation, *, base_revision):
        raise failure

    monkeypatch.setattr(
        compile_story_v3.StoryPublisher,
        "publish",
        fail_publish,
    )

    try:
        returncode = compile_story_v3.main(
            [
                "--source",
                str(story_root),
                "--build-root",
                str(build_root),
            ]
        )
    except (StoryRevisionConflict, StoryRevisionIntegrityError, OSError):
        pytest.fail("known publication failure escaped compile CLI")

    captured = capsys.readouterr()
    assert returncode == 1
    assert captured.out == ""
    assert captured.err == (
        json.dumps(
            expected_diagnostic,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    assert pointer_path.read_bytes() == pointer_before


def test_compile_cli_real_pointer_replace_failure_preserves_active_pointer(
    story_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    from backend.scripts import compile_story_v3

    build_root = tmp_path / "build"
    assert (
        compile_story_v3.main(
            [
                "--source",
                str(story_root),
                "--build-root",
                str(build_root),
            ]
        )
        == 0
    )
    first_summary = json.loads(capsys.readouterr().out)
    pointer_path = build_root / "current.json"
    pointer_before = pointer_path.read_bytes()
    _mutate_json(
        story_root / "nodes" / "B.json",
        lambda node: node["meta"].update(name="Changed B"),
    )

    def fail_before_pointer_replace(self, pointer):
        raise OSError("pointer replace denied")

    monkeypatch.setattr(
        compile_story_v3.StoryPublisher,
        "_replace_pointer",
        fail_before_pointer_replace,
    )

    returncode = compile_story_v3.main(
        [
            "--source",
            str(story_root),
            "--build-root",
            str(build_root),
        ]
    )

    captured = capsys.readouterr()
    assert returncode == 1
    assert captured.out == ""
    assert captured.err == (
        json.dumps(
            {
                "code": "STORY_PUBLISH_IO_FAILED",
                "location": "build",
                "message": "Story publication could not be completed.",
                "severity": "error",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    assert pointer_path.read_bytes() == pointer_before
    assert json.loads(pointer_before)["revision"] == first_summary["revision"]
    assert len(list((build_root / "revisions").iterdir())) == 2


def test_compile_cli_strict_rejects_warnings_without_activating(
    story_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    from backend.scripts import compile_story_v3

    compilation = StoryCompiler().compile(story_root)
    warning = StoryDiagnostic(
        code="STORY_TEST_WARNING",
        severity="warning",
        message="A stable warning.",
        location="project.json",
    )
    warned = StoryCompilation(
        snapshot=compilation.require_success(),
        diagnostics=(warning,),
    )

    class WarningCompiler:
        def compile(self, source: Path) -> StoryCompilation:
            return warned

    monkeypatch.setattr(compile_story_v3, "StoryCompiler", WarningCompiler)
    build_root = tmp_path / "build"

    returncode = compile_story_v3.main(
        [
            "--source",
            str(story_root),
            "--build-root",
            str(build_root),
            "--strict",
        ]
    )

    captured = capsys.readouterr()
    assert returncode == 1
    assert captured.out == ""
    assert captured.err == (
        json.dumps(
            {
                "code": "STORY_TEST_WARNING",
                "location": "project.json",
                "message": "A stable warning.",
                "severity": "warning",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    assert not (build_root / "current.json").exists()
