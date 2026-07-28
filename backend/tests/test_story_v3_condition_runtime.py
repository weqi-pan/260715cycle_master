from typing import Any, cast

import pytest

from app.engine.condition_eval import ConditionEvaluator
from app.schemas.game import GameState
from app.schemas.story_v3 import (
    AllCondition,
    AnyCondition,
    AtNodeCondition,
    AttributeCompareCondition,
    CounterCompareCondition,
    FlagEqualsCondition,
    ItemCondition,
    NotCondition,
)


@pytest.fixture
def state() -> GameState:
    return GameState(
        current_node_id="A",
        cycle_count=2,
        half_cycle_count=1,
        inventory=[
            {"id": "item_coin", "count": 2},
            {"id": "item_empty", "count": 0},
            {"id": "item_quantity_empty", "quantity": 0},
        ],
        flags={"door_open": True, "trust": 2, "title": "keeper"},
        player_attributes={"insight": 5, "sanity": 80},
    )


def test_none_condition_is_unconditional(state):
    assert ConditionEvaluator().check(None, state) is True


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        ("lt", 6, True),
        ("lte", 5, True),
        ("eq", 5, True),
        ("ne", 6, True),
        ("gte", 5, True),
        ("gt", 4, True),
        ("lt", 5, False),
        ("gt", 5, False),
    ],
)
def test_attribute_compare_supports_every_operator(
    state,
    operator,
    value,
    expected,
):
    condition = AttributeCompareCondition(
        type="attribute_compare",
        attribute="insight",
        operator=operator,
        value=value,
    )

    assert ConditionEvaluator().check(condition, state) is expected


def test_attribute_compare_rejects_missing_runtime_attribute(state):
    condition = AttributeCompareCondition(
        type="attribute_compare",
        attribute="courage",
        operator="gte",
        value=1,
    )

    with pytest.raises(KeyError, match="courage"):
        ConditionEvaluator().check(condition, state)


@pytest.mark.parametrize(
    ("flag", "value", "expected"),
    [
        ("door_open", True, True),
        ("trust", 2, True),
        ("title", "keeper", True),
        ("missing_flag", False, False),
    ],
)
def test_flag_equals_uses_registered_runtime_value(state, flag, value, expected):
    condition = FlagEqualsCondition(type="flag_equals", flag=flag, value=value)

    assert ConditionEvaluator().check(condition, state) is expected


@pytest.mark.parametrize(
    ("item_id", "present", "expected"),
    [
        ("item_coin", True, True),
        ("item_coin", False, False),
        ("item_empty", True, False),
        ("item_quantity_empty", True, False),
        ("item_missing", False, True),
    ],
)
def test_item_condition_respects_presence_and_quantity(
    state,
    item_id,
    present,
    expected,
):
    condition = ItemCondition(type="item", item_id=item_id, present=present)

    assert ConditionEvaluator().check(condition, state) is expected


@pytest.mark.parametrize(
    ("counter", "value"),
    [
        ("completed_cycles", 2),
        ("current_cycle", 3),
        ("half_cycles", 1),
    ],
)
def test_counter_compare_uses_v3_counter_semantics(state, counter, value):
    condition = CounterCompareCondition(
        type="counter_compare",
        counter=counter,
        operator="eq",
        value=value,
    )

    assert ConditionEvaluator().check(condition, state) is True


def test_at_node_matches_current_node(state):
    assert ConditionEvaluator().check(
        AtNodeCondition(type="at_node", node_id="A"),
        state,
    ) is True
    assert ConditionEvaluator().check(
        AtNodeCondition(type="at_node", node_id="E"),
        state,
    ) is False


def test_nested_condition_uses_v3_state(state):
    condition = AllCondition(
        type="all",
        conditions=[
            AttributeCompareCondition(
                type="attribute_compare",
                attribute="insight",
                operator="gte",
                value=5,
            ),
            AnyCondition(
                type="any",
                conditions=[
                    ItemCondition(type="item", item_id="item_missing"),
                    FlagEqualsCondition(
                        type="flag_equals",
                        flag="door_open",
                        value=True,
                    ),
                ],
            ),
            NotCondition(
                type="not",
                condition=AtNodeCondition(type="at_node", node_id="E"),
            ),
        ],
    )

    assert ConditionEvaluator().check(condition, state) is True


def test_unsupported_condition_type_is_rejected(state):
    condition = cast(Any, object())

    with pytest.raises(TypeError, match="Unsupported v3 condition: object"):
        ConditionEvaluator().check(condition, state)
