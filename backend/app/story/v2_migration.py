"""Pure, deterministic conversion from Story System v2 values to v3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, cast

from app.domain.items import (
    CROSS_SURFACE_ITEMS,
    DISCARDABLE_ITEMS,
    ITEM_NAMES,
)
from app.domain.npcs import NPC_NAMES
from app.engine.story_v2_loader import StoryV2Loader
from app.schemas.story_v2 import (
    ContentBlock,
    StoryEffectV2,
    StoryNodeV2,
)
from app.schemas.story_v3 import (
    AllCondition,
    AnyCondition,
    AtNodeCondition,
    AttributeCompareCondition,
    AuthoringV3,
    AssetCatalogV3,
    AttributeDefinitionV3,
    ChoiceAvailabilityV3,
    CompareOperator,
    ConditionV3,
    CrossingInteractionV3,
    CrossingRoutingV3,
    CounterCompareCondition,
    DialogueContentBlockV3,
    EntrySequenceV3,
    FlagEqualsCondition,
    FlagDefinitionV3,
    GenderVariantNoteV3,
    InventoryEffect,
    ItemDefinitionV3,
    ItemCondition,
    ModifyAttributeEffect,
    ModifyCounterEffect,
    NarrationContentBlockV3,
    NextActionV3,
    NotCondition,
    NpcDefinitionV3,
    NpcItemNoteV3,
    PersistNodeItemEffect,
    RestoreEntryAttributeEffect,
    RoutingV3,
    SceneItemNoteV3,
    SceneV3,
    SetFlagEffect,
    ShortcutRoutingV3,
    StoryChoiceV3,
    StoryEffectV3,
    StoryNodeMetaV3,
    StoryNodeV3,
    StoryProjectV3,
    SystemContentBlockV3,
    WarpRoutingV3,
)
from app.story.identifiers import validate_story_id


OPERATOR_MAP = {
    "<": "lt",
    "<=": "lte",
    "==": "eq",
    "!=": "ne",
    ">=": "gte",
    ">": "gt",
}

_COMPARISON_PATTERN = r"(<=|>=|==|!=|<|>)"
_ATTRIBUTE_RE = re.compile(
    rf"^attr:([^<>=!]+){_COMPARISON_PATTERN}([+-]?\d+)$"
)
_COUNTER_RE = re.compile(
    rf"^(cycle|half_cycle){_COMPARISON_PATTERN}(\d+)$"
)
_FLAG_EQUALS_RE = re.compile(r"^flag:([^=]+)=(.+)$")
_INVALID_LOCAL_ID_RE = re.compile(r"[^A-Za-z0-9_-]")

PARENT_FIXES = {
    "S10": "F",
    "S13": "G",
    "S14": "G",
    "S19": "H",
    "S20": "H",
}

RETURN_TARGET_FIXES = {
    "S19_choice_02": "H",
    "S20_choice_02": "H",
}

OWNER_RETURN_FIXES = {
    "S2_choice_03": "A",
    "S3_choice_03": "B",
    "S4_choice_03": "B",
    "S5_choice_01": "C",
    "S5_choice_03": "C",
    "S6_choice_03": "C",
    "S15_choice_03": "G",
}

DEEP_INTERACTIONS = [
    ("E_choice_05", "npc_a_liu"),
    ("E_choice_06", "npc_li_ergou"),
    ("E_choice_07", "npc_liu_qisheng"),
    ("E_choice_08", "npc_huijue"),
    ("E_choice_09", "npc_shen_banxian"),
    ("E_choice_10", "npc_deleng"),
]

WARP_TARGETS = ["A", "B", "C", "D", "E", "F", "G", "H"]

ATTRIBUTE_DEFINITIONS = {
    "sanity": AttributeDefinitionV3(
        display_name="理智",
        default=100,
        minimum=0,
        maximum=100,
    ),
    "sanity_max": AttributeDefinitionV3(
        display_name="理智上限",
        default=100,
        minimum=0,
        maximum=100,
    ),
    "courage": AttributeDefinitionV3(
        display_name="勇气",
        default=5,
        minimum=0,
        maximum=10,
    ),
    "insight": AttributeDefinitionV3(
        display_name="洞察",
        default=3,
        minimum=0,
        maximum=10,
    ),
    "zhang_trust": AttributeDefinitionV3(
        display_name="张天民信任",
        default=0,
        minimum=0,
        maximum=3,
    ),
}


def parse_v2_condition(expression: str | None) -> ConditionV3 | None:
    """Parse a supported v2 condition string into the closed v3 condition tree."""
    if expression is None or not expression.strip():
        return None
    return _parse_condition(expression.strip())


def _parse_condition(expression: str) -> ConditionV3:
    condition = _strip_outer_group(expression.strip())

    if condition.startswith("and:"):
        parts = _split_top_level(condition[4:])
        return AllCondition(
            type="all",
            conditions=[_parse_condition(part) for part in parts],
        )

    if condition.startswith("or:"):
        parts = _split_top_level(condition[3:])
        return AnyCondition(
            type="any",
            conditions=[_parse_condition(part) for part in parts],
        )

    if condition.startswith("not:"):
        inner = condition[4:].strip()
        if not inner:
            raise ValueError(f"Malformed v2 condition: {expression!r}")
        return NotCondition(type="not", condition=_parse_condition(inner))

    if condition.startswith("has_item:"):
        item_id = condition[9:].strip()
        if not item_id:
            raise ValueError(f"Malformed v2 condition: {expression!r}")
        return ItemCondition(type="item", item_id=item_id, present=True)

    if condition.startswith("has_flag:"):
        flag = condition[9:].strip()
        if not flag:
            raise ValueError(f"Malformed v2 condition: {expression!r}")
        return FlagEqualsCondition(type="flag_equals", flag=flag, value=True)

    flag_match = _FLAG_EQUALS_RE.fullmatch(condition)
    if flag_match:
        flag, value = flag_match.groups()
        if value in {"True", "False"}:
            typed_value: bool | int | str = value == "True"
        elif re.fullmatch(r"[+-]?\d+", value):
            typed_value = int(value)
        else:
            typed_value = value
        return FlagEqualsCondition(
            type="flag_equals",
            flag=flag.strip(),
            value=typed_value,
        )

    attribute_match = _ATTRIBUTE_RE.fullmatch(condition)
    if attribute_match:
        attribute, symbol, value = attribute_match.groups()
        return AttributeCompareCondition(
            type="attribute_compare",
            attribute=attribute.strip(),
            operator=cast(CompareOperator, OPERATOR_MAP[symbol]),
            value=int(value),
        )

    counter_match = _COUNTER_RE.fullmatch(condition)
    if counter_match:
        counter, symbol, value = counter_match.groups()
        return CounterCompareCondition(
            type="counter_compare",
            counter=(
                "current_cycle"
                if counter == "cycle"
                else "half_cycles"
            ),
            operator=cast(CompareOperator, OPERATOR_MAP[symbol]),
            value=int(value),
        )

    if condition.startswith("at_node:"):
        node_id = condition[8:].strip()
        if not node_id:
            raise ValueError(f"Malformed v2 condition: {expression!r}")
        return AtNodeCondition(type="at_node", node_id=node_id)

    raise ValueError(f"Unknown v2 condition expression: {expression!r}")


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for character in text:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(f"Unbalanced v2 condition group: {text!r}")

        if character == "," and depth == 0:
            part = "".join(current).strip()
            if not part:
                raise ValueError(f"Malformed v2 condition list: {text!r}")
            parts.append(part)
            current = []
        else:
            current.append(character)

    if depth != 0:
        raise ValueError(f"Unbalanced v2 condition group: {text!r}")

    final = "".join(current).strip()
    if not final:
        raise ValueError(f"Malformed v2 condition list: {text!r}")
    parts.append(final)
    return parts


def _strip_outer_group(text: str) -> str:
    while text.startswith("("):
        depth = 0
        closing_index: int | None = None
        for index, character in enumerate(text):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth < 0:
                    raise ValueError(
                        f"Unbalanced v2 condition group: {text!r}"
                    )
                if depth == 0:
                    closing_index = index
                    break
        if closing_index is None:
            raise ValueError(f"Unbalanced v2 condition group: {text!r}")
        if closing_index != len(text) - 1:
            break
        text = text[1:-1].strip()

    depth = 0
    for character in text:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(f"Unbalanced v2 condition group: {text!r}")
    if depth != 0:
        raise ValueError(f"Unbalanced v2 condition group: {text!r}")
    if not text:
        raise ValueError("Malformed empty v2 condition group")
    return text


def migrate_v2_effect(
    effect: StoryEffectV2,
    *,
    node_id: str,
    choice_id: str,
) -> StoryEffectV3:
    """Convert one v2 choice effect without a free-form fallback."""
    target = effect.target

    if effect.type in {"add_item", "remove_item"}:
        if target is None:
            raise ValueError(
                f"{effect.type} effect requires target at "
                f"{node_id}/{choice_id}"
            )
        return InventoryEffect(
            type="inventory",
            item_id=target,
            operation=(
                "add" if effect.type == "add_item" else "remove"
            ),
            quantity=int(effect.value),
        )

    if effect.type in {"heal", "damage"}:
        if target is None:
            raise ValueError(
                f"{effect.type} effect requires target at "
                f"{node_id}/{choice_id}"
            )
        signed_value = int(effect.value)
        if effect.type == "damage":
            signed_value = -signed_value
        return ModifyAttributeEffect(
            type="modify_attribute",
            attribute=target,
            operation="add",
            value=signed_value,
        )

    if effect.type == "set_flag" and target == "zhang_trust":
        return ModifyAttributeEffect(
            type="modify_attribute",
            attribute="zhang_trust",
            operation="set",
            value=int(effect.value),
        )

    if effect.type == "set_flag":
        if target is None:
            raise ValueError(
                f"set_flag effect requires target at {node_id}/{choice_id}"
            )
        return SetFlagEffect(
            type="set_flag",
            flag=target,
            value=effect.value,
        )

    if effect.type == "leave_item":
        if target is None:
            raise ValueError(
                f"leave_item effect requires target at {node_id}/{choice_id}"
            )
        return PersistNodeItemEffect(
            type="persist_node_item",
            node_id=node_id,
            item_id=target,
        )

    raise ValueError(
        f"Unknown v2 effect type {effect.type!r} at {node_id}/{choice_id}"
    )


def migrate_v2_node(node: StoryNodeV2) -> StoryNodeV3:
    """Convert the common v2 node surface; special routing is migrated later."""
    local_ids = _NodeLocalIdMapper(node.id)
    return StoryNodeV3(
        schema_version=3,
        id=node.id,
        meta=StoryNodeMetaV3(
            name=node.meta.name,
            node_type=node.meta.node_type,
            position=node.meta.position,
            time_label=node.meta.time_label,
            parent_node_id=node.meta.parent_node_id,
            terminal=None,
        ),
        scene=_migrate_scene(node),
        entry_sequences=[
            EntrySequenceV3(
                id=local_ids.migrate(sequence.id, namespace="entry"),
                when=parse_v2_condition(sequence.when),
                blocks=[
                    _migrate_content_block(block, local_ids)
                    for block in sequence.blocks
                ],
            )
            for sequence in node.entry_sequences
        ],
        choices=[
            StoryChoiceV3(
                id=choice.id,
                text=choice.label,
                short_text=choice.short_label,
                availability=ChoiceAvailabilityV3(
                    condition=parse_v2_condition(choice.condition),
                    locked_visibility=choice.locked_visibility,
                    locked_reason=None,
                ),
                repeat_policy=choice.repeat_policy,
                hint=choice.hint,
                result=[
                    _migrate_content_block(block, local_ids)
                    for block in choice.result_blocks
                ],
                effects=[
                    migrate_v2_effect(
                        effect,
                        node_id=node.id,
                        choice_id=choice.id,
                    )
                    for effect in choice.effects
                ],
                next=NextActionV3(
                    target=choice.next.node_id,
                    mode=choice.next.mode,
                ),
            )
            for choice in node.choices
        ],
        routing=None,
        authoring=_migrate_authoring(node),
    )


def migrate_project(source_root: Path, destination_root: Path) -> None:
    """Migrate the complete v2 corpus into deterministic v3 source files."""
    source = Path(source_root)
    destination = Path(destination_root)
    nodes_root = source / "nodes"
    loader = StoryV2Loader(nodes_root if nodes_root.is_dir() else source)
    nodes = {
        node_id: _apply_project_repairs(migrate_v2_node(v2_node), v2_node)
        for node_id, v2_node in loader.nodes.items()
    }

    project = _build_project(nodes.values())
    assets = AssetCatalogV3(schema_version=3, assets={})
    destination.mkdir(parents=True, exist_ok=True)
    output_nodes = destination / "nodes"
    output_nodes.mkdir(parents=True, exist_ok=True)
    expected_node_files = {f"{node_id}.json" for node_id in nodes}
    for stale_path in sorted(output_nodes.glob("*.json")):
        if (
            stale_path.name not in expected_node_files
            and stale_path.is_file()
        ):
            stale_path.unlink()

    _write_json(destination / "project.json", project.model_dump(mode="json"))
    _write_json(destination / "assets.json", assets.model_dump(mode="json"))
    for node_id in sorted(nodes):
        _write_json(
            output_nodes / f"{node_id}.json",
            nodes[node_id].model_dump(mode="json"),
        )


def _apply_project_repairs(
    node: StoryNodeV3,
    source: StoryNodeV2,
) -> StoryNodeV3:
    parent_node_id = PARENT_FIXES.get(node.id, node.meta.parent_node_id)
    choices: list[StoryChoiceV3] = []
    for choice in node.choices:
        next_action = choice.next
        target = RETURN_TARGET_FIXES.get(
            choice.id,
            OWNER_RETURN_FIXES.get(choice.id),
        )
        if target is not None:
            next_action = next_action.model_copy(update={"target": target})
        if choice.id in {"E_choice_11", "H_choice_10", "J_choice_03"}:
            next_action = next_action.model_copy(update={"mode": "travel"})

        availability = choice.availability.model_copy(
            update={
                "condition": _rewrite_zhang_trust_condition(
                    choice.availability.condition
                )
            }
        )
        effects = choice.effects
        repeat_policy = choice.repeat_policy
        if choice.id == "D_choice_05":
            effects = [
                ModifyAttributeEffect(
                    type="modify_attribute",
                    attribute="zhang_trust",
                    operation="set",
                    value=3,
                )
            ]
        elif choice.id == "D_choice_09":
            effects = [
                ModifyCounterEffect(
                    type="modify_counter",
                    counter="half_cycles",
                    operation="add",
                    value=1,
                )
            ]
        elif choice.id == "H_choice_09":
            effects = [
                ModifyCounterEffect(
                    type="modify_counter",
                    counter="completed_cycles",
                    operation="add",
                    value=1,
                )
            ]
        elif choice.id == "S20_choice_01":
            effects = [
                RestoreEntryAttributeEffect(
                    type="restore_entry_attribute",
                    attribute="sanity",
                )
            ]
            repeat_policy = "once_per_cycle"

        choices.append(
            choice.model_copy(
                update={
                    "availability": availability,
                    "effects": effects,
                    "next": next_action,
                    "repeat_policy": repeat_policy,
                }
            )
        )

    return node.model_copy(
        update={
            "meta": node.meta.model_copy(
                update={"parent_node_id": parent_node_id}
            ),
            "choices": choices,
            "routing": _migrate_routing(source),
        }
    )


def _rewrite_zhang_trust_condition(
    condition: ConditionV3 | None,
) -> ConditionV3 | None:
    if condition is None:
        return None
    if condition.type == "flag_equals" and condition.flag == "zhang_trust":
        return AttributeCompareCondition(
            type="attribute_compare",
            attribute="zhang_trust",
            operator="gte",
            value=1,
        )
    if condition.type in {"all", "any"}:
        return condition.model_copy(
            update={
                "conditions": [
                    _rewrite_zhang_trust_condition(nested)
                    for nested in condition.conditions
                ]
            }
        )
    if condition.type == "not":
        return condition.model_copy(
            update={
                "condition": _rewrite_zhang_trust_condition(
                    condition.condition
                )
            }
        )
    return condition


def _migrate_routing(source: StoryNodeV2) -> RoutingV3 | None:
    if source.id == "E":
        crossing = source.routing.crossing
        if crossing is None:
            raise ValueError("E requires v2 crossing routing metadata")
        return CrossingRoutingV3(
            type="crossing",
            trigger_time=crossing["crossing_trigger_time"],
            target_era=crossing["crossing_target_era"],
            max_deep_interactions=2,
            deep_interactions=[
                CrossingInteractionV3(
                    choice_id=choice_id,
                    npc_id=npc_id,
                )
                for choice_id, npc_id in DEEP_INTERACTIONS
            ],
            duration_note=crossing.get("crossing_duration"),
            return_note=crossing.get("return_trigger"),
        )
    if source.id == "J":
        shortcut = source.routing.shortcut
        if shortcut is None:
            raise ValueError("J requires v2 shortcut routing metadata")
        entry_condition = parse_v2_condition(shortcut["entry_condition"])
        if entry_condition is None:
            raise ValueError("J shortcut requires an entry condition")
        return ShortcutRoutingV3(
            type="shortcut",
            entry_condition=entry_condition,
            entry_node_id=shortcut["entry_node"],
            exit_node_id=shortcut["exit_node"],
            counter_effects=[
                ModifyCounterEffect(
                    type="modify_counter",
                    counter="half_cycles",
                    operation="add",
                    value=1,
                )
            ],
        )
    if source.id == "K":
        warp = source.routing.warp
        if warp is None:
            raise ValueError("K requires v2 warp routing metadata")
        entry_condition = parse_v2_condition(warp["entry_condition"])
        if entry_condition is None:
            raise ValueError("K warp requires an entry condition")
        return WarpRoutingV3(
            type="warp",
            entry_condition=entry_condition,
            allowed_targets=WARP_TARGETS,
            exit_effects=[
                ModifyAttributeEffect(
                    type="modify_attribute",
                    attribute="sanity_max",
                    operation="add",
                    value=-1,
                    clamp=True,
                )
            ],
            sacrifice_target=None,
        )
    return None


def _build_project(nodes: Iterable[StoryNodeV3]) -> StoryProjectV3:
    flags: set[str] = set()
    item_ids = set(ITEM_NAMES)
    npc_ids = set(NPC_NAMES)

    for node in nodes:
        for value in _walk_json(node.model_dump(mode="json")):
            value_type = value.get("type")
            if value_type == "flag_equals":
                flags.add(value["flag"])
            elif value_type == "set_flag":
                flags.add(value["flag"])
            elif value_type in {"item", "inventory"}:
                item_ids.add(value["item_id"])
            elif value_type == "persist_node_item":
                item_ids.add(value["item_id"])
            elif value_type == "record_interaction":
                npc_ids.add(value["subject_id"])
            elif value_type == "dialogue":
                npc_ids.add(value["speaker_id"])

        npc_ids.update(node.authoring.npcs_present)
        item_ids.update(note.item_id for note in node.authoring.scene_items)
        for note in node.authoring.npc_item_notes:
            npc_ids.add(note.npc_id)
            item_ids.add(note.item_id)
            if note.required_flag is not None:
                flags.add(note.required_flag)
        if node.routing is not None and node.routing.type == "crossing":
            npc_ids.update(
                interaction.npc_id
                for interaction in node.routing.deep_interactions
            )

    return StoryProjectV3(
        schema_version=3,
        entry_node_id="A",
        attributes=ATTRIBUTE_DEFINITIONS,
        flags={
            flag: FlagDefinitionV3(
                display_name=flag.replace("_", " "),
                default=False,
            )
            for flag in sorted(flags)
        },
        items={
            item_id: ItemDefinitionV3(
                display_name=ITEM_NAMES.get(item_id, item_id),
                discardable=item_id in DISCARDABLE_ITEMS,
                cross_surface=item_id in CROSS_SURFACE_ITEMS,
            )
            for item_id in sorted(item_ids)
        },
        npcs={
            npc_id: NpcDefinitionV3(
                display_name=NPC_NAMES.get(
                    npc_id,
                    "玩家" if npc_id == "player" else npc_id,
                )
            )
            for npc_id in sorted(npc_ids)
        },
        counters=["completed_cycles", "half_cycles"],
        jump_modes=["stay", "travel", "shortcut", "warp"],
    )


def _walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_json(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_json(nested)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _migrate_content_block(
    block: ContentBlock,
    local_ids: "_NodeLocalIdMapper",
):
    common = {
        "id": local_ids.migrate(block.id, namespace="block"),
        "text": block.text,
        "when": parse_v2_condition(block.when),
    }
    if block.type == "narration":
        return NarrationContentBlockV3(type="narration", **common)
    if block.type == "dialogue":
        return DialogueContentBlockV3(
            type="dialogue",
            speaker_id=block.speaker_id,
            **common,
        )
    return SystemContentBlockV3(type="system", **common)


def _migrate_scene(node: StoryNodeV2) -> SceneV3:
    background_id = _existing_story_id_or_none(node.scene.background)
    return SceneV3(
        background_id=background_id,
        allow_no_background=background_id is None,
        ambient_id=_existing_story_id_or_none(node.scene.ambient),
        palette=node.scene.palette,
        atmosphere=node.scene.atmosphere,
    )


def _migrate_authoring(node: StoryNodeV2) -> AuthoringV3:
    npc_item_mapping = node.authoring.npc_item_mapping
    if npc_item_mapping is None:
        npc_item_notes = []
    elif isinstance(npc_item_mapping, list):
        npc_item_notes = [
            NpcItemNoteV3(
                npc_id=entry["npc_id"],
                item_id=entry["item_id"],
                required_flag=entry.get("flag"),
            )
            for entry in npc_item_mapping
        ]
    else:
        raise ValueError(
            f"Unsupported v2 npc_item_mapping at node {node.id}: "
            f"{type(npc_item_mapping).__name__}"
        )

    gender_variant = node.authoring.gender_variant
    return AuthoringV3(
        trigger_description=node.meta.trigger_condition,
        npcs_present=node.authoring.npcs_present,
        scene_items=[
            SceneItemNoteV3(
                item_id=entry["item_id"],
                location=entry["location"],
                acquisition_note=entry.get("acquire_condition"),
            )
            for entry in node.authoring.scene_items
        ],
        npc_item_notes=npc_item_notes,
        sensory=node.authoring.sensory,
        gender_variant=(
            GenderVariantNoteV3.model_validate(gender_variant)
            if gender_variant is not None
            else None
        ),
        notes=[],
    )


def _migrate_local_id(value: str) -> str:
    try:
        return validate_story_id(value)
    except ValueError:
        pass

    candidate = _INVALID_LOCAL_ID_RE.sub("_", value.strip())
    if not candidate or not candidate[0].isascii() or not candidate[0].isalpha():
        candidate = f"id_{candidate}"
    candidate = candidate[:64]
    try:
        return validate_story_id(candidate)
    except ValueError:
        return validate_story_id(f"id_{candidate}"[:64])


class _NodeLocalIdMapper:
    """Assign valid, collision-safe entry and block IDs within one node."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._source_ids: dict[tuple[str, str], str] = {}
        self._output_ids: dict[tuple[str, str], str] = {}

    def migrate(self, value: str, *, namespace: str) -> str:
        source_key = (namespace, value)
        if source_key in self._source_ids:
            return self._source_ids[source_key]

        candidate = _migrate_local_id(value)
        output_key = (namespace, candidate)
        existing_source = self._output_ids.get(output_key)
        if existing_source is not None and existing_source != value:
            candidate = self._disambiguate(
                value,
                base=candidate,
                namespace=namespace,
            )
            output_key = (namespace, candidate)

        existing_source = self._output_ids.get(output_key)
        if existing_source is not None and existing_source != value:
            raise ValueError(
                f"Unable to assign unique {namespace} id in node "
                f"{self.node_id}: {existing_source!r} and {value!r}"
            )

        self._source_ids[source_key] = candidate
        self._output_ids[output_key] = value
        return candidate

    def _disambiguate(
        self,
        value: str,
        *,
        base: str,
        namespace: str,
    ) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        for digest_length in range(8, 61, 4):
            prefix_length = 63 - digest_length
            candidate = f"{base[:prefix_length]}_{digest[:digest_length]}"
            output_key = (namespace, candidate)
            if output_key not in self._output_ids:
                return validate_story_id(candidate)
        raise ValueError(
            f"Unable to disambiguate {namespace} id in node "
            f"{self.node_id}: {value!r}"
        )


def _existing_story_id_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return validate_story_id(value)
    except ValueError:
        return None
