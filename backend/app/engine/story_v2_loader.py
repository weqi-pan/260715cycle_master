"""剧情 JSON v2 的只读运行时内容仓库。"""

from __future__ import annotations

import json
from pathlib import Path

from ..paths import DATA_DIR
from ..schemas.game import GameState
from ..schemas.story_v2 import ContentBlock, StoryNodeV2, VARIABLE_TEMPLATE_RE
from .condition_eval import ConditionEvaluator
from .graph import GraphBundle


class StoryV2Loader:
    """加载 v2 内容块，并为游戏引擎提供唯一的剧情运行图。"""

    def __init__(self, root: Path | None = None):
        self.root = root or (DATA_DIR / "story_data_v2" / "nodes")
        self.nodes = self._load_all()

    def _load_all(self) -> dict[str, StoryNodeV2]:
        if not self.root.is_dir():
            raise RuntimeError(f"Story v2 directory not found: {self.root}")
        nodes: dict[str, StoryNodeV2] = {}
        for path in sorted(self.root.glob("*.json")):
            node = StoryNodeV2.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
            if node.id in nodes:
                raise RuntimeError(f"Duplicate story v2 node: {node.id}")
            nodes[node.id] = node
        if not nodes:
            raise RuntimeError(f"No story v2 nodes found: {self.root}")
        return nodes

    def load_graph(self) -> dict[str, GraphBundle]:
        """从 v2 文件构建完整运行图，不读取 SQLite 故事表。"""
        return {
            node_id: GraphBundle.from_story_v2(node)
            for node_id, node in self.nodes.items()
        }

    @staticmethod
    def _resolved_blocks(
        blocks: list[ContentBlock],
        state: GameState,
        evaluator: ConditionEvaluator,
    ) -> list[ContentBlock]:
        variables = {
            "cycle_count": state.cycle_count,
            "half_cycle_count": state.half_cycle_count,
        }

        def interpolate(text: str) -> str:
            def replace(match):
                name = match.group(1)
                if name not in variables:
                    raise ValueError(f"unsupported story variable: {name}")
                return str(variables[name])

            return VARIABLE_TEMPLATE_RE.sub(replace, text)

        return [
            block.model_copy(update={
                "text": interpolate(block.text),
                "when": None,
            })
            for block in blocks
            if evaluator.check(block.when, state)
        ]

    def entry_blocks(
        self,
        node_id: str,
        state: GameState,
        evaluator: ConditionEvaluator,
    ) -> list[ContentBlock]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        matching = [
            sequence
            for sequence in node.entry_sequences
            if evaluator.check(sequence.when, state)
        ]
        if not matching:
            return []
        sequence = max(matching, key=lambda item: item.priority)
        return self._resolved_blocks(sequence.blocks, state, evaluator)

    def result_blocks(
        self,
        node_id: str,
        choice_id: str,
        state: GameState,
        evaluator: ConditionEvaluator,
    ) -> list[ContentBlock]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        choice = next((item for item in node.choices if item.id == choice_id), None)
        if not choice:
            return []
        return self._resolved_blocks(choice.result_blocks, state, evaluator)
