"""故事内容 JSON v2 的严格数据契约。

v2 使用内容块明确表达“正文、对话、系统提示”的展示顺序，避免前端从
content、dialogue_lines 和 transition_text 三处猜测剧情流程。
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CONTROL_TEMPLATE_RE = re.compile(r"\{\{\s*(?:#if|else|/if)\b", re.IGNORECASE)
DIALOGUE_QUOTATION_RE = re.compile(r'["“”]')
VARIABLE_TEMPLATE_RE = re.compile(
    r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}",
    re.IGNORECASE,
)
SUPPORTED_STORY_VARIABLES = {"cycle_count", "half_cycle_count"}


class StrictModel(BaseModel):
    """拒绝未知字段的 v2 基类。"""

    model_config = ConfigDict(extra="forbid")


class StoryEffectV2(StrictModel):
    """结构化游戏效果；显示文本不得代替效果数据。"""

    type: str = Field(min_length=1)
    target: str | None = None
    value: Any = None


class ContentBlock(StrictModel):
    """播放器可顺序消费的最小内容单元。"""

    id: str = Field(min_length=1)
    type: Literal["narration", "dialogue", "system"]
    text: str = Field(min_length=1)
    speaker_id: str | None = None
    when: str | None = None

    @model_validator(mode="after")
    def validate_block(self):
        if self.type == "dialogue" and not self.speaker_id:
            raise ValueError("dialogue block requires speaker_id")
        if self.type == "dialogue" and DIALOGUE_QUOTATION_RE.search(self.text):
            raise ValueError(
                "dialogue text must not contain authored quotation marks; "
                "split speech and narration into separate content blocks"
            )
        if self.type != "dialogue" and self.speaker_id is not None:
            raise ValueError("only dialogue block may define speaker_id")
        if CONTROL_TEMPLATE_RE.search(self.text):
            raise ValueError("control templates are forbidden; use block.when")
        unknown_variables = {
            match.group(1)
            for match in VARIABLE_TEMPLATE_RE.finditer(self.text)
            if match.group(1) not in SUPPORTED_STORY_VARIABLES
        }
        if unknown_variables:
            names = ", ".join(sorted(unknown_variables))
            raise ValueError(f"unsupported story variable: {names}")
        return self


class EntrySequence(StrictModel):
    """进入节点时按条件选中的内容序列。"""

    id: str = Field(min_length=1)
    when: str | None = None
    priority: int = 0
    blocks: list[ContentBlock] = Field(min_length=1)


class NextAction(StrictModel):
    """选择播放结果后的导航行为。"""

    node_id: str = Field(min_length=1)
    mode: Literal["stay", "travel", "shortcut", "warp"]


class StoryChoiceV2(StrictModel):
    """与所属节点共置的选择和结果内容。"""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    short_label: str | None = None
    condition: str | None = None
    locked_visibility: Literal["show", "hide"] = "show"
    repeat_policy: Literal[
        "always", "once_per_visit", "once_per_cycle", "once_ever"
    ] = "once_per_visit"
    priority: int = 99
    hint: str | None = None
    result_blocks: list[ContentBlock] = Field(default_factory=list)
    effects: list[StoryEffectV2] = Field(default_factory=list)
    next: NextAction


class StoryNodeMeta(StrictModel):
    """节点身份、拓扑与展示标题。"""

    name: str = Field(min_length=1)
    node_type: Literal["main", "normal", "special_shortcut", "special_warp"]
    position: float
    time_label: str | None = None
    parent_node_id: str | None = None
    trigger_condition: str | None = None


class SceneSpec(StrictModel):
    """不参与剧情规则的场景表现配置。"""

    background: str | None = None
    palette: str | None = None
    ambient: str | None = None
    atmosphere: list[str] = Field(default_factory=list)


class RoutingSpec(StrictModel):
    """莫比乌斯跨面、J 捷径和 K 跃迁配置。"""

    crossing: dict[str, Any] | None = None
    shortcut: dict[str, Any] | None = None
    warp: dict[str, Any] | None = None


class AuthoringSpec(StrictModel):
    """编剧和编辑器使用、暂不直接驱动播放器的结构化元数据。"""

    linked_sub_nodes: list[dict[str, Any]] = Field(default_factory=list)
    npcs_present: list[str] = Field(default_factory=list)
    scene_items: list[dict[str, Any]] = Field(default_factory=list)
    npc_item_mapping: dict[str, Any] | list[Any] | None = None
    sensory: str | None = None
    gender_variant: dict[str, Any] | None = None


class StoryNodeV2(StrictModel):
    """单文件内聚的 v2 故事节点。"""

    schema_version: Literal[2] = 2
    id: str = Field(min_length=1)
    meta: StoryNodeMeta
    scene: SceneSpec = Field(default_factory=SceneSpec)
    entry_sequences: list[EntrySequence] = Field(min_length=1)
    choices: list[StoryChoiceV2] = Field(default_factory=list)
    routing: RoutingSpec = Field(default_factory=RoutingSpec)
    authoring: AuthoringSpec = Field(default_factory=AuthoringSpec)

    @model_validator(mode="after")
    def validate_node(self):
        sequence_ids = [sequence.id for sequence in self.entry_sequences]
        if len(sequence_ids) != len(set(sequence_ids)):
            raise ValueError("entry sequence ids must be unique within a node")

        choice_ids = [choice.id for choice in self.choices]
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("choice ids must be unique within a node")

        block_ids: list[str] = []
        for sequence in self.entry_sequences:
            block_ids.extend(block.id for block in sequence.blocks)
        for choice in self.choices:
            block_ids.extend(block.id for block in choice.result_blocks)
            if choice.next.mode == "stay" and choice.next.node_id != self.id:
                raise ValueError("stay choice must target its owning node")
            if choice.next.mode != "stay" and choice.next.node_id == self.id:
                raise ValueError("same-node choice must use stay mode")

        if len(block_ids) != len(set(block_ids)):
            raise ValueError("content block ids must be unique within a node")
        return self
