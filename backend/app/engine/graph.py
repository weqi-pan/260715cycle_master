# backend/app/engine/graph.py
import json
from sqlalchemy.orm import Session
from ..models.story import StoryNode as StoryNodeModel, Choice as ChoiceModel


class GraphBundle:
    """一个节点的完整数据：节点本体 + 它的所有选择。"""
    def __init__(self, node: StoryNodeModel, choices: list[ChoiceModel]):
        self.id = node.id
        self.name = node.name
        self.position = node.position
        self.node_type = node.node_type
        self.time_label = node.time_label
        self.content = node.content
        self.speaker = node.speaker
        self.background = node.background
        self.cycle_variants = self._safe_json(node.cycle_variants_json, {})
        self.color_palette = node.color_palette
        self.ambient = node.ambient
        self.atmosphere = self._safe_json(node.atmosphere_json, [])
        self.sensory = node.sensory
        self.gender_variant = self._safe_json(node.gender_variant_json, None)
        self.parent_node_id = node.parent_node_id
        self.trigger_condition = node.trigger_condition
        self.crossing_config = self._safe_json(node.crossing_config_json, None)
        self.warp_config = self._safe_json(node.warp_config_json, None)
        self.shortcut_config = self._safe_json(node.shortcut_config_json, None)
        self.npc_item_mapping = self._safe_json(node.npc_item_mapping_json, None)
        self.scene_items = self._safe_json(node.scene_items_json, None)

        self.choices: list[ChoiceData] = []
        for c in choices:
            self.choices.append(ChoiceData(
                id=c.id,
                from_node_id=c.from_node_id,
                text=c.text,
                short_text=c.short_text,
                next_node_id=c.next_node_id,
                condition=c.condition,
                effects=self._safe_json(c.effects_json, []),
                priority=c.priority,
                hint=c.hint,
                is_hidden_when_locked=bool(c.is_hidden_when_locked),
                transition_text=c.transition_text,
            ))

    @staticmethod
    def _safe_json(raw, default):
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default


class ChoiceData:
    def __init__(self, id, from_node_id, text, short_text, next_node_id,
                 condition, effects, priority, hint, is_hidden_when_locked, transition_text):
        self.id = id
        self.from_node_id = from_node_id
        self.text = text
        self.short_text = short_text
        self.next_node_id = next_node_id
        self.condition = condition
        self.effects = effects
        self.priority = priority
        self.hint = hint
        self.is_hidden_when_locked = is_hidden_when_locked
        self.transition_text = transition_text


class GraphLoader:
    """从数据库加载整个故事图为字典 {node_id: GraphBundle}。"""

    def load_all(self, session: Session) -> dict[str, GraphBundle]:
        nodes = session.query(StoryNodeModel).all()
        choices = session.query(ChoiceModel).all()

        choices_by_node: dict[str, list[ChoiceModel]] = {}
        for c in choices:
            choices_by_node.setdefault(c.from_node_id, []).append(c)

        graph: dict[str, GraphBundle] = {}
        for node in nodes:
            node_choices = choices_by_node.get(node.id, [])
            node_choices.sort(key=lambda c: c.priority)
            graph[node.id] = GraphBundle(node, node_choices)

        return graph
