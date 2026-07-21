"""Phase 1–5 已知核心回归用例。

R0 阶段先以 strict xfail 固定缺陷。修复对应问题时，必须移除 xfail 并让断言正式通过。
"""

import pytest
from pydantic import ValidationError

from app.engine.engine import GameEngine
from app.engine.graph import ChoiceData, GraphBundle
from app.models.story import StoryNode
from app.schemas.game import ChoiceResult, GameState


def make_bundle(node_id: str, node_type: str = "main") -> GraphBundle:
    node = StoryNode(
        id=node_id,
        name=f"Node {node_id}",
        position=0.0,
        node_type=node_type,
        content=f"Content {node_id}",
        speaker=None,
        background=None,
    )
    return GraphBundle(node, [])


def make_choice(
    choice_id: str,
    from_node_id: str,
    next_node_id: str,
    *,
    condition: str | None = None,
    hidden_when_locked: bool = False,
    transition_text: str = "Result text",
) -> ChoiceData:
    return ChoiceData(
        id=choice_id,
        from_node_id=from_node_id,
        text=choice_id,
        short_text=None,
        next_node_id=next_node_id,
        condition=condition,
        effects=[],
        priority=1,
        hint="需要测试条件" if condition else None,
        is_hidden_when_locked=hidden_when_locked,
        transition_text=transition_text,
    )


def test_a_self_loop_does_not_complete_cycle():
    engine = GameEngine()
    graph = {"A": make_bundle("A")}
    graph["A"].choices = [make_choice("A.inspect", "A", "A")]
    state = GameState(current_node_id="A")

    frame = engine.process_choice(graph, "A", "A.inspect", state)

    assert frame.state.cycle_count == 0
    assert frame.cycle_event is None
    assert frame.speaker_names["npc_yan_yan"] == "燕妍"


def test_reaching_e_updates_half_cycle():
    engine = GameEngine()
    graph = {"D": make_bundle("D"), "E": make_bundle("E")}
    graph["D"].choices = [make_choice("D.to.E", "D", "E")]
    state = GameState(current_node_id="D")

    frame = engine.process_choice(graph, "D", "D.to.E", state)

    assert frame.state.half_cycle_count == 1


def test_unavailable_choice_is_hidden_even_when_authored_as_visible():
    engine = GameEngine()
    graph = {"A": make_bundle("A")}
    graph["A"].choices = [
        make_choice(
            "A.locked",
            "A",
            "A",
            condition="has_item:item_missing",
            hidden_when_locked=False,
        )
    ]
    state = GameState(current_node_id="A")

    choices = engine.resolve_available_choices(graph, "A", state)

    assert choices == []


def test_warp_entry_cannot_be_forged():
    engine = GameEngine()
    graph = {"A": make_bundle("A"), "K": make_bundle("K", "special_warp")}
    graph["K"].warp_config = {
        "entry_condition": "has_flag:taoist_chant",
        "warp_targets": ["A"],
    }
    state = GameState(current_node_id="A", flags={})

    with pytest.raises(ValueError, match="warp|condition|available"):
        engine.process_choice(graph, "A", "__warp_K_enter", state)


def test_first_warp_exit_reduces_sanity_max_from_current_sanity():
    engine = GameEngine()
    graph = {"A": make_bundle("A"), "K": make_bundle("K", "special_warp")}
    graph["K"].warp_config = {
        "entry_condition": "has_flag:taoist_chant",
        "warp_targets": ["A"],
    }
    state = GameState(current_node_id="K")

    frame = engine.process_choice(graph, "K", "__warp_K_exit_A", state)

    assert frame.state.player_attributes["sanity_max"] == 99


def test_shortcut_j_to_a_counts_half_cycle_not_full_cycle():
    engine = GameEngine()
    graph = {"J": make_bundle("J"), "A": make_bundle("A")}
    graph["J"].choices = [make_choice("J.to.A", "J", "A")]
    state = GameState(current_node_id="J")

    frame = engine.process_choice(graph, "J", "J.to.A", state)

    assert frame.state.half_cycle_count == 1
    assert frame.state.cycle_count == 0
    assert frame.cycle_event is None


def test_warp_k_to_a_does_not_fake_cycle_completion():
    engine = GameEngine()
    graph = {"K": make_bundle("K", "special_warp"), "A": make_bundle("A")}
    graph["K"].warp_config = {
        "entry_condition": "has_flag:taoist_chant",
        "warp_targets": ["A"],
    }
    state = GameState(current_node_id="K")

    frame = engine.process_choice(graph, "K", "__warp_K_exit_A", state)

    assert frame.state.cycle_count == 0
    assert frame.cycle_event is None


def test_normal_h_to_a_completes_full_cycle():
    engine = GameEngine()
    graph = {"H": make_bundle("H"), "A": make_bundle("A")}
    graph["H"].choices = [make_choice("H.to.A", "H", "A")]
    state = GameState(current_node_id="H")

    frame = engine.process_choice(graph, "H", "H.to.A", state)

    assert frame.state.cycle_count == 1
    assert frame.cycle_event is not None


def test_legacy_result_templates_are_resolved_before_returning_frame():
    engine = GameEngine()
    graph = {"A": make_bundle("A")}
    graph["A"].choices = [make_choice(
        "A.template",
        "A",
        "A",
        transition_text=(
            "开头。{{#if cycle>=2}}高轮文本{{else}}低轮文本{{/if}}"
            "\n\n[获得道具：测试物品] [sanity -1]"
        ),
    )]
    state = GameState(current_node_id="A", cycle_count=2)

    frame = engine.process_choice(graph, "A", "A.template", state)

    assert frame.transition_text == "开头。高轮文本"
    assert "{{" not in frame.transition_text
    assert "[获得道具" not in frame.transition_text


def test_legacy_node_content_resolves_false_template_branch():
    engine = GameEngine()
    graph = {"A": make_bundle("A")}
    graph["A"].content = "{{#if cycle>=3}}第三轮{{else}}第一轮{{/if}}"
    state = GameState(current_node_id="A", cycle_count=1)

    assert engine._resolve_content(graph["A"], state) == "第一轮"


def test_legacy_cycle_range_uses_highest_numeric_threshold():
    engine = GameEngine()
    bundle = make_bundle("A")
    bundle.cycle_variants = {
        "cycle_3+": "第三轮以上",
        "cycle_9+": "第九轮以上",
        "cycle_10+": "第十轮以上",
        "cycle_11+": "第十一轮以上",
    }

    assert engine._resolve_content(
        bundle, GameState(current_node_id="A", cycle_count=12)
    ) == "第十一轮以上"


def test_choice_result_requires_non_empty_target_node():
    with pytest.raises(ValidationError):
        ChoiceResult(id="broken", text="坏选项", next_node_id="")
