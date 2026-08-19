"""Suite-wide test fixtures.

test_mcp_toolkit.py drives real MCP dispatch through `mcp.client.Client`,
which routes each tool call's synchronous Django ORM work through
`sync_to_async` onto its own dedicated worker thread rather than the test's
own thread. pytest-django's `db` fixture isolates each test by wrapping it in
an outer atomic transaction on *its* thread's connection and rolling that
back afterwards -- but the worker thread opens a separate, thread-local
connection that was never part of that transaction, so writes made through
it commit for real and survive into later tests (e.g. Printer rows from
test_mcp_toolkit.py leaking into test_resolve_printer_device.py's counts).

This fixture flushes bambu_run's Printer table after each test in that file
specifically, restoring isolation without touching the test file itself
(which mirrors mcp-gate's proven end-to-end test pattern verbatim).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_async_mcp_dispatch_writes(request, django_db_blocker):
    yield
    if request.node.module.__name__ != "tests.test_mcp_toolkit":
        return
    with django_db_blocker.unblock():
        from bambu_run.models import Printer

        Printer.objects.all().delete()
