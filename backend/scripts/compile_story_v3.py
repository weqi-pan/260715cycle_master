"""Compile and publish a Story System v3 authoring project."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.paths import STORY_BUILD_DIR, STORY_V3_DIR  # noqa: E402
from app.schemas.story_v3 import StorySnapshotV3  # noqa: E402
from app.story.compiler import StoryCompiler  # noqa: E402
from app.story.diagnostics import StoryDiagnostic  # noqa: E402
from app.story.publisher import (  # noqa: E402
    StoryPublisher,
    StoryRevisionConflict,
    StoryRevisionIntegrityError,
)


def _summary(snapshot: StorySnapshotV3) -> dict[str, int | str]:
    return {
        "revision": snapshot.revision,
        "node_count": len(snapshot.nodes),
        "choice_count": sum(
            len(node.choices) for node in snapshot.nodes.values()
        ),
        "content_block_count": sum(
            sum(
                len(sequence.blocks)
                for sequence in node.entry_sequences
            )
            + sum(
                len(choice.result)
                for choice in node.choices
            )
            for node in snapshot.nodes.values()
        ),
    }


def _print_diagnostic(diagnostic: StoryDiagnostic) -> None:
    print(
        json.dumps(
            asdict(diagnostic),
            ensure_ascii=False,
            sort_keys=True,
        ),
        file=sys.stderr,
    )


def _cli_error(
    code: str,
    message: str,
    location: str,
) -> StoryDiagnostic:
    return StoryDiagnostic(
        code=code,
        severity="error",
        message=message,
        location=location,
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=STORY_V3_DIR)
    parser.add_argument(
        "--build-root",
        type=Path,
        default=STORY_BUILD_DIR,
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    source_root = args.source.resolve()
    build_root = args.build_root.resolve()
    if build_root == source_root or source_root in build_root.parents:
        _print_diagnostic(
            _cli_error(
                "STORY_BUILD_ROOT_OVERLAP",
                (
                    "Story build root must not be the source root "
                    "or a descendant of it."
                ),
                "--build-root",
            )
        )
        return 1

    compilation = StoryCompiler().compile(source_root)
    for diagnostic in compilation.diagnostics:
        _print_diagnostic(diagnostic)

    has_errors = any(
        diagnostic.severity == "error"
        for diagnostic in compilation.diagnostics
    )
    has_strict_warnings = args.strict and any(
        diagnostic.severity == "warning"
        for diagnostic in compilation.diagnostics
    )
    if has_errors or has_strict_warnings:
        return 1

    publisher = StoryPublisher(build_root)
    try:
        base_revision = publisher.current_revision()
    except StoryRevisionIntegrityError:
        _print_diagnostic(
            _cli_error(
                "STORY_ACTIVE_REVISION_INVALID",
                "Active story revision could not be verified.",
                "build/current.json",
            )
        )
        return 1
    except OSError:
        _print_diagnostic(
            _cli_error(
                "STORY_ACTIVE_REVISION_IO_FAILED",
                "Active story revision could not be read.",
                "build/current.json",
            )
        )
        return 1

    try:
        publisher.publish(
            compilation,
            base_revision=base_revision,
        )
    except StoryRevisionConflict:
        _print_diagnostic(
            _cli_error(
                "STORY_PUBLISH_CONFLICT",
                "Active story revision changed during publication.",
                "build/current.json",
            )
        )
        return 1
    except StoryRevisionIntegrityError:
        _print_diagnostic(
            _cli_error(
                "STORY_PUBLISH_INTEGRITY_FAILED",
                "Published story revision failed integrity verification.",
                "build/revisions",
            )
        )
        return 1
    except OSError:
        _print_diagnostic(
            _cli_error(
                "STORY_PUBLISH_IO_FAILED",
                "Story publication could not be completed.",
                "build",
            )
        )
        return 1

    snapshot = compilation.require_success()
    print(
        json.dumps(
            _summary(snapshot),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
