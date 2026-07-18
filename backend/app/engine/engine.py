# backend/app/engine/engine.py
from .graph import GraphBundle, ChoiceData
from .condition_eval import ConditionEvaluator
from .special_router import SpecialRouter
from ..schemas.game import GameState, Frame, NodeData, ChoiceResult, PersistentFound


class GameEngine:
    def __init__(self):
        self.evaluator = ConditionEvaluator()
        self.special_router = SpecialRouter(self.evaluator)

    def process_choice(
        self,
        graph: dict[str, GraphBundle],
        node_id: str,
        choice_id: str,
        state: GameState,
        save_id: str | None = None,
    ) -> Frame:
        bundle = graph[node_id]

        # ① 检查是否为特殊路由选项
        if choice_id.startswith("__"):
            choice = self.special_router.resolve(choice_id, bundle, graph, state)
        else:
            choice = self._find_choice(bundle, choice_id)

        # ② 条件校验
        if choice.condition and not self.evaluator.evaluate(choice.condition, state):
            raise ValueError(f"Condition not met: {choice.condition}")

        # ③ 记录已访问节点
        if node_id not in state.visited_nodes:
            state.visited_nodes.append(node_id)

        # ④ 应用 Effects
        self._apply_effects(choice.effects, state, node_id)

        # ⑤ 跳转目标节点
        next_bundle = graph[choice.next_node_id]
        state.current_node_id = next_bundle.id

        # ⑥ 循环检测
        cycle_event = None
        if next_bundle.id == "A" and len(state.visited_nodes) > 0:
            state.cycle_count += 1
            state.visited_nodes = []
            cycle_event = {
                "type": "cycle_complete",
                "cycle_count": state.cycle_count,
                "half_cycle_count": state.half_cycle_count,
            }

        # ⑦ 解析可用选项
        available = self.resolve_available_choices(graph, next_bundle.id, state)

        # ⑧ 构建 Frame
        return Frame(
            node=NodeData(
                id=next_bundle.id,
                name=next_bundle.name,
                node_type=next_bundle.node_type,
                position=next_bundle.position,
                time_label=next_bundle.time_label,
                content=self._resolve_content(next_bundle, state),
                speaker=next_bundle.speaker,
                background=next_bundle.background,
            ),
            state=state,
            available_choices=available,
            persistent_found=PersistentFound(),
            cycle_event=cycle_event,
        )

    def resolve_available_choices(
        self, graph: dict[str, GraphBundle], node_id: str, state: GameState
    ) -> list[ChoiceResult]:
        bundle = graph[node_id]
        results = []

        for c in bundle.choices:
            available = self.evaluator.check(c.condition, state)
            # Hide unavailable choices by default; only show if explicitly NOT hidden
            if not available:
                if c.is_hidden_when_locked:
                    continue
                # Show locked choice with readable reason
                reason = c.hint or self.evaluator.describe_condition(c.condition)
                results.append(ChoiceResult(
                    id=c.id,
                    text=c.text,
                    short_text=c.short_text,
                    available=False,
                    reason=reason,
                    source="static",
                ))
            else:
                results.append(ChoiceResult(
                    id=c.id,
                    text=c.text,
                    short_text=c.short_text,
                    available=True,
                    reason=None,
                    source="static",
                ))

        # 注入特殊路由选项
        specials = self.special_router.get_available(bundle, graph, state)
        results.extend(specials)

        results.sort(key=lambda r: (
            0 if r.source != "static" else 1,
            next((c.priority for c in bundle.choices if c.id == r.id), 99)
        ))
        return results

    def _find_choice(self, bundle: GraphBundle, choice_id: str) -> ChoiceData:
        for c in bundle.choices:
            if c.id == choice_id:
                return c
        raise ValueError(f"Choice '{choice_id}' not found in node '{bundle.id}'")

    def _apply_effects(self, effects: list[dict], state: GameState, node_id: str):
        for effect in effects:
            etype = effect.get("type")
            target = effect.get("target", "")
            value = effect.get("value")

            if etype == "add_item":
                state.inventory.append({"id": target, "name": target, "count": value})
            elif etype == "remove_item":
                state.inventory = [i for i in state.inventory if i.get("id") != target]
            elif etype == "set_flag":
                state.flags[target] = value
            elif etype == "remove_flag":
                state.flags.pop(target, None)
            elif etype == "heal":
                attr = state.player_attributes.get(target, 0)
                state.player_attributes[target] = min(attr + value, 100)
            elif etype == "damage":
                attr = state.player_attributes.get(target, 100)
                state.player_attributes[target] = max(attr - value, 0)
            elif etype == "set_attr":
                state.player_attributes[target] = value

    def _resolve_content(self, bundle: GraphBundle, state: GameState) -> str:
        """解析 cycle_variants + {{变量}} 替换。"""
        variants = bundle.cycle_variants or {}
        content = bundle.content

        # 匹配最精确的 cycle variant
        for key in [f"cycle_{state.cycle_count}", f"cycle_{state.cycle_count}+"]:
            if key in variants and variants[key]:
                content = variants[key]
                break
        else:
            for key in sorted(variants.keys()):
                if key.endswith("+") and state.cycle_count >= int(key.replace("cycle_", "").replace("+", "")):
                    if variants[key]:
                        content = variants[key]

        # {{变量}} 替换
        content = content.replace("{{cycle_count}}", str(state.cycle_count))
        content = content.replace("{{half_cycle_count}}", str(state.half_cycle_count))
        for attr_name, attr_val in state.player_attributes.items():
            content = content.replace(f"{{{{attr:{attr_name}}}}}", str(attr_val))

        return content
