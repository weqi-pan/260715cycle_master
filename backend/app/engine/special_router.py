# backend/app/engine/special_router.py
from .graph import GraphBundle, ChoiceData
from ..schemas.game import ChoiceResult, GameState


class SpecialRouter:
    def __init__(self, evaluator):
        self.evaluator = evaluator

    def get_available(
        self, bundle: GraphBundle, graph: dict[str, GraphBundle], state: GameState
    ) -> list[ChoiceResult]:
        results = []

        # K 跃迁入口
        warp_node = graph.get("K")
        if warp_node and warp_node.warp_config and bundle.id != "K":
            entry_cond = warp_node.warp_config.get("entry_condition")
            if entry_cond and self.evaluator.check(entry_cond, state):
                entry_text = warp_node.warp_config.get("entry_text", "踏入跃迁裂隙")
                results.append(ChoiceResult(
                    id="__warp_K_enter",
                    text=entry_text,
                    available=True,
                    source="special_warp",
                ))

        # K 从内部跳转到各目标
        if bundle.id == "K" and warp_node and warp_node.warp_config:
            targets = warp_node.warp_config.get("warp_targets", [])
            for target_id in targets:
                if target_id in graph:
                    target = graph[target_id]
                    results.append(ChoiceResult(
                        id=f"__warp_K_exit_{target_id}",
                        text=f"跃迁至{target.name}（{target.id}）",
                        available=True,
                        source="special_warp",
                    ))

        return results

    def resolve(
        self, choice_id: str, bundle: GraphBundle,
        graph: dict[str, GraphBundle], state: GameState
    ) -> ChoiceData:
        if choice_id == "__warp_K_enter":
            return ChoiceData(
                id=choice_id, from_node_id=bundle.id,
                text="踏入跃迁裂隙", short_text="跃迁",
                next_node_id="K", condition=None, effects=[],
                priority=0, hint=None, is_hidden_when_locked=False,
                transition_text="灰白色的虚空在你周围展开。脚下暗红色的光脉在缓慢搏动。",
            )
        if choice_id.startswith("__warp_K_exit_"):
            target_id = choice_id.replace("__warp_K_exit_", "")
            return ChoiceData(
                id=choice_id, from_node_id="K",
                text=f"跃迁至{target_id}", short_text=f"→{target_id}",
                next_node_id=target_id, condition=None,
                effects=[
                    {"type": "set_attr", "target": "sanity_max", "value": -1}
                ],
                priority=10, hint="消耗san值上限-1",
                is_hidden_when_locked=False,
                transition_text=f"暗红色的光吞没了一切。再睁开眼时——你已到达{target_id}。",
            )
        raise ValueError(f"Unknown special choice: {choice_id}")
