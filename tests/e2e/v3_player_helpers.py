"""Shared helpers for pure-v3 player-facing E2E tests."""

from __future__ import annotations

import time

import requests
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:5173"
PLAY_URL = f"{BASE_URL}/play"
API_BASE = "http://localhost:8000/api"


def start_frame() -> dict:
    response = requests.get(f"{API_BASE}/game/start", timeout=5)
    assert response.status_code == 200, response.text
    return response.json()


def choose(frame: dict, choice_id: str) -> dict:
    node_id = frame["node"]["id"]
    response = requests.post(
        f"{API_BASE}/game/choose/{node_id}",
        json={"choice_id": choice_id, "turn_id": frame["turn_id"]},
        timeout=5,
    )
    assert response.status_code == 200, response.text
    return response.json()


def resume(state: dict) -> dict:
    response = requests.post(f"{API_BASE}/game/resume", json=state, timeout=5)
    assert response.status_code == 200, response.text
    return response.json()


def available_choice_ids(frame: dict) -> set[str]:
    return {
        choice["id"]
        for choice in frame["available_choices"]
        if choice["available"]
    }


def open_game(page: Page) -> None:
    page.goto(PLAY_URL)
    start_button = page.locator(".start-btn")
    expect(start_button).to_be_visible(timeout=10_000)
    start_button.click()
    expect(page.locator(".status-bar")).to_be_visible(timeout=10_000)
    expect(page.locator("[data-testid='story-block']").first).to_be_visible(
        timeout=10_000
    )


def advance_to_choices(page: Page, timeout_ms: int = 12_000) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    main = page.locator(".game-main")
    while time.monotonic() < deadline:
        choices = page.locator(".choice-btn")
        if choices.count() and choices.first.is_visible():
            return
        main.click(position={"x": 5, "y": 5}, force=True)
        page.wait_for_timeout(30)
    raise AssertionError("Choices did not become visible before timeout")


def click_choice(page: Page, keyword: str) -> None:
    advance_to_choices(page)
    button = page.locator(".choice-btn:not([disabled])", has_text=keyword).first
    expect(button).to_be_visible(timeout=5_000)
    expect(button).to_be_enabled(timeout=5_000)
    button.click()
