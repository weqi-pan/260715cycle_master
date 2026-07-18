"""
Pytest 配置 — 使用系统 Chrome 浏览器进行测试
"""

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """使用系统 Chrome 浏览器（跳过 Playwright 浏览器下载）"""
    return {
        "channel": "chrome",
        "headless": False,
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """覆盖浏览器上下文参数"""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
        "locale": "zh-CN",
    }
