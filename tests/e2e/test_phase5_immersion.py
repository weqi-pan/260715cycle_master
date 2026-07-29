"""Pure-v3 immersion checks for content blocks, speakers, scene data, and flow."""

import time

from playwright.sync_api import Page, expect

from v3_player_helpers import (
    advance_to_choices,
    choose,
    click_choice,
    open_game,
    start_frame,
)


class TestV3SceneData:
    def test_start_frame_exposes_scene_and_ordered_content(self):
        frame = start_frame()

        assert frame["node"]["ambient"] is None
        assert frame["node"]["color_palette"] == "暗红+金色"
        assert frame["node"]["entry_blocks"]
        assert all(block["id"] for block in frame["node"]["entry_blocks"])
        assert frame["scene_effects"] == []

    def test_c_node_dialogue_uses_v3_speaker_registry(self):
        at_b = choose(start_frame(), "A_choice_01")
        at_c = choose(at_b, "B_choice_08")

        speaker_ids = {
            block["speaker_id"]
            for block in at_c["node"]["entry_blocks"]
            if block["type"] == "dialogue"
        }
        assert "npc_yan_yan" in speaker_ids
        assert at_c["speaker_names"]["npc_yan_yan"] == "燕妍"

    def test_full_main_ring_completes_one_cycle(self):
        frame = start_frame()
        route = [
            ("A_choice_01", "B"),
            ("B_choice_08", "C"),
            ("C_choice_07", "D"),
            ("D_choice_09", "E"),
            ("E_choice_12", "F"),
            ("F_choice_10", "G"),
            ("G_choice_09", "H"),
            ("H_choice_09", "A"),
        ]

        for choice_id, expected_node in route:
            frame = choose(frame, choice_id)
            assert frame["node"]["id"] == expected_node

        assert frame["state"]["cycle_count"] == 1
        assert frame["cycle_event"] == {
            "type": "cycle_complete",
            "cycle_count": 1,
            "half_cycle_count": 1,
        }


class TestImmersivePlayerUi:
    def test_player_shell_renders_without_optional_ambient_audio(self, page: Page):
        open_game(page)

        expect(page.locator(".bg-layer")).to_be_visible()
        expect(page.locator(".bg-vignette")).to_be_visible()
        expect(page.locator(".story-timeline")).to_be_visible()
        assert page.locator(".error").count() == 0

    def test_story_timeline_preserves_blocks_while_advancing(self, page: Page):
        open_game(page)
        first = page.locator("[data-testid='story-block']").first

        page.locator(".game-main").click(position={"x": 5, "y": 5}, force=True)
        expect(first).to_contain_text("夕阳将荔湾广场")
        first_text = first.inner_text()
        page.locator(".game-main").click(position={"x": 5, "y": 5}, force=True)

        assert page.locator("[data-testid='story-block']").count() >= 2
        assert first.inner_text() == first_text

    def test_c_dialogue_renders_named_chat_bubble(self, page: Page):
        open_game(page)
        click_choice(page, "办理入住")
        expect(page.locator(".node-name")).to_contain_text(
            "德星路出租屋", timeout=10_000
        )
        advance_to_choices(page)
        click_choice(page, "时间不早了")
        expect(page.locator(".node-name")).to_contain_text(
            "华林寺", timeout=10_000
        )

        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            chat = page.locator(".chat-row")
            if chat.count() and chat.first.is_visible():
                break
            page.locator(".game-main").click(
                position={"x": 5, "y": 5}, force=True
            )
            page.wait_for_timeout(30)
        else:
            raise AssertionError("C dialogue did not render")

        expect(page.locator(".chat-name", has_text="燕妍").first).to_be_visible()
        expect(page.locator(".chat-text").first).not_to_be_empty()

    def test_short_player_path_remains_interactive(self, page: Page):
        open_game(page)
        advance_to_choices(page)
        expect(page.locator(".choice-btn:not([disabled])").first).to_be_visible()

        click_choice(page, "办理入住")
        expect(page.locator(".game-play")).to_be_visible()
        assert page.locator(".error").count() == 0
