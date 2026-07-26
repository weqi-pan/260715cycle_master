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
from app.story.publisher import StoryPublisher  # noqa: E402


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

    compilation = StoryCompiler().compile(args.source.resolve())
    if compilation.snapshot is not None:
        print(
            json.dumps(
                _summary(compilation.snapshot),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    for diagnostic in compilation.diagnostics:
        print(
            json.dumps(
                asdict(diagnostic),
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )

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

    publisher = StoryPublisher(args.build_root.resolve())
    publisher.publish(
        compilation,
        base_revision=publisher.current_revision(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
