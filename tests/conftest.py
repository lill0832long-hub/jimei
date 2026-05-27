"""
测试共享 fixtures 和工具函数
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nicegui import ui
from app.components.state import state
import pytest


def setup_logged_in():
    state.current_user = {"id": 1, "username": "admin", "role": "admin"}
    state.selected_ledger_id = 1
    state.selected_year = 2026
    state.selected_month = 5
    state.sidebar_group_expanded = {
        "work": True, "operations": True, "reports": True, "finance": True,
    }


def setup_logged_out():
    state.current_user = None
    state.selected_ledger_id = None


def render_page(page_key):
    from app.config import get_page_render
    setup_logged_in()
    state.current_page = page_key
    container = ui.column().classes("w-full")
    with container:
        render_fn = get_page_render(page_key)
        if render_fn:
            render_fn()
    return container


@pytest.fixture(scope="session")
def browser():
    from tests.test_browser_ui import Browser
    return Browser()


@pytest.fixture
def r():
    from tests.test_browser_ui import Result
    return Result()