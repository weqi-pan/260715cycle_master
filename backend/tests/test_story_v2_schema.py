"""故事 JSON v2 数据契约测试。"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.story_v2 import ContentBlock, StoryNodeV2


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def make_node_data():
    return {
        "schema_version": 2,
        "id": "A",
        "meta": {
            "name": "起点",
            "node_type": "main",
            "position": 0,
        },
        "scene": {},
        "entry_sequences": [
            {
                "id": "A.entry.default",
                "blocks": [
                    {
                        "id": "A.entry.narration.01",
                        "type": "narration",
                        "text": "你站在正门前。",
                    }
                ],
            }
        ],
        "choices": [
            {
                "id": "A.choice.inspect",
                "label": "观察铜狮",
                "result_blocks": [
                    {
                        "id": "A.choice.inspect.narration.01",
                        "type": "narration",
                        "text": "铜狮的眼睛似乎动了一下。",
                    }
                ],
                "effects": [],
                "next": {"node_id": "A", "mode": "stay"},
            }
        ],
        "routing": {},
        "authoring": {},
    }


def test_valid_story_node_v2():
    node = StoryNodeV2.model_validate(make_node_data())
    assert node.id == "A"
    assert node.choices[0].next.mode == "stay"


def test_dialogue_requires_speaker_id():
    with pytest.raises(ValidationError, match="speaker_id"):
        ContentBlock(
            id="A.dialogue.01",
            type="dialogue",
            text="你是谁？",
        )


@pytest.mark.parametrize(
    "text",
    [
        '"你知道吗？"',
        '"你知道吗？"她压低声音。',
        '她压低声音。"你知道吗？"',
        '“你知道吗？”',
    ],
)
def test_dialogue_rejects_authored_quotation_marks(text):
    with pytest.raises(ValidationError, match="quotation marks"):
        ContentBlock(
            id="A.dialogue.quoted",
            type="dialogue",
            speaker_id="npc_test",
            text=text,
        )


def test_control_template_is_forbidden():
    with pytest.raises(ValidationError, match="control templates"):
        ContentBlock(
            id="A.narration.01",
            type="narration",
            text="{{#if cycle>=2}}又见面了。{{/if}}",
        )


def test_unknown_interpolation_variable_is_forbidden():
    with pytest.raises(ValidationError, match="unsupported story variable"):
        ContentBlock(
            id="A.narration.unknown-variable",
            type="narration",
            text="第{{unknown_count}}次。",
        )


def test_supported_interpolation_variable_is_valid():
    block = ContentBlock(
        id="A.narration.cycle-variable",
        type="narration",
        text="第{{cycle_count}}次。",
    )
    assert block.text == "第{{cycle_count}}次。"


def test_stay_choice_must_target_owning_node():
    data = make_node_data()
    data["choices"][0]["next"]["node_id"] = "B"
    with pytest.raises(ValidationError, match="stay choice"):
        StoryNodeV2.model_validate(data)


def test_duplicate_block_id_is_rejected():
    data = make_node_data()
    data["choices"][0]["result_blocks"][0]["id"] = "A.entry.narration.01"
    with pytest.raises(ValidationError, match="block ids"):
        StoryNodeV2.model_validate(data)


def test_all_migrated_story_v2_files_validate():
    node_dir = PROJECT_ROOT / "data" / "story_data_v2" / "nodes"
    paths = sorted(node_dir.glob("*.json"))
    assert len(paths) == 30

    nodes = [
        StoryNodeV2.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        for path in paths
    ]
    assert sum(len(node.choices) for node in nodes) == 143
