"""Pure-v3 core gameplay checklist: API contract, choices, routes, and UI."""

import requests
from playwright.sync_api import Page, expect

from v3_player_helpers import (
    API_BASE,
    BASE_URL,
    advance_to_choices,
    available_choice_ids,
    choose,
    click_choice,
    open_game,
    resume,
    start_frame,
)


class TestPureV3Api:
    def test_health(self):
        response = requests.get(f"{API_BASE}/health", timeout=5)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_start_returns_v3_frame_and_server_turn(self):
        frame = start_frame()

        assert frame["node"]["id"] == "A"
        assert frame["node"]["entry_blocks"]
        assert frame["turn_id"]
        assert available_choice_ids(frame) == {
            "A_choice_01",
            "A_choice_02",
            "A_choice_07",
        }
        locked = next(
            choice
            for choice in frame["available_choices"]
            if choice["id"] == "A_choice_03"
        )
        assert locked["available"] is False

    def test_server_turn_advances_a_to_b_and_rejects_replay(self):
        initial = start_frame()
        selected = choose(initial, "A_choice_01")

        assert selected["node"]["id"] == "B"
        assert selected["state"]["current_node_id"] == "B"

        replay = requests.post(
            f"{API_BASE}/game/choose/A",
            json={
                "choice_id": "A_choice_01",
                "turn_id": initial["turn_id"],
            },
            timeout=5,
        )
        assert replay.status_code == 409

    def test_exploration_unlocks_clues_and_coin_item(self):
        explored = choose(start_frame(), "A_choice_02")
        assert explored["state"]["flags"]["exploring_surroundings"] is True
        assert {"A_choice_03", "A_choice_05", "A_choice_11", "A_choice_12"} <= (
            available_choice_ids(explored)
        )

        inspected = choose(explored, "A_choice_05")
        acquired = choose(inspected, "A_choice_06")

        assert acquired["state"]["inventory"] == [
            {
                "id": "item_qing_coin",
                "name": "清代顺治通宝",
                "discardable": True,
                "cross_surface": True,
                "count": 1,
            }
        ]
        assert "A_choice_06" not in available_choice_ids(acquired)

    def test_shortcut_route_enters_j_and_returns_to_a(self):
        state = start_frame()["state"]
        state["current_node_id"] = "E"
        state["flags"]["know_secret_tunnel"] = True

        at_e = resume(state)
        assert "E_choice_11" in available_choice_ids(at_e)
        at_j = choose(at_e, "E_choice_11")
        returned = choose(at_j, "J_choice_01")

        assert at_j["node"]["id"] == "J"
        assert returned["node"]["id"] == "A"
        assert returned["state"]["half_cycle_count"] == 1

    def test_warp_route_applies_uniform_exit_cost(self):
        state = start_frame()["state"]
        state["current_node_id"] = "H"
        state["flags"]["taoist_chant"] = True
        sanity_max = state["player_attributes"]["sanity_max"]

        at_h = resume(state)
        at_k = choose(at_h, "H_choice_10")
        returned = choose(at_k, "K_choice_02")

        assert at_k["node"]["id"] == "K"
        assert returned["node"]["id"] == "A"
        assert returned["state"]["player_attributes"]["sanity_max"] == (
            sanity_max - 1
        )


class TestPureV3PlayerUi:
    def test_start_screen_requires_player_entry(self, page: Page):
        page.goto(f"{BASE_URL}/play")
        expect(page.get_by_role("button", name="踏入循环")).to_be_visible()
        assert page.locator(".status-bar").count() == 0

        page.get_by_role("button", name="踏入循环").click()
        expect(page.locator(".status-bar")).to_be_visible(timeout=10_000)
        expect(page.locator(".node-name")).to_contain_text("荔湾广场正门")

    def test_visible_locked_choices_are_disabled(self, page: Page):
        open_game(page)
        advance_to_choices(page)

        enabled = page.locator(".choice-btn:not([disabled])")
        assert enabled.count() == 3
        locked = page.locator(".choice-btn", has_text="铜狮底座上的刻字")
        expect(locked).to_be_visible()
        expect(locked).to_be_disabled()

    def test_exploration_unlocks_player_options(self, page: Page):
        open_game(page)
        click_choice(page, "周边转转")
        advance_to_choices(page)

        expect(
            page.locator(".choice-btn", has_text="铜狮底座上的刻字")
        ).to_be_enabled()
        expect(
            page.locator(".choice-btn:not([disabled])", has_text="检查台阶")
        ).to_be_enabled()
        expect(page.locator(".choice-btn", has_text="B1入口")).to_be_enabled()
