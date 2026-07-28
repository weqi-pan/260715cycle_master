"""Atomic execution for typed Story System v3 effects."""

from collections.abc import Collection

from app.schemas.game import GameState
from app.schemas.story_v3 import (
    InventoryEffect,
    MarkOnceEffect,
    ModifyAttributeEffect,
    ModifyCounterEffect,
    PersistNodeItemEffect,
    RecordInteractionEffect,
    RestoreEntryAttributeEffect,
    SetFlagEffect,
    StoryEffectV3,
    StoryProjectV3,
)


class EffectExecutionError(ValueError):
    """Raised when a typed effect cannot be applied to runtime state."""


_EXPECTED_EFFECT_TYPES = {
    ModifyAttributeEffect: "modify_attribute",
    SetFlagEffect: "set_flag",
    InventoryEffect: "inventory",
    PersistNodeItemEffect: "persist_node_item",
    RecordInteractionEffect: "record_interaction",
    ModifyCounterEffect: "modify_counter",
    MarkOnceEffect: "mark_once",
    RestoreEntryAttributeEffect: "restore_entry_attribute",
}


class EffectExecutor:
    def __init__(
        self,
        project: StoryProjectV3,
        *,
        node_ids: Collection[str],
    ) -> None:
        self.project = project
        self.node_ids = frozenset(node_ids)

    def apply(
        self,
        effects: list[StoryEffectV3],
        state: GameState,
        *,
        node_id: str,
    ) -> GameState:
        """Apply a batch to a validated copy and return it only on success."""

        if node_id not in self.node_ids:
            raise EffectExecutionError(f"Unknown node: {node_id}")
        try:
            candidate = state.normalized(
                self.project,
                node_ids=self.node_ids,
                clamp_attributes=False,
            )
        except ValueError as exc:
            raise EffectExecutionError(str(exc)) from exc

        for effect in effects:
            self._apply_one(effect, candidate, node_id=node_id)
        return candidate

    def _apply_one(
        self,
        effect: StoryEffectV3,
        state: GameState,
        *,
        node_id: str,
    ) -> None:
        expected_type = _EXPECTED_EFFECT_TYPES.get(type(effect))
        if expected_type is None:
            raise EffectExecutionError(
                f"Unsupported v3 effect: {type(effect).__name__}"
            )
        if effect.type != expected_type:
            raise EffectExecutionError(
                f"Unsupported v3 effect type: {effect.type}"
            )

        if isinstance(effect, ModifyAttributeEffect):
            self._modify_attribute(effect, state)
            return
        if isinstance(effect, SetFlagEffect):
            self._set_flag(effect, state)
            return
        if isinstance(effect, InventoryEffect):
            self._modify_inventory(effect, state)
            return
        if isinstance(effect, PersistNodeItemEffect):
            self._persist_node_item(effect, state)
            return
        if isinstance(effect, RecordInteractionEffect):
            self._record_interaction(effect, state)
            return
        if isinstance(effect, ModifyCounterEffect):
            self._modify_counter(effect, state)
            return
        if isinstance(effect, MarkOnceEffect):
            self._mark_once(effect, state)
            return
        if isinstance(effect, RestoreEntryAttributeEffect):
            self._restore_entry_attribute(effect, state)
            return
        raise EffectExecutionError(
            f"Unsupported v3 effect: {type(effect).__name__}"
        )

    def _modify_attribute(
        self,
        effect: ModifyAttributeEffect,
        state: GameState,
    ) -> None:
        definition = self.project.attributes.get(effect.attribute)
        if definition is None:
            raise EffectExecutionError(f"Unknown attribute: {effect.attribute}")
        current = state.player_attributes[effect.attribute]
        value = current + effect.value if effect.operation == "add" else effect.value
        if effect.clamp:
            value = min(definition.maximum, max(definition.minimum, value))
        state.player_attributes[effect.attribute] = value

    def _set_flag(self, effect: SetFlagEffect, state: GameState) -> None:
        definition = self.project.flags.get(effect.flag)
        if definition is None:
            raise EffectExecutionError(f"Unknown flag: {effect.flag}")
        if type(effect.value) is not type(definition.default):
            raise EffectExecutionError(
                f"Invalid flag value type for {effect.flag}: "
                f"expected {type(definition.default).__name__}"
            )
        state.flags[effect.flag] = effect.value

    def _modify_inventory(
        self,
        effect: InventoryEffect,
        state: GameState,
    ) -> None:
        definition = self.project.items.get(effect.item_id)
        if definition is None:
            raise EffectExecutionError(f"Unknown item: {effect.item_id}")
        index = next(
            (
                index
                for index, entry in enumerate(state.inventory)
                if entry.get("id") == effect.item_id
            ),
            None,
        )
        current = 0
        if index is not None:
            entry = state.inventory[index]
            current = int(entry.get("count", entry.get("quantity", 1)))

        if effect.operation == "remove":
            remaining = current - effect.quantity
            if remaining < 0:
                raise EffectExecutionError(
                    f"Inventory removal would go below zero: {effect.item_id}"
                )
            if remaining == 0:
                if index is not None:
                    state.inventory.pop(index)
                return
            assert index is not None
            state.inventory[index] = self._item_view(
                effect.item_id,
                count=remaining,
            )
            return

        count = current + effect.quantity
        item = self._item_view(effect.item_id, count=count)
        if index is None:
            state.inventory.append(item)
        else:
            state.inventory[index] = item

    def _persist_node_item(
        self,
        effect: PersistNodeItemEffect,
        state: GameState,
    ) -> None:
        if effect.node_id not in self.node_ids:
            raise EffectExecutionError(f"Unknown node: {effect.node_id}")
        if effect.item_id not in self.project.items:
            raise EffectExecutionError(f"Unknown item: {effect.item_id}")
        node_state = state.persistent_nodes.setdefault(
            effect.node_id,
            {"items": [], "dangers": []},
        )
        node_state.setdefault("dangers", [])
        items = node_state.setdefault("items", [])
        if not any(item.get("id") == effect.item_id for item in items):
            items.append(self._item_view(effect.item_id))

    def _record_interaction(
        self,
        effect: RecordInteractionEffect,
        state: GameState,
    ) -> None:
        if effect.subject_id not in self.project.npcs:
            raise EffectExecutionError(f"Unknown NPC: {effect.subject_id}")
        subjects = state.interaction_history.setdefault(effect.group, [])
        if effect.subject_id not in subjects:
            subjects.append(effect.subject_id)

    def _modify_counter(
        self,
        effect: ModifyCounterEffect,
        state: GameState,
    ) -> None:
        if effect.counter not in self.project.counters:
            raise EffectExecutionError(f"Unknown counter: {effect.counter}")
        field = {
            "completed_cycles": "cycle_count",
            "half_cycles": "half_cycle_count",
        }[effect.counter]
        current = getattr(state, field)
        value = current + effect.value if effect.operation == "add" else effect.value
        setattr(state, field, value)

    @staticmethod
    def _mark_once(effect: MarkOnceEffect, state: GameState) -> None:
        if effect.scope not in {"visit", "cycle", "session"}:
            raise EffectExecutionError(f"Unknown once scope: {effect.scope}")
        marks = state.once_marks.setdefault(effect.scope, [])
        if effect.key not in marks:
            marks.append(effect.key)

    def _restore_entry_attribute(
        self,
        effect: RestoreEntryAttributeEffect,
        state: GameState,
    ) -> None:
        definition = self.project.attributes.get(effect.attribute)
        if definition is None:
            raise EffectExecutionError(f"Unknown attribute: {effect.attribute}")
        if effect.attribute not in state.entry_attributes:
            raise EffectExecutionError(
                f"Missing entry attribute: {effect.attribute}"
            )
        value = state.entry_attributes[effect.attribute]
        state.player_attributes[effect.attribute] = min(
            definition.maximum,
            max(definition.minimum, value),
        )

    def _item_view(self, item_id: str, *, count: int | None = None) -> dict:
        definition = self.project.items[item_id]
        item = {
            "id": item_id,
            "name": definition.display_name,
            "discardable": definition.discardable,
            "cross_surface": definition.cross_surface,
        }
        if count is not None:
            item["count"] = count
        return item
