"""Atomic publication tests for Story System v3 snapshots."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.schemas.story_v3 import StorySnapshotV3
from app.story.compiler import StoryCompilation
from app.story.diagnostics import StoryCompileError
from app.story.publisher import (
    StoryPublisher,
    StoryRevisionConflict,
    StoryRevisionIntegrityError,
)


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _add_unmanifested_file(revision_root: Path) -> None:
    (revision_root / "unmanifested.bin").write_bytes(b"unexpected")


def _add_unmanifested_directory(revision_root: Path) -> None:
    (revision_root / "unmanifested").mkdir()


def _compilation(label: str) -> StoryCompilation:
    node_id = f"node_{label}"
    snapshot_payload = {
        "schema_version": 3,
        "project": {
            "schema_version": 3,
            "entry_node_id": node_id,
            "attributes": {},
            "flags": {},
            "items": {},
            "npcs": {},
            "counters": ["completed_cycles", "half_cycles"],
            "jump_modes": ["stay", "travel", "shortcut", "warp"],
        },
        "assets": {"schema_version": 3, "assets": {}},
        "nodes": {
            node_id: {
                "schema_version": 3,
                "id": node_id,
                "meta": {
                    "name": f"Node {label}",
                    "node_type": "main",
                    "position": 0,
                    "time_label": None,
                    "parent_node_id": None,
                    "terminal": {
                        "type": "ending",
                        "ending_id": f"ending_{label}",
                    },
                },
                "scene": {
                    "background_id": None,
                    "allow_no_background": True,
                    "ambient_id": None,
                    "palette": None,
                    "atmosphere": [],
                },
                "entry_sequences": [
                    {
                        "id": f"entry_{label}",
                        "when": None,
                        "blocks": [
                            {
                                "id": f"block_{label}",
                                "type": "narration",
                                "text": f"Story {label}",
                                "when": None,
                            }
                        ],
                    }
                ],
                "choices": [],
                "routing": None,
                "authoring": {
                    "trigger_description": None,
                    "npcs_present": [],
                    "scene_items": [],
                    "npc_item_notes": [],
                    "sensory": None,
                    "gender_variant": None,
                    "notes": [],
                },
            }
        },
    }
    normalized = StorySnapshotV3.model_validate(
        {"revision": "0" * 64, **snapshot_payload}
    ).model_dump(mode="json")
    normalized.pop("revision")
    revision = hashlib.sha256(_canonical_bytes(normalized)).hexdigest()
    snapshot = StorySnapshotV3.model_validate(
        {"revision": revision, **normalized}
    )
    return StoryCompilation(snapshot=snapshot, diagnostics=())


@pytest.fixture
def first_compilation() -> StoryCompilation:
    return _compilation("first")


@pytest.fixture
def second_compilation() -> StoryCompilation:
    return _compilation("second")


@pytest.mark.parametrize(
    "prelude",
    [
        pytest.param(
            "import app.schemas.story_v3\n",
            id="schema-first",
        ),
        pytest.param(
            "import app.story\n",
            id="story-first",
        ),
    ],
)
def test_public_story_imports_are_order_independent(prelude: str):
    backend_root = Path(__file__).parents[1]
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            prelude
            + (
                "from app.story import (\n"
                "    DiagnosticSeverity,\n"
                "    PublishedRevision,\n"
                "    StoryCompilation,\n"
                "    StoryCompileError,\n"
                "    StoryCompiler,\n"
                "    StoryDiagnostic,\n"
                "    StoryPublisher,\n"
                "    StoryRevisionConflict,\n"
                "    StoryRevisionIntegrityError,\n"
                ")\n"
                "assert StoryPublisher.__name__ == 'StoryPublisher'\n"
                "assert StoryCompiler.__name__ == 'StoryCompiler'\n"
            ),
        ],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr


def test_publish_writes_content_addressed_revision_and_pointer(
    tmp_path: Path,
    first_compilation: StoryCompilation,
):
    publisher = StoryPublisher(tmp_path / "build")

    published = publisher.publish(first_compilation, base_revision=None)

    snapshot_path = published.root / "story.snapshot.json"
    manifest_path = published.root / "manifest.json"
    assert published.root == (
        tmp_path / "build" / "revisions" / published.revision
    )
    assert snapshot_path.exists()
    assert manifest_path.exists()
    assert json.loads((tmp_path / "build" / "current.json").read_text()) == {
        "revision": published.revision
    }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_bytes = snapshot_path.read_bytes()
    assert manifest == {
        "schema_version": 1,
        "revision": published.revision,
        "files": {
            "story.snapshot.json": {
                "sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
                "size": len(snapshot_bytes),
            }
        },
    }
    assert publisher.load_active().revision == published.revision


def test_stale_base_revision_is_rejected(
    tmp_path: Path,
    first_compilation: StoryCompilation,
    second_compilation: StoryCompilation,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    second = publisher.publish(
        second_compilation,
        base_revision=first.revision,
    )

    with pytest.raises(StoryRevisionConflict) as raised:
        publisher.publish(
            first_compilation,
            base_revision=first.revision,
        )

    assert raised.value.expected == first.revision
    assert raised.value.actual == second.revision
    assert publisher.load_active().revision == second.revision


def test_pointer_replace_failure_keeps_previous_revision_active(
    tmp_path: Path,
    first_compilation: StoryCompilation,
    second_compilation: StoryCompilation,
    monkeypatch: pytest.MonkeyPatch,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)

    def raise_disk_error(_pointer: dict[str, str]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(publisher, "_replace_pointer", raise_disk_error)

    with pytest.raises(OSError, match="disk full"):
        publisher.publish(
            second_compilation,
            base_revision=first.revision,
        )

    assert StoryPublisher(tmp_path / "build").load_active().revision == (
        first.revision
    )


def test_reusing_existing_revision_verifies_snapshot_hash(
    tmp_path: Path,
    first_compilation: StoryCompilation,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    (first.root / "story.snapshot.json").write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(StoryRevisionIntegrityError):
        publisher.publish(
            first_compilation,
            base_revision=first.revision,
        )


def test_existing_valid_revision_is_reused_without_rewriting_files(
    tmp_path: Path,
    first_compilation: StoryCompilation,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    snapshot_path = first.root / "story.snapshot.json"
    manifest_path = first.root / "manifest.json"
    old_timestamp = 1_000_000_000
    os.utime(snapshot_path, ns=(old_timestamp, old_timestamp))
    os.utime(manifest_path, ns=(old_timestamp, old_timestamp))

    second = publisher.publish(
        first_compilation,
        base_revision=first.revision,
    )

    assert second == first
    assert snapshot_path.stat().st_mtime_ns == old_timestamp
    assert manifest_path.stat().st_mtime_ns == old_timestamp


def test_reusing_existing_revision_verifies_manifest_revision(
    tmp_path: Path,
    first_compilation: StoryCompilation,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    manifest_path = first.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["revision"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(StoryRevisionIntegrityError):
        publisher.publish(
            first_compilation,
            base_revision=first.revision,
        )


@pytest.mark.parametrize(
    "add_entry",
    [
        pytest.param(_add_unmanifested_file, id="file"),
        pytest.param(_add_unmanifested_directory, id="directory"),
    ],
)
def test_reusing_existing_revision_rejects_unmanifested_entry(
    tmp_path: Path,
    first_compilation: StoryCompilation,
    add_entry,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    add_entry(first.root)

    with pytest.raises(StoryRevisionIntegrityError):
        publisher.publish(
            first_compilation,
            base_revision=first.revision,
        )


@pytest.mark.parametrize(
    "add_entry",
    [
        pytest.param(_add_unmanifested_file, id="file"),
        pytest.param(_add_unmanifested_directory, id="directory"),
    ],
)
def test_load_active_rejects_unmanifested_entry(
    tmp_path: Path,
    first_compilation: StoryCompilation,
    add_entry,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    add_entry(first.root)

    with pytest.raises(StoryRevisionIntegrityError):
        publisher.load_active()


def test_load_active_rejects_pointer_snapshot_revision_mismatch(
    tmp_path: Path,
    first_compilation: StoryCompilation,
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    pointer_path = tmp_path / "build" / "current.json"
    pointer_path.write_text(
        json.dumps({"revision": "f" * 64}),
        encoding="utf-8",
    )

    with pytest.raises(StoryRevisionIntegrityError):
        publisher.load_active()

    assert first.root.exists()


def test_pointer_is_replaced_from_same_directory(
    tmp_path: Path,
    first_compilation: StoryCompilation,
    monkeypatch: pytest.MonkeyPatch,
):
    publisher = StoryPublisher(tmp_path / "build")
    original_replace = Path.replace
    replacements: list[tuple[Path, Path]] = []

    def record_replace(source: Path, target: Path):
        replacements.append((source, Path(target)))
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", record_replace)

    publisher.publish(first_compilation, base_revision=None)

    pointer_replacements = [
        (source, target)
        for source, target in replacements
        if target.name == "current.json"
    ]
    assert len(pointer_replacements) == 1
    source, target = pointer_replacements[0]
    assert source.parent == target.parent == tmp_path / "build"


def test_failed_compilation_creates_no_build_files(tmp_path: Path):
    publisher = StoryPublisher(tmp_path / "build")
    compilation = StoryCompilation(snapshot=None, diagnostics=())

    with pytest.raises(StoryCompileError):
        publisher.publish(compilation, base_revision=None)

    assert not (tmp_path / "build").exists()
