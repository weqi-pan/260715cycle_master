"""只读校验 data/story_data_v2 的契约、引用和可达性。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.story_v2 import StoryNodeV2  # noqa: E402


DEFAULT_ROOT = PROJECT_ROOT / "data" / "story_data_v2"


def duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def validate(root: Path) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    nodes: list[StoryNodeV2] = []

    node_dir = root / "nodes"
    if not node_dir.is_dir():
        return [f"missing nodes directory: {node_dir}"], [], {}

    node_paths = sorted(node_dir.glob("*.json"))
    if not node_paths:
        errors.append("story contains no node files")

    for path in node_paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            nodes.append(StoryNodeV2.model_validate(raw))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    node_ids = [node.id for node in nodes]
    for node_id in duplicates(node_ids):
        errors.append(f"duplicate node id: {node_id}")
    node_id_set = set(node_ids)

    choice_ids = [choice.id for node in nodes for choice in node.choices]
    for choice_id in duplicates(choice_ids):
        errors.append(f"duplicate choice id: {choice_id}")

    block_ids = [
        block.id
        for node in nodes
        for sequence in node.entry_sequences
        for block in sequence.blocks
    ] + [
        block.id
        for node in nodes
        for choice in node.choices
        for block in choice.result_blocks
    ]
    for block_id in duplicates(block_ids):
        errors.append(f"duplicate content block id: {block_id}")

    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_id_set}
    for node in nodes:
        if not any(sequence.when is None for sequence in node.entry_sequences):
            errors.append(f"{node.id}: missing default entry sequence")
        for choice in node.choices:
            if choice.next.node_id not in node_id_set:
                errors.append(
                    f"{choice.id}: missing target node {choice.next.node_id}"
                )
            else:
                adjacency[node.id].add(choice.next.node_id)

    reachable = {"A"} if "A" in node_id_set else set()
    while True:
        before = len(reachable)
        for node_id in list(reachable):
            reachable.update(adjacency.get(node_id, set()))
        if len(reachable) == before:
            break

    unreachable = sorted(node_id_set - reachable)
    if unreachable:
        warnings.append(f"nodes unreachable from A: {', '.join(unreachable)}")

    summary = {
        "node_count": len(nodes),
        "choice_count": len(choice_ids),
        "entry_block_count": sum(
            len(sequence.blocks) for node in nodes for sequence in node.entry_sequences
        ),
        "result_block_count": sum(
            len(choice.result_blocks) for node in nodes for choice in node.choices
        ),
        "dialogue_block_count": sum(
            block.type == "dialogue"
            for node in nodes
            for sequence in node.entry_sequences
            for block in sequence.blocks
        )
        + sum(
            block.type == "dialogue"
            for node in nodes
            for choice in node.choices
            for block in choice.result_blocks
        ),
        "reachable_count": len(reachable),
        "unreachable_nodes": unreachable,
    }
    return errors, warnings, summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    errors, warnings, summary = validate(args.root.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for error in errors:
        print(f"ERROR {error}")
    for warning in warnings:
        print(f"WARN  {warning}")

    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
