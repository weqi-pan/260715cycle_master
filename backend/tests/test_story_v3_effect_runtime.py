from typing import Any, cast

import pytest

from app.engine.effects_v3 import EffectExecutionError, EffectExecutor
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
)


@pytest.fixture
def executor(canonical_v3_snapshot) -> EffectExecutor:
    return EffectExecutor(
        canonical_v3_snapshot.project,
        node_ids=canonical_v3_snapshot.nodes,
    )


@pytest.fixture
def state(canonical_v3_snapshot) -> GameState:
    state = GameState.new(canonical_v3_snapshot.project)
    state.entry_attributes = {"sanity": 72}
    return state


def test_attribute_effects_use_project_clamps_without_mutating_input(
    executor,
    state,
):
    state.player_attributes["sanity"] = 95
    before = state.model_copy(deep=True)

    result = executor.apply(
        [
            ModifyAttributeEffect(
                type="modify_attribute",
                attribute="sanity",
                operation="add",
                value=10,
            ),
            ModifyAttributeEffect(
                type="modify_attribute",
                attribute="courage",
                operation="set",
                value=99,
                clamp=False,
            ),
        ],
        state,
        node_id="A",
    )

    assert result.player_attributes["sanity"] == 100
    assert result.player_attributes["courage"] == 99
    assert state == before


def test_set_flag_requires_registered_flag_and_matching_scalar_type(
    executor,
    state,
):
    result = executor.apply(
        [
            SetFlagEffect(
                type="set_flag",
                flag="checked_pocket_item",
                value=True,
            ),
        ],
        state,
        node_id="A",
    )

    assert result.flags["checked_pocket_item"] is True

    with pytest.raises(EffectExecutionError, match="flag value type"):
        executor.apply(
            [
                SetFlagEffect(
                    type="set_flag",
                    flag="checked_pocket_item",
                    value=1,
                ),
            ],
            state,
            node_id="A",
        )


def test_inventory_effects_add_and_remove_quantity_with_project_metadata(
    canonical_v3_snapshot,
    executor,
    state,
):
    result = executor.apply(
        [
            InventoryEffect(
                type="inventory",
                item_id="item_qing_coin",
                operation="add",
                quantity=3,
            ),
            InventoryEffect(
                type="inventory",
                item_id="item_qing_coin",
                operation="remove",
                quantity=2,
            ),
        ],
        state,
        node_id="A",
    )

    definition = canonical_v3_snapshot.project.items["item_qing_coin"]
    assert result.inventory == [
        {
            "id": "item_qing_coin",
            "name": definition.display_name,
            "count": 1,
            "discardable": definition.discardable,
            "cross_surface": definition.cross_surface,
        },
    ]

    removed = executor.apply(
        [
            InventoryEffect(
                type="inventory",
                item_id="item_qing_coin",
                operation="remove",
                quantity=1,
            ),
        ],
        result,
        node_id="A",
    )
    assert removed.inventory == []


def test_inventory_removal_below_zero_is_rejected_atomically(executor, state):
    state.inventory = [{"id": "item_qing_coin", "count": 1}]
    before = state.model_copy(deep=True)

    with pytest.raises(EffectExecutionError, match="below zero"):
        executor.apply(
            [
                InventoryEffect(
                    type="inventory",
                    item_id="item_qing_coin",
                    operation="remove",
                    quantity=2,
                ),
            ],
            state,
            node_id="A",
        )

    assert state == before


def test_persist_node_item_is_registered_hydrated_and_idempotent(
    canonical_v3_snapshot,
    executor,
    state,
):
    effect = PersistNodeItemEffect(
        type="persist_node_item",
        node_id="H",
        item_id="A_note_from_H",
    )

    result = executor.apply([effect, effect], state, node_id="H")

    definition = canonical_v3_snapshot.project.items["A_note_from_H"]
    assert result.persistent_nodes["H"] == {
        "items": [
            {
                "id": "A_note_from_H",
                "name": definition.display_name,
                "discardable": definition.discardable,
                "cross_surface": definition.cross_surface,
            },
        ],
        "dangers": [],
    }


def test_record_interaction_tracks_unique_subjects(executor, state):
    effect = RecordInteractionEffect(
        type="record_interaction",
        group="crossing_E",
        subject_id="npc_yan_yan",
    )

    result = executor.apply([effect, effect], state, node_id="E")

    assert result.interaction_history == {"crossing_E": ["npc_yan_yan"]}


def test_counter_effects_modify_registered_counters(executor, state):
    result = executor.apply(
        [
            ModifyCounterEffect(
                type="modify_counter",
                counter="completed_cycles",
                operation="add",
                value=2,
            ),
            ModifyCounterEffect(
                type="modify_counter",
                counter="half_cycles",
                operation="set",
                value=5,
            ),
        ],
        state,
        node_id="A",
    )

    assert result.cycle_count == 2
    assert result.half_cycle_count == 5


@pytest.mark.parametrize("scope", ["visit", "cycle", "session"])
def test_mark_once_records_unique_keys_by_scope(executor, state, scope):
    effect = MarkOnceEffect(type="mark_once", key="s20_restored", scope=scope)

    result = executor.apply([effect, effect], state, node_id="S20")

    assert result.once_marks == {scope: ["s20_restored"]}


def test_restore_entry_attribute_uses_captured_value(executor, state):
    state.player_attributes["sanity"] = 20

    result = executor.apply(
        [
            RestoreEntryAttributeEffect(
                type="restore_entry_attribute",
                attribute="sanity",
            ),
        ],
        state,
        node_id="S20",
    )

    assert result.player_attributes["sanity"] == 72


def test_effect_batch_rolls_back_when_later_effect_fails(executor, state):
    before_json = state.model_dump_json()
    effects = [
        SetFlagEffect(
            type="set_flag",
            flag="checked_pocket_item",
            value=True,
        ),
        InventoryEffect(
            type="inventory",
            item_id="missing_item",
            operation="add",
            quantity=1,
        ),
    ]

    with pytest.raises(EffectExecutionError, match="Unknown item"):
        executor.apply(effects, state, node_id="A")

    assert state.model_dump_json() == before_json


@pytest.mark.parametrize(
    ("effect", "message"),
    [
        (
            ModifyAttributeEffect(
                type="modify_attribute",
                attribute="missing_attribute",
                operation="add",
                value=1,
            ),
            "Unknown attribute",
        ),
        (
            SetFlagEffect(
                type="set_flag",
                flag="missing_flag",
                value=True,
            ),
            "Unknown flag",
        ),
        (
            InventoryEffect(
                type="inventory",
                item_id="missing_item",
                operation="add",
                quantity=1,
            ),
            "Unknown item",
        ),
        (
            PersistNodeItemEffect(
                type="persist_node_item",
                node_id="missing_node",
                item_id="item_qing_coin",
            ),
            "Unknown node",
        ),
        (
            RecordInteractionEffect(
                type="record_interaction",
                group="crossing_E",
                subject_id="missing_npc",
            ),
            "Unknown NPC",
        ),
        (
            RestoreEntryAttributeEffect(
                type="restore_entry_attribute",
                attribute="courage",
            ),
            "entry attribute",
        ),
    ],
)
def test_unknown_effect_references_are_rejected(executor, state, effect, message):
    with pytest.raises(EffectExecutionError, match=message):
        executor.apply([effect], state, node_id="A")


def test_unknown_current_node_is_rejected(executor, state):
    with pytest.raises(EffectExecutionError, match="Unknown node"):
        executor.apply([], state, node_id="missing_node")


def test_counter_must_be_declared_by_project(canonical_v3_snapshot, state):
    project = canonical_v3_snapshot.project.model_copy(
        deep=True,
        update={"counters": ["completed_cycles"]},
    )
    executor = EffectExecutor(project, node_ids=canonical_v3_snapshot.nodes)
    effect = ModifyCounterEffect(
        type="modify_counter",
        counter="half_cycles",
        operation="add",
        value=1,
    )

    with pytest.raises(EffectExecutionError, match="Unknown counter"):
        executor.apply([effect], state, node_id="A")


def test_unknown_once_scope_is_rejected(executor, state):
    effect = MarkOnceEffect.model_construct(
        type="mark_once",
        key="invalid_mark",
        scope="lifetime",
    )

    with pytest.raises(EffectExecutionError, match="Unknown once scope"):
        executor.apply([effect], state, node_id="A")


def test_unsupported_effect_type_is_rejected(executor, state):
    effect = cast(Any, object())

    with pytest.raises(EffectExecutionError, match="Unsupported v3 effect: object"):
        executor.apply([effect], state, node_id="A")
