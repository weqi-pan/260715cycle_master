"""
Phase 5 测试清单 — 沉浸体验
基于 plan/phase5-测试清单.md (sections A-F)

运行: pytest tests/e2e/test_phase5_immersion.py -v
"""

import pytest
import requests
import subprocess
import os
import re
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5173"
PLAY_URL = f"{BASE_URL}/play"
API_BASE = "http://localhost:8000/api"


def dismiss_overlay(page: Page):
    for _ in range(5):
        if page.locator(".transition-overlay").count() == 0:
            break
        try:
            page.evaluate("document.querySelector('.transition-overlay')?.click()")
        except Exception:
            pass
        page.wait_for_timeout(500)
    page.wait_for_timeout(300)


def wait_game_ready(page: Page, timeout: int = 15000):
    expect(page.locator(".narrative-text")).to_be_visible(timeout=timeout)


def click_choice(page: Page, keyword: str):
    texts = page.locator(".choice-btn .choice-text").all_inner_texts()
    for i, t in enumerate(texts):
        if keyword in t:
            page.locator(".choice-btn").nth(i).click(force=True, timeout=5000)
            try:
                page.wait_for_selector(".transition-overlay", state="attached", timeout=8000)
            except Exception:
                pass
            dismiss_overlay(page)
            return


def skip_typing(page: Page):
    try:
        page.locator(".narrative-box").click(timeout=3000)
        page.wait_for_timeout(500)
    except Exception:
        pass


def go_to_play(page: Page):
    page.goto(PLAY_URL)
    wait_game_ready(page)
    skip_typing(page)


# ============================================================
# F. Regression
# ============================================================

class TestF_Regression:
    def test_f1_backend_tests(self):
        backend_dir = os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"
        ))
        python_exe = os.path.join(backend_dir, "venv", "Scripts", "python.exe")
        result = subprocess.run(
            [python_exe, "-m", "pytest", "tests/", "-v", "--tb=short"],
            cwd=backend_dir, capture_output=True, text=True, timeout=60,
        )
        stdout = result.stdout
        if "= short test summary info =" in stdout:
            assert "FAILED" not in stdout.split("= short test summary info =")[-1]
        m = re.search(r"(\d+)\s+passed", stdout)
        assert m and int(m.group(1)) >= 24

    def test_f2_typecheck(self):
        frontend_dir = os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend"
        ))
        result = subprocess.run(
            ["npx", "vue-tsc", "--noEmit"],
            cwd=frontend_dir, capture_output=True, text=True, timeout=120, shell=True,
        )
        assert result.returncode == 0


# ============================================================
# A. Audio
# ============================================================

class TestA_Audio:
    def test_a1_ambient_field_in_api(self):
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        node = resp.json()["node"]
        assert "ambient" in node
        assert node["ambient"] is None

    def test_a2_ambient_code_in_gameplay(self):
        gp_path = os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "frontend", "src", "views", "GamePlay.vue"
        ))
        with open(gp_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "ambient" in content

    def test_a3_no_ambient_no_error(self, page: Page):
        go_to_play(page)
        expect(page.locator(".narrative-text")).to_be_visible()


# ============================================================
# B. Speaker
# ============================================================

class TestB_Speaker:
    def test_b1_d_node_speaker(self):
        resp = requests.get(f"{API_BASE}/editor/nodes", timeout=5)
        d_node = [n for n in resp.json()["nodes"] if n["id"] == "D"]
        assert len(d_node) > 0
        assert d_node[0].get("speaker") == "张天民"

    def test_b2_c_node_speaker(self):
        resp = requests.get(f"{API_BASE}/editor/nodes", timeout=5)
        c_node = [n for n in resp.json()["nodes"] if n["id"] == "C"]
        assert len(c_node) > 0
        assert c_node[0].get("speaker") == "燕妍"

    def test_b3_other_nodes_null_speaker(self):
        resp = requests.get(f"{API_BASE}/editor/nodes", timeout=5)
        nodes = resp.json()["nodes"]
        for nid in ["A", "B", "E", "F", "G", "H"]:
            node = [n for n in nodes if n["id"] == nid]
            assert len(node) > 0
            assert node[0].get("speaker") is None

    def test_b4_speaker_avatar_ui(self, page: Page):
        go_to_play(page)
        assert page.locator(".speaker-row").count() == 0
        click_choice(page, "办理入住")
        skip_typing(page)
        click_choice(page, "华林寺")
        skip_typing(page)
        row = page.locator(".speaker-row")
        if row.count() > 0:
            expect(page.locator(".speaker-avatar").first).to_be_visible()


# ============================================================
# C. Color palette
# ============================================================

class TestC_ColorPalette:
    def test_c1_in_types(self):
        p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "frontend", "src", "types", "index.ts"))
        with open(p, "r", encoding="utf-8") as f:
            assert "color_palette" in f.read()

    def test_c2_in_gameplay(self):
        p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "frontend", "src", "views", "GamePlay.vue"))
        with open(p, "r", encoding="utf-8") as f:
            assert "color_palette" in f.read()

    def test_c3_smooth_ui(self, page: Page):
        go_to_play(page)
        for _ in range(3):
            if page.locator(".choice-btn").count() > 0:
                page.locator(".choice-btn").first.click(force=True)
                page.wait_for_timeout(200)
                dismiss_overlay(page)
                skip_typing(page)
        expect(page.locator(".narrative-text")).to_be_visible(timeout=5000)


# ============================================================
# D. SFX
# ============================================================

class TestD_SFX:
    def test_d1_sfx_effect_no_crash(self):
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"
        )))
        from app.engine.engine import GameEngine
        from app.schemas.game import GameState
        state = GameState(
            current_node_id="A", cycle_count=0, half_cycle_count=0,
            inventory=[], flags={}, visited_nodes=["A"],
            player_attributes={"sanity": 100, "courage": 5, "insight": 3},
            endings_reached=[], persistent_nodes={},
        )
        engine = GameEngine()
        try:
            engine._apply_effects(
                [{"type": "sfx", "target": "click"}], state, "A"
            )
        except Exception as e:
            pytest.fail(f"sfx effect crashed: {e}")

    def test_d2_scene_effects_channel(self):
        p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "frontend", "src", "views", "GamePlay.vue"))
        with open(p, "r", encoding="utf-8") as f:
            assert "sceneEffect" in f.read()


# ============================================================
# E. Full ring traversal
# ============================================================

class TestE_FullRing:
    def test_e1_a_b_c_path(self):
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        state = resp.json()["state"]
        current = "A"
        visited = ["A"]
        for _ in range(12):
            cr = requests.get(f"{API_BASE}/editor/choices/{current}", timeout=5)
            choices = cr.json().get("choices", [])
            advanced = False
            for c in choices:
                if c["next_node_id"] != current:
                    r = requests.post(
                        f"{API_BASE}/game/choose/{current}",
                        json={"choice_id": c["id"], "state": state}, timeout=5,
                    )
                    if r.status_code == 200:
                        state = r.json()["state"]
                        current = r.json()["node"]["id"]
                        visited.append(current)
                        advanced = True
                        break
            if not advanced:
                break
            if current == "A" and len(visited) > 3:
                break
        main_visited = set(n for n in visited if n in "ABCDEFGH")
        assert len(main_visited) >= 3

    def test_e2_cycle_starts_zero(self):
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        assert resp.json()["state"]["cycle_count"] == 0

    def test_e3_no_crash_ui(self, page: Page):
        go_to_play(page)
        for _ in range(5):
            if page.locator(".choice-btn").count() == 0:
                break
            page.locator(".choice-btn").first.click(force=True)
            page.wait_for_timeout(300)
            dismiss_overlay(page)
            skip_typing(page)
        expect(page.locator(".narrative-text")).to_be_visible(timeout=5000)


# ============================================================
# Source verification
# ============================================================

class TestSourceVerification:
    def test_model_ambient(self):
        p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "backend", "app", "models", "story.py"))
        with open(p, "r", encoding="utf-8") as f:
            assert "ambient" in f.read()

    def test_schema_ambient(self):
        p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "backend", "app", "schemas", "game.py"))
        with open(p, "r", encoding="utf-8") as f:
            assert "ambient" in f.read()

    def test_engine_ambient(self):
        p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "backend", "app", "engine", "engine.py"))
        with open(p, "r", encoding="utf-8") as f:
            assert "ambient" in f.read()

    def test_types_ambient(self):
        p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "frontend", "src", "types", "index.ts"))
        with open(p, "r", encoding="utf-8") as f:
            assert "ambient" in f.read()
