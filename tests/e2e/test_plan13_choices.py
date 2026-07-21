"""计划 13：选项只显示当前可执行且未消费的项目。"""

from playwright.sync_api import Page, expect


def advance_until_choices(page: Page) -> None:
    choices = page.locator("button.choice-btn")
    for _ in range(80):
        if choices.count() > 0:
            return
        page.locator(".content-wrapper").click(position={"x": 20, "y": 20})
    raise AssertionError("choices did not appear after advancing the timeline")


def test_selected_stay_choice_disappears(page: Page):
    page.goto("http://127.0.0.1:5173")
    page.get_by_role("button", name="踏入循环").click()
    advance_until_choices(page)

    choices = page.locator("button.choice-btn")
    expect(page.locator("button.choice-btn.locked")).to_have_count(0)
    selected = page.locator("button.choice-btn:not(.scene-trans)").first
    selected_text = selected.locator(".choice-text").inner_text()
    selected.click()
    advance_until_choices(page)

    expect(page.locator("button.choice-btn .choice-text", has_text=selected_text)).to_have_count(0)


def test_editor_reads_v2_story_graph(page: Page):
    page.goto("http://127.0.0.1:5173/editor")

    expect(page.get_by_role("heading", name="节点列表 (30)")).to_be_visible()
    expect(page.locator(".node-item")).to_have_count(30)
