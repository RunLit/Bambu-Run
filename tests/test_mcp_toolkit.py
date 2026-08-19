"""Proves this toolkit's capability assignments are wired correctly through
real MCP dispatch -- not by calling tool functions directly. See
~/src/mcp-gate/tests/test_end_to_end.py for the pattern this is modeled on;
mcp-gate's own HTTP-shaped dispatch machinery is already tested there, so
this file only needs the stdio-shaped Client, which is enough to drive
server.middleware and prove which tools this toolkit's capability tags
actually gate.
"""
import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from mcp_gate import Gate, OpenIdentity

from bambu_run.mcp.toolkit import build_toolkit
from bambu_run.models import Printer

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_full_capability_caller_sees_all_eight_tools(db):
    Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    gate = Gate(
        name="test",
        toolkits=[build_toolkit()],
        identity=OpenIdentity(["read_printer", "read_print_history", "read_filament"]),
    )
    server = gate.build_server()

    async with Client(server, mode="legacy") as client:
        result = await client.list_tools()

    names = {t.name for t in result.tools}
    assert names == {
        "get_printer_status", "get_metrics_history", "get_hardware_health",
        "list_print_jobs", "get_print_job", "get_print_statistics",
        "list_filaments", "get_filament",
    }


async def test_read_printer_only_caller_cannot_see_or_call_filament_tool(db):
    Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    gate = Gate(
        name="test",
        toolkits=[build_toolkit()],
        identity=OpenIdentity(["read_printer"]),
    )
    server = gate.build_server()

    async with Client(server, mode="legacy") as client:
        visible = await client.list_tools()
        visible_names = {t.name for t in visible.tools}
        assert "list_filaments" not in visible_names
        assert "list_print_jobs" not in visible_names
        assert "get_printer_status" in visible_names

        with pytest.raises(MCPError):
            await client.call_tool("list_filaments", {})


async def test_read_printer_caller_can_call_get_printer_status(db):
    Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    gate = Gate(
        name="test",
        toolkits=[build_toolkit()],
        identity=OpenIdentity(["read_printer"]),
    )
    server = gate.build_server()

    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("get_printer_status", {})
        assert result is not None


def test_build_toolkit_has_no_name_collisions():
    # Toolkit.tool() raises ValueError on a name collision at registration
    # time -- building it twice without raising is itself the assertion.
    build_toolkit()
    build_toolkit()
