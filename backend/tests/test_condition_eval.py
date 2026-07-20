# backend/tests/test_condition_eval.py
import pytest
from app.engine.condition_eval import ConditionEvaluator
from app.schemas.game import GameState


def make_state(**kwargs):
    defaults = {
        "current_node_id": "A",
        "cycle_count": 1,
        "half_cycle_count": 0,
        "inventory": [],
        "flags": {},
        "player_attributes": {"sanity": 100, "courage": 5, "insight": 3},
    }
    defaults.update(kwargs)
    return GameState(**defaults)


@pytest.fixture
def evaluator():
    return ConditionEvaluator()


# --- null / empty ---
def test_null_condition_always_true(evaluator):
    assert evaluator.check(None, make_state()) == True
    assert evaluator.check("", make_state()) == True


# --- has_item ---
def test_has_item_true(evaluator):
    state = make_state(inventory=[{"id": "item_key", "name": "Key"}])
    assert evaluator.evaluate("has_item:item_key", state) == True


def test_has_item_false(evaluator):
    state = make_state(inventory=[])
    assert evaluator.evaluate("has_item:item_key", state) == False


# --- has_flag ---
def test_has_flag_true(evaluator):
    state = make_state(flags={"know_secret": True})
    assert evaluator.evaluate("has_flag:know_secret", state) == True


def test_has_flag_false(evaluator):
    state = make_state(flags={})
    assert evaluator.evaluate("has_flag:know_secret", state) == False


# --- flag:NAME=VALUE ---
def test_flag_eq_true(evaluator):
    state = make_state(flags={"zhang_trust": 3})
    assert evaluator.evaluate("flag:zhang_trust=3", state) == True


def test_flag_eq_false(evaluator):
    state = make_state(flags={"zhang_trust": 1})
    assert evaluator.evaluate("flag:zhang_trust=3", state) == False


# --- attr ---
def test_attr_gte_true(evaluator):
    assert evaluator.evaluate("attr:courage>=5", make_state()) == True


def test_attr_gte_false(evaluator):
    assert evaluator.evaluate("attr:courage>=8", make_state()) == False


def test_attr_lt_true(evaluator):
    assert evaluator.evaluate("attr:sanity<50", make_state(player_attributes={"sanity": 30})) == True


# --- cycle ---
def test_cycle_gte_true(evaluator):
    assert evaluator.evaluate("cycle>=3", make_state(cycle_count=5)) == True


def test_cycle_gte_false(evaluator):
    assert evaluator.evaluate("cycle>=3", make_state(cycle_count=1)) == False


def test_cycle_equality(evaluator):
    assert evaluator.evaluate("cycle==2", make_state(cycle_count=2)) is True
    assert evaluator.evaluate("cycle!=2", make_state(cycle_count=3)) is True


# --- half_cycle ---
def test_half_cycle_true(evaluator):
    assert evaluator.evaluate("half_cycle>=1", make_state(half_cycle_count=2)) == True


def test_half_cycle_comparison(evaluator):
    assert evaluator.evaluate(
        "half_cycle<2", make_state(half_cycle_count=1)
    ) is True


# --- at_node ---
def test_at_node_true(evaluator):
    assert evaluator.evaluate("at_node:E", make_state(current_node_id="E")) == True


def test_at_node_false(evaluator):
    assert evaluator.evaluate("at_node:E", make_state(current_node_id="A")) == False


# --- not ---
def test_not(evaluator):
    assert evaluator.evaluate("not:has_item:item_key", make_state(inventory=[])) == True
    assert evaluator.evaluate("not:has_item:item_key", make_state(inventory=[{"id": "item_key"}])) == False


# --- and ---
def test_and_both_true(evaluator):
    state = make_state(inventory=[{"id": "item_key"}], flags={"unlocked": True})
    assert evaluator.evaluate("and:has_item:item_key,has_flag:unlocked", state) == True


def test_and_one_false(evaluator):
    state = make_state(inventory=[{"id": "item_key"}], flags={})
    assert evaluator.evaluate("and:has_item:item_key,has_flag:unlocked", state) == False


# --- or ---
def test_or_one_true(evaluator):
    state = make_state(inventory=[], flags={"unlocked": True})
    assert evaluator.evaluate("or:has_item:item_key,has_flag:unlocked", state) == True


def test_or_both_false(evaluator):
    state = make_state(inventory=[], flags={})
    assert evaluator.evaluate("or:has_item:item_key,has_flag:unlocked", state) == False


# --- nested ---
def test_nested_and_or(evaluator):
    # and:has_item:beads,or:courage>=8,cycle>=3
    state = make_state(
        inventory=[{"id": "item_beads"}],
        player_attributes={"courage": 5},
        cycle_count=5,
    )
    assert evaluator.evaluate("and:has_item:item_beads,(or:attr:courage>=8,cycle>=3)", state) == True


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (make_state(flags={"taoist_chant": True}), True),
        (make_state(cycle_count=3, player_attributes={"courage": 8}), True),
        (make_state(inventory=[{"id": "item_beads"}], flags={"river_crossed": True}), True),
        (make_state(cycle_count=3, player_attributes={"courage": 7}), False),
    ],
)
def test_warp_condition_has_three_independent_routes(evaluator, state, expected):
    condition = (
        "or:has_flag:taoist_chant,"
        "(and:attr:courage>=8,cycle>=3),"
        "(and:has_item:item_beads,has_flag:river_crossed)"
    )
    assert evaluator.evaluate(condition, state) is expected
