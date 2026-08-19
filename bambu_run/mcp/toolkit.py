"""Assembles the 8-tool bambu_run MCP toolkit, capability-tagged per the spec."""
from __future__ import annotations

from mcp_gate import Toolkit

from bambu_run.mcp.filaments import get_filament, list_filaments
from bambu_run.mcp.jobs import get_print_job, get_print_statistics, list_print_jobs
from bambu_run.mcp.status import get_hardware_health, get_metrics_history, get_printer_status


def build_toolkit() -> Toolkit:
    """Build the bambu_run MCP toolkit: 8 tools across read_printer,
    read_print_history, and read_filament.

    Called fresh by each entry point rather than shared as a module-level
    singleton, so tests (and multiple concurrent Gates, if ever needed) get
    an isolated Toolkit instance rather than sharing registration state.
    """
    kit = Toolkit("bambu_run")
    kit.tool(requires="read_printer")(get_printer_status)
    kit.tool(requires="read_printer")(get_metrics_history)
    kit.tool(requires="read_printer")(get_hardware_health)
    kit.tool(requires="read_print_history")(list_print_jobs)
    kit.tool(requires="read_print_history")(get_print_job)
    kit.tool(requires="read_print_history")(get_print_statistics)
    kit.tool(requires="read_filament")(list_filaments)
    kit.tool(requires="read_filament")(get_filament)
    return kit
