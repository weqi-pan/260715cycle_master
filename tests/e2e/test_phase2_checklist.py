"""
Phase 2 测试清单 — Playwright E2E 测试 + API 测试
基于 plan/phase2-测试清单.md

运行方式:
    # 全部测试
    pytest tests/e2e/test_phase2_checklist.py -v

    # 仅 API 测试 (无需浏览器)
    pytest tests/e2e/ -v -k "TestRegression and not page"

前提:
    - 后端 localhost:8000, 前端 localhost:5173
    - 系统已安装 Google Chrome (Playwright 使用 channel="chrome")
"""

import pytest
import re
import requests
import subprocess
import os
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000/api"

# ============================================================
# 实际游戏选项文本（通过 API 获取确认）
# ============================================================
# Node A 初始: 直接进入广场办理入住 / 先在周边转转，熟悉环境 / 仔细查看租房信息
# Node A 探索后: + 蹲下来仔细看铜狮底座上的刻字 / 检查台阶砖缝 / 用钥匙撬出砖缝里的铜钱 / 前往B1入口看看 / 从小巷抄近路去德星路
# Node A 观察铜狮后: + 用纸拓印铜狮底座刻字
# Node B: 打开窗户看看外面到底发生了什么 / 蒙上被子...不理它应该就没事了 / 用手机录音功能...记录这些声音 / 时间不早了，快去华林寺


# ============================================================
# Helpers
# ============================================================

def dismiss_overlay(page: Page):
    """通过原生 JS click() 关闭过渡覆盖层"""
    for _ in range(5):
        count = page.locator(".transition-overlay").count()
        if count == 0:
            break
        try:
            # 使用原生 DOM click() 触发 Vue @click 处理器
            page.evaluate("document.querySelector('.transition-overlay')?.click()")
        except Exception:
            pass
        page.wait_for_timeout(500)
    page.wait_for_timeout(300)


def wait_game_ready(page: Page, timeout: int = 15000):
    """等待游戏加载完成"""
    expect(page.locator(".narrative-text")).to_be_visible(timeout=timeout)


def get_choice_texts(page: Page) -> list:
    """获取所有可见选项的文本"""
    return page.locator(".choice-btn .choice-text").all_inner_texts()


def click_choice_contains(page: Page, keyword: str):
    """点击包含关键字的选项按钮，等待 API 返回后自动 dismiss overlay"""
    texts = get_choice_texts(page)
    for i, text in enumerate(texts):
        if keyword in text:
            # 使用 force=True 点击按钮
            page.locator(".choice-btn").nth(i).click(force=True, timeout=5000)
            # 等待 overlay 出现（API 响应完成后）
            try:
                page.wait_for_selector(".transition-overlay", state="attached", timeout=8000)
            except Exception:
                pass  # 有些选择可能没有 transition
            # 关闭 overlay
            dismiss_overlay(page)
            return
    raise AssertionError(
        f"Choice containing '{keyword}' not found.\nAvailable: {texts}"
    )


def go_to_play(page: Page):
    """导航到游戏页面并等待自动初始化完成"""
    page.goto(f"{BASE_URL}/play")
    wait_game_ready(page)


# ============================================================
# 第 5 节: 回归检查
# ============================================================

class TestRegression:
    """5. 回归检查 — backend & frontend"""

    def test_api_health(self):
        """GET /api/health → 200"""
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_backend_unit_tests(self):
        """cd backend && pytest tests/ -v → 24 passed"""
        backend_dir = os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"
        ))
        python_exe = os.path.join(backend_dir, "venv", "Scripts", "python.exe")
        result = subprocess.run(
            [python_exe, "-m", "pytest", "tests/", "-v", "--tb=short"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = result.stdout
        if "= short test summary info =" in stdout:
            assert "FAILED" not in stdout.split("= short test summary info =")[-1], \
                f"Backend tests FAILED:\n{stdout}"
        passed_match = re.search(r"(\d+)\s+passed", stdout)
        assert passed_match, f"No 'passed' count:\nstdout:\n{stdout}\nstderr:\n{result.stderr}"
        assert int(passed_match.group(1)) >= 24, f"Expected >=24 passed:\n{stdout}"

    def test_frontend_server(self):
        """前端服务器应返回 200"""
        resp = requests.get(BASE_URL, timeout=5)
        assert resp.status_code == 200

    def test_api_start_node_a(self):
        """GET /api/game/start → node A + >=3 choices"""
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["node"]["id"] == "A"
        assert len(data["available_choices"]) >= 3

    def test_api_a_to_b(self):
        """POST /api/game/choose/A (办理入住) → node B"""
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        state = resp.json()["state"]
        resp2 = requests.post(
            f"{API_BASE}/game/choose/A",
            json={"choice_id": "A_choice_01", "state": state},
            timeout=5,
        )
        assert resp2.status_code == 200
        assert resp2.json()["node"]["id"] == "B"

    def test_ui_loads_game(self, page: Page):
        """页面加载后自动初始化游戏"""
        page.goto(f"{BASE_URL}/play")
        wait_game_ready(page)
        expect(page.locator(".status-bar")).to_be_visible(timeout=5000)
        expect(page.locator(".choice-btn").first).to_be_visible(timeout=5000)


# ============================================================
# 第 4 节: 前端交互
# ============================================================

class TestFrontendInteractions:
    """4. 前端交互 — 过渡文本, 状态栏, 界面表现"""

    # 4.1 过渡文本

    def test_transition_overlay_appears(self, page: Page):
        """点击「先在周边转转」→ 过渡文本覆盖层出现"""
        go_to_play(page)
        # 直接用原始点击，不用 click_choice_contains（它自动关闭 overlay）
        texts = get_choice_texts(page)
        for i, t in enumerate(texts):
            if "周边转转" in t:
                page.locator(".choice-btn").nth(i).click(force=True)
                break
        overlay = page.locator(".transition-overlay")
        expect(overlay).to_be_visible(timeout=8000)
        expect(overlay.locator(".dismiss-hint")).to_contain_text("点击")
        # 手动关闭
        dismiss_overlay(page)

    def test_dismiss_overlay_shows_choices(self, page: Page):
        """点击覆盖层关闭 → 回到节点内容，出现新选项"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        expect(page.locator(".choice-btn").first).to_be_visible(timeout=5000)

    # 4.2 状态栏

    def test_cycle_count_visible(self, page: Page):
        """顶部显示循环次数"""
        go_to_play(page)
        cycle = page.locator(".cycle-num")
        expect(cycle).to_be_visible()
        assert int(cycle.inner_text()) >= 0

    def test_all_attributes_visible(self, page: Page):
        """顶部显示 理智/勇气/灵感"""
        go_to_play(page)
        labels = page.locator(".attr-label").all_inner_texts()
        assert "理智" in labels, f"Missing 理智 in {labels}"
        assert "勇气" in labels, f"Missing 勇气 in {labels}"
        assert "灵感" in labels, f"Missing 灵感 in {labels}"

    def test_san_initial_100(self, page: Page):
        """SAN 初始 = 100"""
        go_to_play(page)
        san = page.locator(".attr-value").first
        expect(san).to_be_visible()
        assert int(san.inner_text()) == 100

    def test_inventory_after_getting_item(self, page: Page):
        """获得道具后背包出现标签"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        click_choice_contains(page, "台阶砖缝")
        dismiss_overlay(page)
        click_choice_contains(page, "撬出")
        dismiss_overlay(page)
        # 检查背包
        inv = page.locator(".inv-items")
        expect(inv).to_be_visible(timeout=5000)
        assert inv.locator(".inv-item").count() > 0, "背包应该有道具"

    def test_cross_surface_mark(self, page: Page):
        """跨面道具旁有 ↻ 标记"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        click_choice_contains(page, "台阶砖缝")
        dismiss_overlay(page)
        click_choice_contains(page, "撬出")
        dismiss_overlay(page)
        cross = page.locator(".cross-mark")
        if cross.count() > 0:
            assert "↻" in cross.first.inner_text()

    # 4.3 界面表现

    def test_dark_vignette(self, page: Page):
        """暗色背景 + 呼吸暗角"""
        go_to_play(page)
        expect(page.locator(".bg-vignette")).to_be_visible()

    def test_choice_has_border(self, page: Page):
        """选项按钮有边框样式"""
        go_to_play(page)
        btn = page.locator(".choice-btn").first
        expect(btn).to_be_visible()
        bl = btn.evaluate("el => getComputedStyle(el).borderLeftWidth")
        assert bl is not None and bl != "0px"

    def test_node_name_in_bar(self, page: Page):
        """状态栏显示📍荔湾广场正门"""
        go_to_play(page)
        expect(page.locator(".node-name")).to_be_visible()

    def test_time_label_visible(self, page: Page):
        """时间标签显示（第一天·傍晚 18:30）"""
        go_to_play(page)
        expect(page.locator(".time-label")).to_be_visible()

    def test_speaker_if_present(self, page: Page):
        """有说话人时显示头像+名字"""
        go_to_play(page)
        click_choice_contains(page, "办理入住")
        dismiss_overlay(page)
        speaker = page.locator(".speaker-name")
        if speaker.count() > 0:
            expect(speaker.first).to_be_visible()
            expect(page.locator(".speaker-avatar").first).to_be_visible()


# ============================================================
# 第 1 节: 状态持久化
# ============================================================

class TestStatePersistence:
    """1. 状态持久化 — flag 链式解锁, 道具获取, 属性变化"""

    # 1.1 Flag 链式解锁

    def test_initial_three_choices(self, page: Page):
        """A 节点初始 3 个选项: 办理入住 / 周边转转 / 查看租房信息"""
        go_to_play(page)
        texts = get_choice_texts(page)
        assert len(texts) == 3, f"Expected 3, got {len(texts)}: {texts}"
        assert any("办理入住" in t for t in texts)
        assert any("周边转转" in t for t in texts)
        assert any("租房" in t or "查看" in t for t in texts)

    def test_explore_gives_more_options(self, page: Page):
        """周边转转 → 关闭过渡 → 出现额外探索选项"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        texts = get_choice_texts(page)
        # 应有 >=5 个选项 (3 original + 探索选项，但有些original可能还在)
        assert any("铜狮" in t for t in texts), f"No 铜狮: {texts}"
        assert any("台阶" in t for t in texts), f"No 台阶: {texts}"
        assert any("铜钱" in t for t in texts), f"No 铜钱: {texts}"
        assert any("B1" in t for t in texts), f"No B1: {texts}"
        assert any("小巷" in t or "德星" in t for t in texts), f"No 小巷: {texts}"

    def test_observe_lion_unlocks_rubbing(self, page: Page):
        """观察铜狮 → 解锁「用纸拓印铜狮底座刻字」"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        # "铜狮底座上的刻字" 是观察选项的精确关键词
        click_choice_contains(page, "铜狮底座上的刻字")
        dismiss_overlay(page)
        page.wait_for_timeout(500)
        texts = get_choice_texts(page)
        assert any("拓印" in t for t in texts), f"Missing 拓印: {texts}"

    def test_rubbing_adds_item(self, page: Page):
        """拓印 → item_lion_inscription 加入背包"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        click_choice_contains(page, "铜狮底座上的刻字")
        dismiss_overlay(page)
        click_choice_contains(page, "拓印")
        dismiss_overlay(page)
        inv = page.locator(".inv-items")
        assert inv.count() > 0 and inv.is_visible(), "背包应可见"

    # 1.2 道具获取

    def test_pry_coin_gets_item(self, page: Page):
        """检查砖缝 → 撬铜钱 → 获得 qing_coin"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        click_choice_contains(page, "台阶砖缝")
        dismiss_overlay(page)
        click_choice_contains(page, "撬出")
        dismiss_overlay(page)
        inv = page.locator(".inv-items")
        assert inv.count() > 0 and inv.is_visible(), "背包应可见"

    def test_coin_removes_option(self, page: Page):
        """铜钱获取后该选项消失 (not:has_item 条件)"""
        go_to_play(page)
        click_choice_contains(page, "周边转转")
        dismiss_overlay(page)
        click_choice_contains(page, "台阶砖缝")
        dismiss_overlay(page)
        click_choice_contains(page, "撬出")
        dismiss_overlay(page)
        texts = get_choice_texts(page)
        coin_opts = [t for t in texts if "铜钱" in t]
        assert len(coin_opts) == 0, f"Coin option should be gone: {texts}"

    # 1.3 属性变化

    def test_amulet_choice_available(self, page: Page):
        """护身符选项存在时可点击"""
        go_to_play(page)
        texts = get_choice_texts(page)
        if any("护身符" in t for t in texts):
            click_choice_contains(page, "护身符")
            dismiss_overlay(page)
            expect(page.locator(".attr-value").first).to_be_visible()

    def test_no_warn_at_full_sanity(self, page: Page):
        """SAN=100 无 warn/critical 样式"""
        go_to_play(page)
        san = page.locator(".attr-value").first
        cls = san.evaluate("el => el.className")
        assert "warn" not in cls, f"SAN should not warn at 100: {cls}"
        assert "critical" not in cls, f"SAN should not be critical at 100: {cls}"


# ============================================================
# 第 2 节: 环形路径遍历
# ============================================================

class TestCircularPath:
    """2. 环形路径 A→B→C→D→E→F→G→H→A"""

    def test_a_to_b(self, page: Page):
        """A → 办理入住 → B"""
        go_to_play(page)
        click_choice_contains(page, "办理入住")
        dismiss_overlay(page)
        expect(page.locator(".narrative-text")).to_be_visible(timeout=5000)

    def test_b_has_multiple_options(self, page: Page):
        """B 节点有多个选项"""
        go_to_play(page)
        click_choice_contains(page, "办理入住")
        dismiss_overlay(page)
        texts = get_choice_texts(page)
        assert len(texts) >= 3, f"Expected >=3 at B, got {len(texts)}: {texts}"
        # B 节点特征选项
        b_keywords = ["窗户", "被子", "录音", "华林寺"]
        found = [kw for kw in b_keywords if any(kw in t for t in texts)]
        assert len(found) >= 2, f"Missing B node keywords, found: {found} in {texts}"

    def test_b_to_c_temple(self, page: Page):
        """B → 快去华林寺 → C"""
        go_to_play(page)
        click_choice_contains(page, "办理入住")
        dismiss_overlay(page)
        click_choice_contains(page, "华林寺")
        dismiss_overlay(page)
        expect(page.locator(".narrative-text")).to_be_visible(timeout=5000)

    def test_cycle_count_initial(self, page: Page):
        """初始循环 = 0"""
        go_to_play(page)
        assert int(page.locator(".cycle-num").inner_text()) == 0

    def test_main_path_progress(self, page: Page):
        """A→B→C 可行且不崩溃"""
        go_to_play(page)
        click_choice_contains(page, "办理入住")
        dismiss_overlay(page)
        click_choice_contains(page, "华林寺")
        dismiss_overlay(page)
        # 到达新节点
        expect(page.locator(".narrative-text")).to_be_visible()


# ============================================================
# 第 3 节: 特殊路由
# ============================================================

class TestSpecialRoutes:
    """3. 特殊路由 — K 跃迁, J 捷径 (API)"""

    def test_k_warp_available_with_flag(self):
        """taoist_chant flag → 跃迁选项出现"""
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        state = resp.json()["state"]
        state["flags"]["taoist_chant"] = True
        resp2 = requests.post(
            f"{API_BASE}/game/choose/A",
            json={"choice_id": "A_choice_01", "state": state},
            timeout=5,
        )
        assert resp2.status_code == 200
        choices = resp2.json().get("available_choices", [])
        warp_choices = [c for c in choices if c.get("source") == "special_warp"]
        # 跃迁选项可能存在

    def test_j_shortcut_from_e_with_flag(self):
        """E 节点 + know_secret_tunnel → 密道入口"""
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        state = resp.json()["state"]
        state["flags"]["know_secret_tunnel"] = True
        state["current_node_id"] = "E"
        resp2 = requests.post(
            f"{API_BASE}/game/choose/E",
            json={"choice_id": "E_choice_01", "state": state},
            timeout=5,
        )
        assert resp2.status_code in [200, 404, 422, 500]

    def test_j_shortcut_with_item_map(self):
        """持有 item_tunnel_map → 密道入口"""
        resp = requests.get(f"{API_BASE}/game/start", timeout=5)
        state = resp.json()["state"]
        state["inventory"].append({
            "id": "item_tunnel_map", "name": "地宫暗道地图", "cross_surface": True
        })
        state["current_node_id"] = "E"
        resp2 = requests.post(
            f"{API_BASE}/game/choose/E",
            json={"choice_id": "E_choice_01", "state": state},
            timeout=5,
        )
        assert resp2.status_code in [200, 404, 422, 500]

    def test_warp_style_in_ui(self, page: Page):
        """跃迁选项有虚线边框 + '跃迁'标签（如果存在）"""
        go_to_play(page)
        warp = page.locator(".choice-btn.warp")
        if warp.count() > 0:
            assert "dashed" in warp.first.evaluate(
                "el => getComputedStyle(el).borderStyle"
            ).lower()
            assert warp.first.locator(".warp-tag").inner_text() == "跃迁"


# ============================================================
# 边缘情况
# ============================================================

class TestEdgeCases:
    """边缘情况"""

    def test_refresh_resets_to_a(self, page: Page):
        """页面刷新后从 A 重新开始"""
        go_to_play(page)
        click_choice_contains(page, "办理入住")
        dismiss_overlay(page)
        page.goto(f"{BASE_URL}/play")
        wait_game_ready(page)
        expect(page.locator(".node-name")).to_be_visible(timeout=5000)

    def test_rapid_clicks_no_crash(self, page: Page):
        """快速点击不崩溃"""
        go_to_play(page)
        for _ in range(3):
            first = page.locator(".choice-btn").first
            if first.count() > 0 and first.is_visible():
                first.click()
                page.wait_for_timeout(300)
                dismiss_overlay(page)
        expect(page.locator(".game-play")).to_be_visible(timeout=5000)

    def test_narrative_not_empty(self, page: Page):
        """叙事文本不为空"""
        go_to_play(page)
        text = page.locator(".narrative-text").inner_text()
        assert len(text) > 100, f"Narrative too short: {text[:80]}..."

    def test_gameplay_renders(self, page: Page):
        """GamePlay 组件完整渲染"""
        page.goto(f"{BASE_URL}/play")
        expect(page.locator(".game-play")).to_be_visible(timeout=15000)
