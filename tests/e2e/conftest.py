"""使用 Playwright 隔离 Chromium 的 E2E 配置。"""

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {"headless": True}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """覆盖浏览器上下文参数"""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
        "locale": "zh-CN",
    }
