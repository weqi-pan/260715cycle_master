"""Story v3 immutable snapshot loading for the gameplay process."""

from __future__ import annotations

import json

import pytest

from app.engine.story_v3_repository import StoryV3Repository
from app.story.compiler import StoryCompilation
from app.story.diagnostics import StoryCompileError, StoryDiagnostic
from app.story.publisher import StoryRevisionIntegrityError


def test_snapshot_is_unavailable_before_refresh(tmp_path):
    repository = StoryV3Repository(tmp_path / "source", tmp_path / "build")

    with pytest.raises(RuntimeError, match="Story v3 runtime is not loaded"):
        _ = repository.snapshot


def test_refresh_compiles_publishes_and_loads_snapshot(tmp_path, copy_story_v3):
    source = copy_story_v3(tmp_path / "source")
    build = tmp_path / "build"
    repository = StoryV3Repository(source, build)

    snapshot = repository.refresh()

    assert snapshot.project.entry_node_id == "A"
    assert repository.snapshot is snapshot
    assert json.loads((build / "current.json").read_text(encoding="utf-8")) == {
        "revision": snapshot.revision
    }
    assert (
        build / "revisions" / snapshot.revision / "story.snapshot.json"
    ).is_file()


def test_refresh_keeps_previous_snapshot_when_new_source_is_invalid(
    tmp_path, copy_story_v3
):
    source = copy_story_v3(tmp_path / "source")
    repository = StoryV3Repository(source, tmp_path / "build")
    previous = repository.refresh()
    (source / "nodes" / "A.json").write_text("{}", encoding="utf-8")

    with pytest.raises(StoryCompileError):
        repository.refresh()

    assert repository.snapshot is previous


def test_refresh_treats_compiler_warnings_as_strict_failure(
    tmp_path, copy_story_v3, monkeypatch
):
    source = copy_story_v3(tmp_path / "source")
    repository = StoryV3Repository(source, tmp_path / "build")
    previous = repository.refresh()
    warning = StoryDiagnostic(
        code="TEST_WARNING",
        severity="warning",
        message="A stable warning.",
        location="project.json",
    )

    class WarningCompiler:
        def compile(self, _source_root):
            return StoryCompilation(
                snapshot=previous,
                diagnostics=(warning,),
            )

    monkeypatch.setattr(
        "app.engine.story_v3_repository.StoryCompiler",
        WarningCompiler,
    )

    with pytest.raises(StoryCompileError) as raised:
        repository.refresh()

    assert raised.value.diagnostics == (warning,)
    assert repository.snapshot is previous


def test_refresh_keeps_previous_snapshot_when_active_revision_is_corrupt(
    tmp_path, copy_story_v3
):
    source = copy_story_v3(tmp_path / "source")
    build = tmp_path / "build"
    repository = StoryV3Repository(source, build)
    previous = repository.refresh()
    snapshot_path = (
        build / "revisions" / previous.revision / "story.snapshot.json"
    )
    snapshot_path.write_text("{}", encoding="utf-8")

    with pytest.raises(StoryRevisionIntegrityError):
        repository.refresh()

    assert repository.snapshot is previous


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_application_startup_loads_v3_before_initializing_database(monkeypatch):
    from app import main

    events: list[str] = []
    monkeypatch.setattr(
        main.game.story,
        "refresh",
        lambda: events.append("story_v3"),
    )
    monkeypatch.setattr(main, "init_db", lambda: events.append("database"))

    main.on_startup()

    assert events == ["story_v3", "database"]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_application_startup_propagates_story_compile_failure(monkeypatch):
    from app import main

    diagnostic = StoryDiagnostic(
        code="STARTUP_STORY_INVALID",
        severity="error",
        message="The active story cannot start.",
        location="project.json",
    )
    failure = StoryCompileError((diagnostic,))
    database_initialized = False

    def fail_refresh():
        raise failure

    def record_database_initialization():
        nonlocal database_initialized
        database_initialized = True

    monkeypatch.setattr(main.game.story, "refresh", fail_refresh)
    monkeypatch.setattr(main, "init_db", record_database_initialization)

    with pytest.raises(StoryCompileError) as raised:
        main.on_startup()

    assert raised.value is failure
    assert database_initialized is False
