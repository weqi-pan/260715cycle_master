"""Typed Story System v3 condition evaluation."""

import operator

from ..schemas.game import GameState
from ..schemas.story_v3 import (
    AllCondition,
    AnyCondition,
    AtNodeCondition,
    AttributeCompareCondition,
    ConditionV3,
    CounterCompareCondition,
    FlagEqualsCondition,
    ItemCondition,
    NotCondition,
)


_COMPARE_OPERATORS = {
    "lt": operator.lt,
    "lte": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
    "gte": operator.ge,
    "gt": operator.gt,
}


class ConditionEvaluator:
    """Recursively evaluate typed v3 conditions against runtime state."""

    def check(self, condition: ConditionV3 | None, state: GameState) -> bool:
        if condition is None:
            return True
        if isinstance(condition, AttributeCompareCondition):
            return _COMPARE_OPERATORS[condition.operator](
                state.player_attributes[condition.attribute],
                condition.value,
            )
        if isinstance(condition, FlagEqualsCondition):
            actual = state.flags.get(condition.flag)
            return type(actual) is type(condition.value) and actual == condition.value
        if isinstance(condition, ItemCondition):
            present = any(
                item.get("id") == condition.item_id
                and item.get("count", item.get("quantity", 1)) > 0
                for item in state.inventory
            )
            return present is condition.present
        if isinstance(condition, CounterCompareCondition):
            counters = {
                "completed_cycles": state.cycle_count,
                "current_cycle": state.cycle_count + 1,
                "half_cycles": state.half_cycle_count,
            }
            return _COMPARE_OPERATORS[condition.operator](
                counters[condition.counter],
                condition.value,
            )
        if isinstance(condition, AtNodeCondition):
            return state.current_node_id == condition.node_id
        if isinstance(condition, AllCondition):
            return all(self.check(item, state) for item in condition.conditions)
        if isinstance(condition, AnyCondition):
            return any(self.check(item, state) for item in condition.conditions)
        if isinstance(condition, NotCondition):
            return not self.check(condition.condition, state)
        raise TypeError(f"Unsupported v3 condition: {type(condition).__name__}")
