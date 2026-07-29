"""Render ordered Story System v3 content for the frontend."""

from ..schemas.game import ContentBlockView, GameState
from ..schemas.story_v3 import (
    ContentBlockV3,
    DialogueContentBlockV3,
    StoryNodeV3,
)

from .condition_eval import ConditionEvaluator


def visible_blocks(
    blocks: list[ContentBlockV3],
    state: GameState,
    evaluator: ConditionEvaluator,
) -> list[ContentBlockView]:
    """Return authored blocks whose typed conditions match, in source order."""

    rendered: list[ContentBlockView] = []
    for block in blocks:
        if not evaluator.check(block.when, state):
            continue
        rendered.append(
            ContentBlockView(
                id=block.id,
                type=block.type,
                text=block.text,
                speaker_id=(
                    block.speaker_id
                    if isinstance(block, DialogueContentBlockV3)
                    else None
                ),
            )
        )
    return rendered


def entry_blocks(
    node: StoryNodeV3,
    state: GameState,
    evaluator: ConditionEvaluator,
) -> list[ContentBlockView]:
    """Render only the first matching entry sequence for a node."""

    for sequence in node.entry_sequences:
        if evaluator.check(sequence.when, state):
            return visible_blocks(sequence.blocks, state, evaluator)
    return []
