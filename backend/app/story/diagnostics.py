"""Stable structured diagnostics for Story System v3 compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DiagnosticSeverity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class StoryDiagnostic:
    """One immutable compiler finding with a machine-stable identity."""

    code: str
    severity: DiagnosticSeverity
    message: str
    location: str


class StoryCompileError(Exception):
    """Raised when a compilation with structured errors is required."""

    def __init__(self, diagnostics: tuple[StoryDiagnostic, ...]):
        self.diagnostics = diagnostics
        error_count = sum(
            diagnostic.severity == "error" for diagnostic in diagnostics
        )
        super().__init__(
            f"story compilation failed with {error_count} error(s)"
        )
