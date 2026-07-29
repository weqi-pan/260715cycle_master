"""Pure-v3 final player checks: saves, playback, navigation, and map UI."""

import json
from pathlib import Path
from uuid import uuid4

import requests
from playwright.sync_api import Page, expect

from v3_player_helpers import (
    API_BASE,
    BASE_URL,
    advance_to_choices,
    choose,
    click_choice,
    open_game,
    resume,
    start_frame,
)


class TestV3ContentBoundary:
    def test_all_story_v3_json_files_are_valid(self):
        story_root = Path(__file__).resolve().parents[2] / "data" / "story_v3"
        files = sorted(story_root.rglob("*.json"))

        assert files
        for path in files:
            with path.open(encoding="utf-8") as handle:
                json.load(handle)
        assert len(list((story_root / "nodes").glob("*.json"))) == 30


class TestV3SaveRoundTrip:
    def test_create_load_update_and_delete_save(self):
        explored = choose(start_frame(), "A_choice_02")
        inspected = choose(explored, "A_choice_05")
        acquired = choose(inspected, "A_choice_06")
        save_name = f"task11-{uuid4().hex[:8]}"

        created = requests.post(
            f"{API_BASE}/saves/",
            params={"name": save_name},
            json=acquired["state"],
            timeout=5,
        )
        assert created.status_code == 200, created.text
        save_id = created.json()["id"]

        try:
            listed = requests.get(f"{API_BASE}/saves/", timeout=5)
            assert listed.status_code == 200
            assert any(save["id"] == save_id for save in listed.json()["saves"])

            loaded = requests.get(f"{API_BASE}/saves/load/{save_id}", timeout=5)
            assert loaded.status_code == 200, loaded.text
            loaded_state = loaded.json()
            assert loaded_state["current_node_id"] == "A"
            assert loaded_state["inventory"] == acquired["state"]["inventory"]
            assert loaded_state["choice_history"] == acquired["state"]["choice_history"]

            resumed = resume(loaded_state)
            assert resumed["turn_id"]

            loaded_state["cycle_count"] = 2
            updated = requests.put(
                f"{API_BASE}/saves/{save_id}",
                json=loaded_state,
                timeout=5,
            )
            assert updated.status_code == 200, updated.text
            reloaded = requests.get(
                f"{API_BASE}/saves/load/{save_id}", timeout=5
            ).json()
            assert reloaded["cycle_count"] == 2
        finally:
            deleted = requests.delete(f"{API_BASE}/saves/{save_id}", timeout=5)
            assert deleted.status_code == 200

    def test_unknown_save_returns_not_found(self):
        response = requests.get(f"{API_BASE}/saves/load/not-found", timeout=5)
        assert response.status_code == 404


class TestPlaybackUi:
    def test_choices_stay_hidden_during_typing_then_appear(self, page: Page):
        open_game(page)

        assert page.locator(".choice-btn").count() == 0
        page.locator(".game-main").click(position={"x": 5, "y": 5}, force=True)
        first_block = page.locator("[data-testid='story-block']").first
        expect(first_block).to_contain_text("夕阳将荔湾广场")
        assert page.locator(".choice-btn").count() == 0

        advance_to_choices(page)
        expect(page.locator(".choice-btn").first).to_be_visible()

    def test_status_bar_shows_cycle_attributes_and_location(self, page: Page):
        open_game(page)

        expect(page.locator(".cycle-num")).to_have_text("0")
        labels = page.locator(".attr-label").all_inner_texts()
        assert {"理智", "勇气", "灵感"} <= set(labels)
        expect(page.locator(".node-name")).to_contain_text("荔湾广场正门")
        expect(page.locator(".time-label")).to_contain_text("第一天")

    def test_cycle_map_renders_eight_main_nodes(self, page: Page):
        open_game(page)
        page.locator(".node-name").click()

        expect(page.locator(".cycle-map")).to_be_visible()
        labels = page.locator(".cycle-map text").all_text_contents()
        assert set("ABCDEFGH") <= set(labels)

    def test_a_to_b_navigation_updates_player_frame(self, page: Page):
        open_game(page)
        click_choice(page, "办理入住")

        expect(page.locator(".node-name")).to_contain_text(
            "德星路出租屋", timeout=10_000
        )
        expect(page.locator(".game-play")).to_be_visible()

    def test_refresh_returns_to_explicit_start_screen(self, page: Page):
        open_game(page)
        page.reload()

        expect(page.get_by_role("button", name="踏入循环")).to_be_visible(
            timeout=10_000
        )
        assert page.locator(".status-bar").count() == 0

    def test_rapid_clicks_do_not_break_player_shell(self, page: Page):
        open_game(page)
        for _ in range(8):
            page.locator(".game-main").click(
                position={"x": 5, "y": 5}, force=True
            )
        expect(page.locator(".game-play")).to_be_visible()
        assert page.locator(".error").count() == 0


class TestApiNavigationState:
    def test_a_to_b_to_c_keeps_authoritative_turn_chain(self):
        at_b = choose(start_frame(), "A_choice_01")
        at_c = choose(at_b, "B_choice_08")

        assert at_b["node"]["id"] == "B"
        assert at_c["node"]["id"] == "C"
        assert at_c["state"]["visited_nodes"][-2:] == ["A", "B"]
        assert at_c["state"]["current_node_id"] == "C"
        assert at_b["turn_id"] != at_c["turn_id"]

    def test_health_and_frontend_are_reachable(self):
        assert requests.get(f"{API_BASE}/health", timeout=5).status_code == 200
        assert requests.get(BASE_URL, timeout=5).status_code == 200
