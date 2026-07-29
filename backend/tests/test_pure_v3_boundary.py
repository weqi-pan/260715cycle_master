"""Repository boundary checks for the pure Story System v3 demo."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.database import Base
from app.engine.condition_eval import ConditionEvaluator
from app.engine.engine import GameEngine
from app.schemas.game import GameState


FORBIDDEN_PATHS = (
    "data/story_data_v2",
    "backend/app/schemas/story_v2.py",
    "backend/app/engine/story_v2_loader.py",
    "backend/app/engine/graph.py",
    "backend/app/engine/special_router.py",
    "backend/app/story/v2_migration.py",
    "backend/scripts/migrate_story_v3.py",
    "backend/scripts/validate_story_v2.py",
    "backend/app/editor",
    "backend/app/routers/editor.py",
    "backend/app/schemas/editor.py",
    "backend/app/models/story.py",
    "backend/app/domain/items.py",
    "backend/app/domain/npcs.py",
    "backend/tests/test_story_v2_editor.py",
    "backend/tests/test_story_v2_runtime.py",
    "backend/tests/test_story_v2_schema.py",
    "backend/tests/test_story_v2_validation.py",
    "backend/tests/test_story_v3_migration.py",
    "backend/tests/test_condition_eval.py",
    "backend/tests/test_engine.py",
    "backend/tests/test_choice_visibility.py",
    "backend/tests/test_inventory_actions.py",
    "backend/tests/test_phase1_5_regressions.py",
    "frontend/src/views/EditorLayout.vue",
    "frontend/src/components/editor",
    "tests/e2e/test_phase3_editor.py",
    "scripts/audit_phase1_5.py",
    "docs/design/故事内容格式规范-v2.md",
)

ACTIVE_ROOTS = (
    "backend/app",
    "backend/scripts",
    "frontend/src",
    "scripts",
)

FORBIDDEN_ACTIVE_TOKENS = (
    "story_data_v2",
    "story_v2",
    "StoryV2",
    "validate_story_v2",
    "migrate_story_v3",
    "GraphBundle",
    "GraphLoader",
    "special_router",
    "models.story",
    "domain.items",
    "domain.npcs",
    "STORY_DATA_DIR",
    "STORY_DATA_V2_DIR",
    "/api/editor",
    "path: '/editor'",
    "EditorLayout",
)


def test_v2_editor_and_migration_paths_are_removed(project_root: Path):
    remaining = [path for path in FORBIDDEN_PATHS if (project_root / path).exists()]

    assert remaining == []


def test_active_code_has_no_v2_or_editor_dependencies(project_root: Path):
    offenders: list[str] = []
    for relative_root in ACTIVE_ROOTS:
        root = project_root / relative_root
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".vue"}:
                continue
            text = path.read_text(encoding="utf-8")
            matched = [token for token in FORBIDDEN_ACTIVE_TOKENS if token in text]
            if matched:
                offenders.append(
                    f"{path.relative_to(project_root).as_posix()}: {', '.join(matched)}"
                )

    assert offenders == []


def test_game_engine_exposes_only_v3_gameplay_entry_points():
    legacy_methods = {
        "process_choice",
        "resolve_available_choices",
        "_apply_effects",
        "_resolve_content",
        "_resolve_text",
    }

    assert legacy_methods.isdisjoint(dir(GameEngine))


def test_database_metadata_has_no_story_authoring_tables():
    assert {"story_nodes", "choices"}.isdisjoint(Base.metadata.tables)


def test_backend_package_imports_from_repository_root(project_root: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.app.main import app; print(app.title)",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Cycle Master API"


def test_condition_evaluator_rejects_string_conditions():
    with pytest.raises(TypeError, match="Unsupported v3 condition"):
        ConditionEvaluator().check(
            "has_flag:legacy",
            GameState(current_node_id="A"),
        )
