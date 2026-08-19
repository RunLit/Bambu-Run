import pytest
from mcp_gate import OpenIdentity, StaticTokenIdentity

from bambu_run.management.commands.bambu_mcp_server import ALL_CAPABILITIES, _build_gate
from bambu_run.mcp.toolkit import build_toolkit


def test_build_gate_stdio_uses_open_identity_with_all_capabilities():
    gate = _build_gate(build_toolkit(), transport="stdio")
    assert isinstance(gate.identity, OpenIdentity)


def test_build_gate_http_requires_api_key():
    with pytest.raises(ValueError, match="BAMBU_RUN_MCP_API_KEY"):
        _build_gate(build_toolkit(), transport="http", api_key=None)


def test_build_gate_http_with_key_uses_static_token_identity():
    gate = _build_gate(build_toolkit(), transport="http", api_key="secret123")
    assert isinstance(gate.identity, StaticTokenIdentity)


def test_all_capabilities_matches_the_three_spec_capabilities():
    assert set(ALL_CAPABILITIES) == {"read_printer", "read_print_history", "read_filament"}
