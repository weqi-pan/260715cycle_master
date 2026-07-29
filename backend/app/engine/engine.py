"""Story System v3 gameplay runtime."""

from .condition_eval import ConditionEvaluator
from .content_v3 import entry_blocks, visible_blocks
from .effects_v3 import EffectExecutor
from ..schemas.game import (
    ChoiceResult,
    ContentBlockView,
    Frame,
    GameState,
    NodeData,
    PersistentFound,
)
from ..schemas.story_v3 import (
    CrossingRoutingV3,
    ModifyCounterEffect,
    RecordInteractionEffect,
    ShortcutRoutingV3,
    StoryChoiceV3,
    StoryNodeV3,
    StorySnapshotV3,
    WarpRoutingV3,
)


class GameEngine:
    """Execute gameplay exclusively from a compiled Story System v3 snapshot."""

    def __init__(self):
        self.evaluator = ConditionEvaluator()

    # ============================================================
    # Story System v3 runtime
    # ============================================================

    def start(self, snapshot: StorySnapshotV3) -> Frame:
        """Start a new game from the v3 project's declared entry node."""

        state = GameState.new(snapshot.project)
        state.entry_attributes = dict(state.player_attributes)
        return self._v3_frame(snapshot, state)

    def resume(self, snapshot: StorySnapshotV3, state: GameState) -> Frame:
        """Validate a persisted v3 state and render its current node."""

        normalized = state.normalized(
            snapshot.project,
            node_ids=snapshot.nodes,
        )
        return self._v3_frame(snapshot, normalized)

    def choose(
        self,
        snapshot: StorySnapshotV3,
        state: GameState,
        *,
        node_id: str,
        choice_id: str,
    ) -> Frame:
        """Execute one ordinary authored v3 choice atomically."""

        if node_id not in snapshot.nodes:
            raise ValueError(f"Node '{node_id}' not found")
        normalized = state.normalized(
            snapshot.project,
            node_ids=snapshot.nodes,
            clamp_attributes=False,
        )
        if normalized.current_node_id != node_id:
            raise ValueError(
                f"State node mismatch: path='{node_id}', "
                f"state='{normalized.current_node_id}'"
            )

        node = snapshot.nodes[node_id]
        if node.meta.terminal is not None:
            raise ValueError(f"Terminal node has no exits: {node.id}")
        choice = self._find_v3_choice(node, choice_id)
        if not self.evaluator.check(choice.availability.condition, normalized):
            raise ValueError(f"Choice is locked: {choice.id}")
        if not self._repeat_available(choice, normalized):
            raise ValueError(
                f"Choice already selected under repeat policy: {choice.id}"
            )
        if choice.next.target not in snapshot.nodes:
            raise ValueError(f"Target node '{choice.next.target}' not found")

        target_node = snapshot.nodes[choice.next.target]
        self._validate_v3_route(node, target_node, choice, normalized)
        route_effects = self._v3_route_effects(node, choice)
        crossing_effect = self._v3_crossing_effect(node, choice, normalized)
        if crossing_effect is not None:
            route_effects.append(crossing_effect)

        previous_cycle = normalized.cycle_count
        updated = EffectExecutor(
            snapshot.project,
            node_ids=snapshot.nodes,
        ).apply(
            [*choice.effects, *route_effects],
            normalized,
            node_id=node_id,
        )
        self._record_choice(choice, updated)

        if node_id not in updated.visited_nodes:
            updated.visited_nodes.append(node_id)
        if choice.next.mode != "stay":
            updated.entry_attributes = dict(updated.player_attributes)
            if choice.next.target != node_id:
                updated.visit_id += 1
            self._reset_v3_destination_visit(target_node, updated)
        updated.current_node_id = choice.next.target

        terminal = target_node.meta.terminal
        if (
            terminal is not None
            and terminal.type == "cycle_complete"
            and updated.cycle_count == previous_cycle
        ):
            updated = EffectExecutor(
                snapshot.project,
                node_ids=snapshot.nodes,
            ).apply(
                [
                    ModifyCounterEffect(
                        type="modify_counter",
                        counter="completed_cycles",
                        operation="add",
                        value=1,
                    )
                ],
                updated,
                node_id=target_node.id,
            )

        cycle_event = None
        if updated.cycle_count > previous_cycle:
            updated.visited_nodes = []
            if "cycle" in updated.once_marks:
                updated.once_marks["cycle"] = []
            cycle_event = {
                "type": "cycle_complete",
                "cycle_count": updated.cycle_count,
                "half_cycle_count": updated.half_cycle_count,
            }

        if terminal is not None and terminal.type == "ending":
            if terminal.ending_id is None:
                raise ValueError(f"Ending terminal requires ending_id: {target_node.id}")
            if terminal.ending_id not in updated.endings_reached:
                updated.endings_reached.append(terminal.ending_id)

        results = visible_blocks(choice.result, updated, self.evaluator)
        return self._v3_frame(
            snapshot,
            updated,
            result_blocks=results,
            cycle_event=cycle_event,
        )

    def discard(
        self,
        snapshot: StorySnapshotV3,
        state: GameState,
        *,
        item_id: str,
    ) -> Frame:
        """Discard one registered, discardable item without advancing time."""

        definition = snapshot.project.items.get(item_id)
        if definition is None:
            raise ValueError(f"Unknown item: {item_id}")
        if not definition.discardable:
            raise ValueError(f"Item cannot be discarded: {item_id}")

        updated = state.normalized(
            snapshot.project,
            node_ids=snapshot.nodes,
            clamp_attributes=False,
        )
        item = next(
            (entry for entry in updated.inventory if entry.get("id") == item_id),
            None,
        )
        if item is None:
            raise ValueError(f"Item not in inventory: {item_id}")
        count = int(item.get("count", item.get("quantity", 1)))
        if count > 1:
            item["count"] = count - 1
            item.pop("quantity", None)
        else:
            updated.inventory = [
                entry
                for entry in updated.inventory
                if entry.get("id") != item_id
            ]
        return self._v3_frame(snapshot, updated)

    def _v3_frame(
        self,
        snapshot: StorySnapshotV3,
        state: GameState,
        *,
        result_blocks: list[ContentBlockView] | None = None,
        cycle_event: dict | None = None,
    ) -> Frame:
        node = snapshot.nodes.get(state.current_node_id)
        if node is None:
            raise ValueError(f"Node '{state.current_node_id}' not found")
        rendered_entry = entry_blocks(node, state, self.evaluator)
        node_state = state.persistent_nodes.get(node.id, {})
        return Frame(
            node=NodeData(
                id=node.id,
                name=node.meta.name,
                node_type=node.meta.node_type,
                position=node.meta.position,
                time_label=node.meta.time_label,
                content="\n\n".join(block.text for block in rendered_entry),
                background=self._v3_asset_path(snapshot, node.scene.background_id),
                ambient=self._v3_asset_path(snapshot, node.scene.ambient_id),
                color_palette=node.scene.palette,
                entry_blocks=rendered_entry,
            ),
            state=state,
            available_choices=self._v3_choices(node, state),
            persistent_found=PersistentFound(
                items=list(node_state.get("items", [])),
                dangers=list(node_state.get("dangers", [])),
            ),
            result_blocks=result_blocks or [],
            cycle_event=cycle_event,
            speaker_names={
                npc_id: definition.display_name
                for npc_id, definition in snapshot.project.npcs.items()
            },
        )

    def _v3_choices(
        self,
        node: StoryNodeV3,
        state: GameState,
    ) -> list[ChoiceResult]:
        if node.meta.terminal is not None:
            return []

        results: list[ChoiceResult] = []
        for choice in node.choices:
            if self._v3_crossing_limit_reached(node, choice, state):
                continue
            if not self._repeat_available(choice, state):
                continue
            available = self.evaluator.check(
                choice.availability.condition,
                state,
            )
            if not available and choice.availability.locked_visibility == "hide":
                continue
            results.append(
                ChoiceResult(
                    id=choice.id,
                    text=choice.text,
                    short_text=choice.short_text,
                    next_node_id=choice.next.target,
                    available=available,
                    reason=(
                        None
                        if available
                        else choice.availability.locked_reason
                    ),
                    source="static",
                )
            )
        return results

    def _validate_v3_route(
        self,
        node: StoryNodeV3,
        target_node: StoryNodeV3,
        choice: StoryChoiceV3,
        state: GameState,
    ) -> None:
        routing = node.routing
        if choice.next.mode == "shortcut":
            if not isinstance(routing, ShortcutRoutingV3):
                raise ValueError(f"Shortcut choice requires shortcut routing: {node.id}")
            if not self.evaluator.check(routing.entry_condition, state):
                raise ValueError("Shortcut entry condition not met")
            if choice.next.target != routing.exit_node_id:
                raise ValueError(
                    f"Shortcut target must be exit node: {routing.exit_node_id}"
                )
        elif choice.next.mode == "warp":
            if not isinstance(routing, WarpRoutingV3):
                raise ValueError(f"Warp choice requires warp routing: {node.id}")
            if not self.evaluator.check(routing.entry_condition, state):
                raise ValueError("Warp entry condition not met")
            if choice.next.target not in routing.allowed_targets:
                raise ValueError(f"Warp target is not allowed: {choice.next.target}")

        if choice.next.mode == "stay":
            return
        target_routing = target_node.routing
        if isinstance(target_routing, ShortcutRoutingV3):
            if node.id != target_routing.entry_node_id:
                raise ValueError(
                    f"Shortcut entry must come from: {target_routing.entry_node_id}"
                )
            if not self.evaluator.check(target_routing.entry_condition, state):
                raise ValueError("Shortcut entry condition not met")
        elif isinstance(target_routing, WarpRoutingV3):
            if not self.evaluator.check(target_routing.entry_condition, state):
                raise ValueError("Warp entry condition not met")

    @staticmethod
    def _v3_route_effects(
        node: StoryNodeV3,
        choice: StoryChoiceV3,
    ) -> list:
        routing = node.routing
        if choice.next.mode == "shortcut" and isinstance(
            routing, ShortcutRoutingV3
        ):
            return list(routing.counter_effects)
        if choice.next.mode == "warp" and isinstance(routing, WarpRoutingV3):
            return list(routing.exit_effects)
        return []

    def _v3_crossing_effect(
        self,
        node: StoryNodeV3,
        choice: StoryChoiceV3,
        state: GameState,
    ) -> RecordInteractionEffect | None:
        routing = node.routing
        if not isinstance(routing, CrossingRoutingV3):
            return None
        interaction = next(
            (
                interaction
                for interaction in routing.deep_interactions
                if interaction.choice_id == choice.id
            ),
            None,
        )
        if interaction is None:
            return None
        if self._v3_crossing_limit_reached(node, choice, state):
            raise ValueError(f"Crossing interaction limit reached: {node.id}")
        return RecordInteractionEffect(
            type="record_interaction",
            group=f"crossing_{node.id}",
            subject_id=interaction.npc_id,
        )

    @staticmethod
    def _v3_crossing_limit_reached(
        node: StoryNodeV3,
        choice: StoryChoiceV3,
        state: GameState,
    ) -> bool:
        routing = node.routing
        if not isinstance(routing, CrossingRoutingV3):
            return False
        deep_choice_ids = {
            interaction.choice_id for interaction in routing.deep_interactions
        }
        if choice.id not in deep_choice_ids:
            return False
        interactions = state.interaction_history.get(f"crossing_{node.id}", [])
        return len(interactions) >= routing.max_deep_interactions

    @staticmethod
    def _reset_v3_destination_visit(
        node: StoryNodeV3,
        state: GameState,
    ) -> None:
        if isinstance(node.routing, CrossingRoutingV3):
            state.interaction_history[f"crossing_{node.id}"] = []

    @staticmethod
    def _find_v3_choice(
        node: StoryNodeV3,
        choice_id: str,
    ) -> StoryChoiceV3:
        for choice in node.choices:
            if choice.id == choice_id:
                return choice
        raise ValueError(f"Choice '{choice_id}' not found in node '{node.id}'")

    @staticmethod
    def _v3_asset_path(
        snapshot: StorySnapshotV3,
        asset_id: str | None,
    ) -> str | None:
        if asset_id is None:
            return None
        asset = snapshot.assets.assets.get(asset_id)
        if asset is None:
            raise ValueError(f"Asset '{asset_id}' not found")
        return asset.path

    @staticmethod
    def _repeat_available(choice: StoryChoiceV3, state: GameState) -> bool:
        """Return whether a choice is available under its repeat policy."""

        policy = choice.repeat_policy
        record = state.choice_history.get(choice.id)
        if policy == "always" or record is None:
            return True
        if policy == "once_per_visit":
            return record.get("last_visit_id") != state.visit_id
        if policy == "once_per_cycle":
            return record.get("last_cycle") != state.cycle_count
        if policy == "once_ever":
            return False
        raise ValueError(f"Unknown repeat policy: {policy}")

    @staticmethod
    def _record_choice(choice: StoryChoiceV3, state: GameState) -> None:
        """Record a successfully executed v3 choice."""

        previous = state.choice_history.get(choice.id, {})
        state.choice_history[choice.id] = {
            "count": previous.get("count", 0) + 1,
            "last_cycle": state.cycle_count,
            "last_visit_id": state.visit_id,
        }
