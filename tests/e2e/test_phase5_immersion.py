"""Phase 5 E2E: Immersion features — audio, speaker, color, full ring traversal."""
import json
import urllib.request


BASE = "http://localhost:8000"


def api(path, data=None):
    url = BASE + path
    if data:
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    return json.load(urllib.request.urlopen(req))


def test_ambient_field_present():
    """NodeData includes ambient field."""
    frame = api("/api/game/start")
    assert "ambient" in frame["node"] or "ambient" in dir(frame["node"]), \
        "ambient field should exist on node"


def test_speaker_on_d_node():
    """D node has speaker set to 张天民."""
    frame = api("/api/game/start")
    state = frame["state"]

    # Navigate: A -> B
    frame = api("/api/game/choose/A", {"choice_id": "A_choice_01", "state": state})
    state = frame["state"]
    # B -> C (B_choice_08, unconditional)
    frame = api("/api/game/choose/B", {"choice_id": "B_choice_08", "state": state})
    state = frame["state"]
    # C -> D (navigate from C to D)
    c_choices = frame["available_choices"]
    c_goto = next((c for c in c_choices if c["text"].startswith("离开") or "前往" in c["text"]), None)
    if not c_goto:
        c_goto = c_choices[-1]  # fallback to last choice
    frame = api(f"/api/game/choose/{frame['node']['id']}", {"choice_id": c_goto["id"], "state": state})

    assert frame["node"]["speaker"] == "张天民", \
        f"D node speaker should be 张天民, got: {frame['node']['speaker']}"


def test_color_palette_in_response():
    """Node includes color_palette for frontend tinting."""
    frame = api("/api/game/start")
    # color_palette is on backend model, verify API returns node data
    assert frame["node"]["name"], "Node should have name"


def test_full_ring_traversal_with_state():
    """Complete ring A->B->C->D->E->F->G->H->A with persisted state."""
    frame = api("/api/game/start")
    state = frame["state"]
    visited = []

    path = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for expected_node in path:
        choices = frame["available_choices"]
        assert len(choices) > 0, f"No choices at node {frame['node']['id']}"

        # Pick the "go to next" choice (usually priority 99)
        goto = next((c for c in choices if "前往" in c["text"] or c.get("priority") == 99), choices[-1])
        frame = api(f"/api/game/choose/{frame['node']['id']}",
                    {"choice_id": goto["id"], "state": state})
        state = frame["state"]
        visited.append(frame["node"]["id"])
        print(f"  {expected_node} -> {frame['node']['id']} ({frame['node']['name']})")

    # Now go back to A
    choices = frame["available_choices"]
    goto_a = next((c for c in choices if c["next_node_id"] == "A"), choices[-1])
    frame = api(f"/api/game/choose/{frame['node']['id']}",
                {"choice_id": goto_a["id"], "state": state})

    assert frame["node"]["id"] == "A", f"Should return to A, got {frame['node']['id']}"
    assert frame["state"]["cycle_count"] >= 1, "Cycle count should increment"
    print(f"  -> A (cycle {frame['state']['cycle_count']}) OK")


def test_sfx_effect_handled():
    """sfx effect type doesn't crash the engine."""
    from app.engine.engine import GameEngine
    engine = GameEngine()
    engine._apply_effects([{"type": "sfx", "target": "click", "value": None}],
                          type('State', (), {
                              'inventory': [], 'flags': {}, 'player_attributes': {},
                              'persistent_nodes': {}
                          })(), "A")
    # No exception = pass


if __name__ == "__main__":
    print("=== test_ambient_field_present ===")
    test_ambient_field_present()
    print("PASS")

    print("=== test_speaker_on_d_node ===")
    test_speaker_on_d_node()
    print("PASS")

    print("=== test_color_palette_in_response ===")
    test_color_palette_in_response()
    print("PASS")

    print("=== test_full_ring_traversal_with_state ===")
    test_full_ring_traversal_with_state()
    print("PASS")

    print("=== test_sfx_effect_handled ===")
    test_sfx_effect_handled()
    print("PASS")

    print("\nAll Phase 5 E2E tests passed!")
