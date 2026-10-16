"""Structural tests for EWM domain tools."""
from __future__ import annotations

import pytest


EXPECTED_TOOL_NAMES = {
    "ewm_read_transport_unit",
    "ewm_read_inbound_delivery",
    "ewm_post_goods_receipt",
    "ewm_create_putaway_tasks",
    "ewm_validate_scan",
    "ewm_confirm_warehouse_task",
    "ewm_analyse_exception",
    "ewm_execute_exception_resolution",
    "ewm_escalate",
}


@pytest.fixture
def tools_module(add_agent_to_path):
    import importlib
    return importlib.import_module("tools")


def test_all_tools_exported(tools_module):
    """ALL_TOOLS must contain exactly the 9 expected EWM tools."""
    names = {t.name for t in tools_module.ALL_TOOLS}
    assert names == EXPECTED_TOOL_NAMES


def test_all_tools_have_descriptions(tools_module):
    """Every tool must have a non-empty description."""
    for tool in tools_module.ALL_TOOLS:
        assert tool.description, f"Tool '{tool.name}' has no description"


def test_all_tools_are_async(tools_module):
    """Every tool coroutine must be awaitable (async)."""
    import inspect

    for tool in tools_module.ALL_TOOLS:
        fn = tool.coroutine or tool.func
        assert fn is not None, f"Tool '{tool.name}' has no callable"
        assert inspect.iscoroutinefunction(fn), f"Tool '{tool.name}' is not async"
