"""Migrate the canonical Story System v2 corpus to v3 authoring files."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.story.compiler import StoryCompiler  # noqa: E402
from app.story.v2_migration import migrate_project  # noqa: E402


DEFAULT_SOURCE = PROJECT_ROOT / "data" / "story_data_v2"
DEFAULT_DESTINATION = PROJECT_ROOT / "data" / "story_v3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args(argv)

    migrate_project(args.source.resolve(), args.destination.resolve())
    compilation = StoryCompiler().compile(args.destination)
    if compilation.diagnostics:
        for diagnostic in compilation.diagnostics:
            print(
                json.dumps(
                    asdict(diagnostic),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
        return 1

    snapshot = compilation.require_success()
    summary = {
        "revision": snapshot.revision,
        "node_count": len(snapshot.nodes),
        "choice_count": sum(
            len(node.choices) for node in snapshot.nodes.values()
        ),
        "content_block_count": sum(
            sum(len(sequence.blocks) for sequence in node.entry_sequences)
            + sum(len(choice.result) for choice in node.choices)
            for node in snapshot.nodes.values()
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
