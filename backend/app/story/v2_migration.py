"""Pure, deterministic conversion from Story System v2 values to v3."""

from __future__ import annotations

import hashlib
import re
from typing import cast

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
    ChoiceAvailabilityV3,
    CompareOperator,
    ConditionV3,
    CounterCompareCondition,
    DialogueContentBlockV3,
    EntrySequenceV3,
    FlagEqualsCondition,
    GenderVariantNoteV3,
    InventoryEffect,
    ItemCondition,
    ModifyAttributeEffect,
    NarrationContentBlockV3,
    NextActionV3,
    NotCondition,
    NpcItemNoteV3,
    PersistNodeItemEffect,
    SceneItemNoteV3,
    SceneV3,
    SetFlagEffect,
    StoryChoiceV3,
    StoryEffectV3,
    StoryNodeMetaV3,
    StoryNodeV3,
    SystemContentBlockV3,
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
            for choice in sorted(
                node.choices,
                key=lambda choice: (choice.priority, choice.id),
            )
        ],
        routing=None,
        authoring=_migrate_authoring(node),
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
