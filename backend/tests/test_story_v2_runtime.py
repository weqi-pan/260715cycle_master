"""v2 内容块进入运行 API 前的仓库选择测试。"""

from app.engine.condition_eval import ConditionEvaluator
from app.engine.story_v2_loader import StoryV2Loader
from app.routers.game import start_game
from app.schemas.game import GameState


def test_c_entry_uses_stable_npc_speaker_ids():
    loader = StoryV2Loader()
    blocks = loader.entry_blocks(
        "C", GameState(current_node_id="C"), ConditionEvaluator()
    )

    dialogue = [block for block in blocks if block.type == "dialogue"]
    assert dialogue
    assert {block.speaker_id for block in dialogue} == {"npc_yan_yan"}


def test_choice_result_exposes_dialogue_blocks_in_authored_order():
    loader = StoryV2Loader()
    blocks = loader.result_blocks(
        "C", "C_choice_01", GameState(current_node_id="C"), ConditionEvaluator()
    )

    assert [
        (block.type, block.speaker_id, block.text)
        for block in blocks[1:4]
    ] == [
        (
            "dialogue",
            "npc_yan_yan",
            "你知道吗，荔湾广场那个地方——",
        ),
        ("narration", None, "她压低声音，"),
        (
            "dialogue",
            "npc_yan_yan",
            "我查过了。1993年施工的时候，挖出了八口棺材。八口。死囚的棺材。"
            "而且那不是普通的墓——棺材底下发现了一个老青砖砌的地下空间，"
            "里面画满了道教符文。",
        ),
    ]


def test_highest_matching_cycle_entry_sequence_wins():
    loader = StoryV2Loader()
    blocks = loader.entry_blocks(
        "C", GameState(current_node_id="C", cycle_count=3), ConditionEvaluator()
    )

    assert blocks
    assert all(block.id.startswith("C.entry.cycle_3+") or block.id.startswith("C.cycle_3+") for block in blocks)
    assert all("{{" not in block.text for block in blocks)
    assert blocks[0].text.startswith("第3次来华林寺")


def test_player_and_npc_result_speakers_remain_distinct():
    loader = StoryV2Loader()
    blocks = loader.result_blocks(
        "E", "E_choice_05", GameState(current_node_id="E"), ConditionEvaluator()
    )

    speakers = [block.speaker_id for block in blocks if block.type == "dialogue"]
    assert speakers == ["player", "npc_a_liu", "npc_a_liu"]


def test_v2_is_a_complete_runtime_graph_source():
    graph = StoryV2Loader().load_graph()

    assert len(graph) == 30
    assert len(graph["A"].choices) == 12
    choice = next(item for item in graph["A"].choices if item.id == "A_choice_01")
    assert choice.next_node_id == "B"
    assert graph["K"].warp_config["warp_targets"] == list("ABCDEFGH")


def test_new_game_starts_without_a_story_database_session():
    frame = start_game()

    assert frame.node.id == "A"
    assert frame.node.entry_blocks
    assert frame.available_choices
