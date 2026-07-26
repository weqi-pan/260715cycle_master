"""Lazy public exports for the story domain package."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "DiagnosticSeverity": ("app.story.diagnostics", "DiagnosticSeverity"),
    "PublishedRevision": ("app.story.publisher", "PublishedRevision"),
    "StoryCompilation": ("app.story.compiler", "StoryCompilation"),
    "StoryCompileError": ("app.story.diagnostics", "StoryCompileError"),
    "StoryCompiler": ("app.story.compiler", "StoryCompiler"),
    "StoryDiagnostic": ("app.story.diagnostics", "StoryDiagnostic"),
    "StoryPublisher": ("app.story.publisher", "StoryPublisher"),
    "StoryRevisionConflict": (
        "app.story.publisher",
        "StoryRevisionConflict",
    ),
    "StoryRevisionIntegrityError": (
        "app.story.publisher",
        "StoryRevisionIntegrityError",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve public types without importing compiler/schema eagerly."""

    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
