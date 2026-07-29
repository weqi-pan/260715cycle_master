"""Strictly compile, publish, and load the active Story System v3 snapshot."""

from __future__ import annotations

from pathlib import Path

from ..schemas.story_v3 import StorySnapshotV3
from ..story.compiler import StoryCompiler
from ..story.diagnostics import StoryCompileError
from ..story.publisher import StoryPublisher


class StoryV3Repository:
    """Own the last fully verified immutable v3 runtime snapshot."""

    def __init__(self, source_root: Path, build_root: Path):
        self.source_root = Path(source_root)
        self.build_root = Path(build_root)
        self._snapshot: StorySnapshotV3 | None = None

    @property
    def snapshot(self) -> StorySnapshotV3:
        if self._snapshot is None:
            raise RuntimeError("Story v3 runtime is not loaded.")
        return self._snapshot

    def refresh(self) -> StorySnapshotV3:
        compilation = StoryCompiler().compile(self.source_root)
        if any(
            diagnostic.severity == "warning"
            for diagnostic in compilation.diagnostics
        ):
            raise StoryCompileError(compilation.diagnostics)
        snapshot = compilation.require_success()

        publisher = StoryPublisher(self.build_root)
        active_revision = publisher.current_revision()
        if active_revision != snapshot.revision:
            publisher.publish(
                compilation,
                base_revision=active_revision,
            )

        loaded = publisher.load_active()
        self._snapshot = loaded
        return loaded
