"""Export the canonical JSON Schema for Story System v3 node sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.paths import STORY_V3_DIR  # noqa: E402
from app.schemas.story_v3 import StoryNodeV3  # noqa: E402


DEFAULT_DESTINATION = STORY_V3_DIR / "story-node-v3.schema.json"


def export_schema(destination: Path) -> None:
    """Write the validation schema in a deterministic UTF-8 form."""

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = StoryNodeV3.model_json_schema(mode="validation")
    content = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    destination.write_bytes(content.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_DESTINATION,
    )
    args = parser.parse_args(argv)

    export_schema(args.destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
