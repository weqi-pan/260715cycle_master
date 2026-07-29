"""Closed authoring and immutable snapshot contracts for Story System v3."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from ..story.identifiers import validate_story_id


StoryId = Annotated[str, AfterValidator(validate_story_id)]
CompareOperator = Literal["lt", "lte", "eq", "ne", "gte", "gt"]


class StrictV3Model(BaseModel):
    """Base for v3 values, whose JSON vocabulary is deliberately closed."""

    model_config = ConfigDict(extra="forbid")


# Conditions


class AttributeCompareCondition(StrictV3Model):
    type: Literal["attribute_compare"]
    attribute: StoryId
    operator: CompareOperator
    value: int


class FlagEqualsCondition(StrictV3Model):
    type: Literal["flag_equals"]
    flag: StoryId
    value: bool | int | str


class ItemCondition(StrictV3Model):
    type: Literal["item"]
    item_id: StoryId
    present: bool = True


class CounterCompareCondition(StrictV3Model):
    type: Literal["counter_compare"]
    counter: Literal["completed_cycles", "current_cycle", "half_cycles"]
    operator: CompareOperator
    value: int = Field(ge=0)


class AtNodeCondition(StrictV3Model):
    type: Literal["at_node"]
    node_id: StoryId


class AllCondition(StrictV3Model):
    type: Literal["all"]
    conditions: list["ConditionV3"] = Field(min_length=1)


class AnyCondition(StrictV3Model):
    type: Literal["any"]
    conditions: list["ConditionV3"] = Field(min_length=1)


class NotCondition(StrictV3Model):
    type: Literal["not"]
    condition: "ConditionV3"


ConditionV3: TypeAlias = Annotated[
    AttributeCompareCondition
    | FlagEqualsCondition
    | ItemCondition
    | CounterCompareCondition
    | AtNodeCondition
    | AllCondition
    | AnyCondition
    | NotCondition,
    Field(discriminator="type"),
]


# Effects


class ModifyAttributeEffect(StrictV3Model):
    type: Literal["modify_attribute"]
    attribute: StoryId
    operation: Literal["add", "set"]
    value: int
    clamp: bool = True


class SetFlagEffect(StrictV3Model):
    type: Literal["set_flag"]
    flag: StoryId
    value: bool | int | str


class InventoryEffect(StrictV3Model):
    type: Literal["inventory"]
    item_id: StoryId
    operation: Literal["add", "remove"]
    quantity: int = Field(default=1, ge=1)


class PersistNodeItemEffect(StrictV3Model):
    type: Literal["persist_node_item"]
    node_id: StoryId
    item_id: StoryId


class RecordInteractionEffect(StrictV3Model):
    type: Literal["record_interaction"]
    group: StoryId
    subject_id: StoryId


class ModifyCounterEffect(StrictV3Model):
    type: Literal["modify_counter"]
    counter: Literal["completed_cycles", "half_cycles"]
    operation: Literal["add", "set"]
    value: int


class MarkOnceEffect(StrictV3Model):
    type: Literal["mark_once"]
    key: StoryId
    scope: Literal["visit", "cycle", "session"]


class RestoreEntryAttributeEffect(StrictV3Model):
    type: Literal["restore_entry_attribute"]
    attribute: StoryId


StoryEffectV3: TypeAlias = Annotated[
    ModifyAttributeEffect
    | SetFlagEffect
    | InventoryEffect
    | PersistNodeItemEffect
    | RecordInteractionEffect
    | ModifyCounterEffect
    | MarkOnceEffect
    | RestoreEntryAttributeEffect,
    Field(discriminator="type"),
]


# Ordered authored content


class NarrationContentBlockV3(StrictV3Model):
    id: StoryId
    type: Literal["narration"]
    text: str
    when: ConditionV3 | None = None


class DialogueContentBlockV3(StrictV3Model):
    id: StoryId
    type: Literal["dialogue"]
    speaker_id: StoryId
    text: str
    when: ConditionV3 | None = None


class SystemContentBlockV3(StrictV3Model):
    id: StoryId
    type: Literal["system"]
    text: str
    when: ConditionV3 | None = None


class CheckResultContentBlockV3(StrictV3Model):
    id: StoryId
    type: Literal["check_result"]
    text: str
    when: ConditionV3 | None = None


ContentBlockV3: TypeAlias = Annotated[
    NarrationContentBlockV3
    | DialogueContentBlockV3
    | SystemContentBlockV3
    | CheckResultContentBlockV3,
    Field(discriminator="type"),
]


class EntrySequenceV3(StrictV3Model):
    id: StoryId
    when: ConditionV3 | None = None
    blocks: list[ContentBlockV3] = Field(min_length=1)


class ChoiceAvailabilityV3(StrictV3Model):
    condition: ConditionV3 | None = None
    locked_visibility: Literal["show", "hide"] = "show"
    locked_reason: str | None = None


class NextActionV3(StrictV3Model):
    target: StoryId
    mode: Literal["stay", "travel", "shortcut", "warp"]


class StoryChoiceV3(StrictV3Model):
    id: StoryId
    text: str
    short_text: str | None = None
    availability: ChoiceAvailabilityV3
    repeat_policy: Literal[
        "always", "once_per_visit", "once_per_cycle", "once_ever"
    ] = "once_per_visit"
    hint: str | None = None
    result: list[ContentBlockV3] = Field(default_factory=list)
    effects: list[StoryEffectV3] = Field(default_factory=list)
    next: NextActionV3


# Routing


class CrossingInteractionV3(StrictV3Model):
    choice_id: StoryId
    npc_id: StoryId


class CrossingRoutingV3(StrictV3Model):
    type: Literal["crossing"]
    trigger_time: str
    target_era: StoryId
    max_deep_interactions: int = Field(ge=1)
    deep_interactions: list[CrossingInteractionV3] = Field(min_length=1)
    duration_note: str | None = None
    return_note: str | None = None


class ShortcutRoutingV3(StrictV3Model):
    type: Literal["shortcut"]
    entry_condition: ConditionV3
    entry_node_id: StoryId
    exit_node_id: StoryId
    counter_effects: list[StoryEffectV3] = Field(default_factory=list)


class WarpRoutingV3(StrictV3Model):
    type: Literal["warp"]
    entry_condition: ConditionV3
    allowed_targets: list[StoryId] = Field(min_length=1)
    exit_effects: list[StoryEffectV3] = Field(min_length=1)
    sacrifice_target: StoryId | None = None


RoutingV3: TypeAlias = Annotated[
    CrossingRoutingV3 | ShortcutRoutingV3 | WarpRoutingV3,
    Field(discriminator="type"),
]


# Project and assets


class AttributeDefinitionV3(StrictV3Model):
    display_name: str
    default: int
    minimum: int
    maximum: int


class FlagDefinitionV3(StrictV3Model):
    display_name: str
    default: bool | int | str


class ItemDefinitionV3(StrictV3Model):
    display_name: str
    discardable: bool = False
    cross_surface: bool = False


class NpcDefinitionV3(StrictV3Model):
    display_name: str


class StoryProjectV3(StrictV3Model):
    schema_version: Literal[3]
    entry_node_id: StoryId
    attributes: dict[StoryId, AttributeDefinitionV3]
    flags: dict[StoryId, FlagDefinitionV3]
    items: dict[StoryId, ItemDefinitionV3]
    npcs: dict[StoryId, NpcDefinitionV3]
    counters: list[Literal["completed_cycles", "half_cycles"]]
    jump_modes: list[Literal["stay", "travel", "shortcut", "warp"]]


class AssetDefinitionV3(StrictV3Model):
    kind: Literal["background", "audio", "sprite"]
    path: str


class AssetCatalogV3(StrictV3Model):
    schema_version: Literal[3]
    assets: dict[StoryId, AssetDefinitionV3]


class SceneV3(StrictV3Model):
    background_id: StoryId | None = None
    allow_no_background: bool
    ambient_id: StoryId | None = None
    palette: str | None = None
    atmosphere: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_background_policy(self):
        if self.background_id is None and not self.allow_no_background:
            raise ValueError(
                "scene without background_id must set allow_no_background"
            )
        return self


# Node metadata and non-runtime authoring notes


class TerminalSpecV3(StrictV3Model):
    type: Literal["ending", "cycle_complete"]
    ending_id: StoryId | None = None


class StoryNodeMetaV3(StrictV3Model):
    name: str
    node_type: Literal["main", "normal", "special_shortcut", "special_warp"]
    position: float
    time_label: str | None = None
    parent_node_id: StoryId | None = None
    terminal: TerminalSpecV3 | None


class SceneItemNoteV3(StrictV3Model):
    item_id: StoryId
    location: str
    acquisition_note: str | None = None


class NpcItemNoteV3(StrictV3Model):
    npc_id: StoryId
    item_id: StoryId
    required_flag: StoryId | None = None


class GenderVariantNoteV3(StrictV3Model):
    male: str
    female: str


class AuthoringV3(StrictV3Model):
    trigger_description: str | None = None
    npcs_present: list[StoryId] = Field(default_factory=list)
    scene_items: list[SceneItemNoteV3] = Field(default_factory=list)
    npc_item_notes: list[NpcItemNoteV3] = Field(default_factory=list)
    sensory: str | None = None
    gender_variant: GenderVariantNoteV3 | None = None
    notes: list[str] = Field(default_factory=list)


class StoryNodeV3(StrictV3Model):
    schema_version: Literal[3]
    id: StoryId
    meta: StoryNodeMetaV3
    scene: SceneV3
    entry_sequences: list[EntrySequenceV3] = Field(min_length=1)
    choices: list[StoryChoiceV3] = Field(default_factory=list)
    routing: RoutingV3 | None = None
    authoring: AuthoringV3 = Field(default_factory=AuthoringV3)

    @model_validator(mode="after")
    def validate_node_local_contract(self):
        sequence_ids = [sequence.id for sequence in self.entry_sequences]
        if len(sequence_ids) != len(set(sequence_ids)):
            raise ValueError("entry sequence ids must be unique within a node")

        choice_ids = [choice.id for choice in self.choices]
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("choice ids must be unique within a node")

        block_ids = [
            block.id
            for sequence in self.entry_sequences
            for block in sequence.blocks
        ]
        block_ids.extend(
            block.id
            for choice in self.choices
            for block in choice.result
        )
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("content block ids must be unique within a node")

        for choice in self.choices:
            if choice.next.mode == "stay" and choice.next.target != self.id:
                raise ValueError("stay choice must target its owning node")
        return self


class StorySnapshotV3(StrictV3Model):
    schema_version: Literal[3]
    revision: str
    project: StoryProjectV3
    assets: AssetCatalogV3
    nodes: dict[StoryId, StoryNodeV3]


AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()
