"""Immutable, content-addressed publication for Story System v3."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from tempfile import NamedTemporaryFile, mkdtemp
from typing import Any

from pydantic import ValidationError

from ..schemas.story_v3 import StorySnapshotV3
from .compiler import StoryCompilation


_REVISION_PATTERN = re.compile(r"[0-9a-f]{64}")
_SNAPSHOT_NAME = "story.snapshot.json"
_MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True, slots=True)
class PublishedRevision:
    """A published immutable revision and its on-disk root."""

    revision: str
    root: Path


class StoryRevisionConflict(RuntimeError):
    """The active revision changed since an editor's last read."""

    def __init__(self, *, expected: str | None, actual: str | None):
        self.expected = expected
        self.actual = actual
        super().__init__(
            "Story revision conflict: "
            f"expected active revision {expected!r}, got {actual!r}."
        )


class StoryRevisionIntegrityError(RuntimeError):
    """A published pointer, manifest, or snapshot failed verification."""


class StoryPublisher:
    """Publish compiled snapshots without mutating authoring sources."""

    def __init__(self, build_root: Path):
        self.build_root = Path(build_root)

    @property
    def revisions_root(self) -> Path:
        return self.build_root / "revisions"

    @property
    def pointer_path(self) -> Path:
        return self.build_root / "current.json"

    def current_revision(self) -> str | None:
        """Return the active revision, or ``None`` before first publish."""

        if not self.pointer_path.exists():
            return None
        pointer = _read_json_object(
            self.pointer_path,
            description="active story pointer",
        )
        if set(pointer) != {"revision"}:
            raise StoryRevisionIntegrityError(
                "Active story pointer must contain only 'revision'."
            )
        revision = pointer["revision"]
        if not isinstance(revision, str) or not _is_revision(revision):
            raise StoryRevisionIntegrityError(
                "Active story pointer contains an invalid revision."
            )
        return revision

    def publish(
        self,
        compilation: StoryCompilation,
        *,
        base_revision: str | None,
    ) -> PublishedRevision:
        """Publish a successful compilation and atomically activate it."""

        snapshot = compilation.require_success()
        _require_content_addressed_snapshot(snapshot)
        current = self.current_revision()
        if current != base_revision:
            raise StoryRevisionConflict(
                expected=base_revision,
                actual=current,
            )
        revision_root = self._write_revision(snapshot)
        self._replace_pointer({"revision": snapshot.revision})
        return PublishedRevision(snapshot.revision, revision_root)

    def load_active(self) -> StorySnapshotV3:
        """Load and verify the currently active immutable snapshot."""

        revision = self.current_revision()
        if revision is None:
            raise FileNotFoundError(
                f"No active story revision at {self.pointer_path}."
            )
        return self._verify_revision(
            self.revisions_root / revision,
            revision,
        )

    def _write_revision(self, snapshot: StorySnapshotV3) -> Path:
        self.revisions_root.mkdir(parents=True, exist_ok=True)
        revision_root = self.revisions_root / snapshot.revision
        if revision_root.exists():
            self._verify_revision(
                revision_root,
                snapshot.revision,
                expected_snapshot=snapshot,
            )
            return revision_root

        temporary_root = Path(
            mkdtemp(
                dir=self.revisions_root,
                prefix=f".{snapshot.revision}.",
                suffix=".tmp",
            )
        )
        try:
            snapshot_bytes = _snapshot_bytes(snapshot)
            _write_file_durable(
                temporary_root / _SNAPSHOT_NAME,
                snapshot_bytes,
            )
            manifest = {
                "schema_version": 1,
                "revision": snapshot.revision,
                "files": {
                    _SNAPSHOT_NAME: {
                        "sha256": _sha256(snapshot_bytes),
                        "size": len(snapshot_bytes),
                    }
                },
            }
            _write_file_durable(
                temporary_root / _MANIFEST_NAME,
                _canonical_json_bytes(manifest),
            )
            _fsync_directory(temporary_root)
            try:
                temporary_root.replace(revision_root)
            except OSError:
                if not revision_root.exists():
                    raise
                self._verify_revision(
                    revision_root,
                    snapshot.revision,
                    expected_snapshot=snapshot,
                )
            _fsync_directory(self.revisions_root)
        finally:
            if temporary_root.exists():
                shutil.rmtree(temporary_root)
        return revision_root

    def _verify_revision(
        self,
        revision_root: Path,
        revision: str,
        *,
        expected_snapshot: StorySnapshotV3 | None = None,
    ) -> StorySnapshotV3:
        if not revision_root.is_dir():
            raise StoryRevisionIntegrityError(
                f"Story revision directory is missing: {revision}."
            )
        try:
            actual_entries = {
                entry.name for entry in revision_root.iterdir()
            }
        except OSError as exc:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} inventory could not be read."
            ) from exc
        expected_entries = {_MANIFEST_NAME, _SNAPSHOT_NAME}
        if actual_entries != expected_entries:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} has an invalid file inventory."
            )

        manifest = _read_json_object(
            revision_root / _MANIFEST_NAME,
            description=f"manifest for story revision {revision}",
        )
        if set(manifest) != {"schema_version", "revision", "files"}:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} has an invalid manifest."
            )
        if manifest["schema_version"] != 1 or manifest["revision"] != revision:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} has a mismatched manifest."
            )
        files = manifest["files"]
        if not isinstance(files, dict) or set(files) != {_SNAPSHOT_NAME}:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} has an invalid file manifest."
            )
        snapshot_metadata = files[_SNAPSHOT_NAME]
        if (
            not isinstance(snapshot_metadata, dict)
            or set(snapshot_metadata) != {"sha256", "size"}
            or not isinstance(snapshot_metadata["sha256"], str)
            or not isinstance(snapshot_metadata["size"], int)
        ):
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} has invalid snapshot metadata."
            )

        snapshot_path = revision_root / _SNAPSHOT_NAME
        try:
            snapshot_bytes = snapshot_path.read_bytes()
        except OSError as exc:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} snapshot could not be read."
            ) from exc
        if (
            len(snapshot_bytes) != snapshot_metadata["size"]
            or _sha256(snapshot_bytes) != snapshot_metadata["sha256"]
        ):
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} snapshot hash does not match."
            )
        try:
            snapshot = StorySnapshotV3.model_validate_json(snapshot_bytes)
        except (ValidationError, ValueError) as exc:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} snapshot is invalid."
            ) from exc
        if snapshot.revision != revision:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} snapshot identifies another revision."
            )
        try:
            _require_content_addressed_snapshot(snapshot)
        except StoryRevisionIntegrityError as exc:
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} snapshot content hash is invalid."
            ) from exc
        if (
            expected_snapshot is not None
            and snapshot_bytes != _snapshot_bytes(expected_snapshot)
        ):
            raise StoryRevisionIntegrityError(
                f"Story revision {revision} differs from compiled snapshot."
            )
        return snapshot

    def _replace_pointer(self, pointer: dict[str, str]) -> None:
        self.build_root.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                "wb",
                dir=self.build_root,
                prefix=".current.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(_canonical_json_bytes(pointer))
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.pointer_path)
            temporary = None
            _fsync_directory(self.build_root)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _snapshot_bytes(snapshot: StorySnapshotV3) -> bytes:
    return _canonical_json_bytes(snapshot.model_dump(mode="json"))


def _require_content_addressed_snapshot(snapshot: StorySnapshotV3) -> None:
    payload = snapshot.model_dump(mode="json")
    revision = payload.pop("revision")
    if not _is_revision(revision):
        raise StoryRevisionIntegrityError(
            "Compiled story snapshot has an invalid revision."
        )
    actual = _sha256(_canonical_json_bytes(payload))
    if revision != actual:
        raise StoryRevisionIntegrityError(
            "Compiled story snapshot revision does not match its content."
        )


def _write_file_durable(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _read_json_object(path: Path, *, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StoryRevisionIntegrityError(
            f"The {description} could not be read."
        ) from exc
    if not isinstance(payload, dict):
        raise StoryRevisionIntegrityError(
            f"The {description} must be a JSON object."
        )
    return payload


def _is_revision(value: str) -> bool:
    return _REVISION_PATTERN.fullmatch(value) is not None


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _fsync_directory(path: Path) -> None:
    """Best-effort directory metadata flush (unsupported on Windows)."""

    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
