"""Run the Bambu-Run MCP server (standalone, single-owner).

Usage:
    python manage.py bambu_mcp_server --transport stdio
    python manage.py bambu_mcp_server --transport http --host 0.0.0.0 --port 8808
    python manage.py bambu_mcp_server --transport http --allowed-host mcp.example.com
"""
import logging

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger("bambu_run.mcp")

ALL_CAPABILITIES = ["read_printer", "read_print_history", "read_filament"]

_INSTRUCTIONS = (
    "Read-only access to Bambu Lab 3D printer data: live status, print "
    "history, and filament inventory, collected via MQTT."
)


def _build_gate(kit, transport, api_key=None):
    """Build the Gate for the requested transport.

    Raises ValueError if HTTP is requested without an api_key -- an
    unauthenticated network MCP endpoint would expose printer and filament
    data to anyone who can reach the port. stdio always uses OpenIdentity:
    the OS process boundary is the trust boundary there, matching mcp-gate's
    own guidance (never use OpenIdentity over HTTP).
    """
    from mcp_gate import Gate, OpenIdentity, StaticTokenIdentity

    if transport == "stdio":
        return Gate(name="bambu-run", toolkits=[kit], identity=OpenIdentity(ALL_CAPABILITIES), instructions=_INSTRUCTIONS)

    if not api_key:
        raise ValueError(
            "BAMBU_RUN_MCP_API_KEY must be set to serve MCP over HTTP -- an "
            "unauthenticated network MCP endpoint would expose printer and "
            "filament data to anyone who can reach the port."
        )
    return Gate(
        name="bambu-run",
        toolkits=[kit],
        identity=StaticTokenIdentity({api_key: ("owner", ALL_CAPABILITIES)}),
        instructions=_INSTRUCTIONS,
    )


class Command(BaseCommand):
    help = "Run the Bambu-Run MCP server for AI agent access (standalone, single-owner)"

    def add_arguments(self, parser):
        from bambu_run.conf import app_settings

        parser.add_argument("--transport", choices=["http", "stdio"], default="stdio")
        parser.add_argument("--host", default=app_settings.MCP_HOST)
        parser.add_argument("--port", type=int, default=app_settings.MCP_PORT)
        parser.add_argument(
            "--allowed-host",
            action="append",
            default=None,
            help=(
                "Host header this server should accept (repeatable). Required "
                "when reachable via a real domain or reverse proxy, e.g. "
                "--allowed-host mcp.example.com. Omit for local-only testing "
                "on 127.0.0.1/localhost."
            ),
        )

    def handle(self, *args, **options):
        try:
            from mcp_gate import run_stdio, asgi_app
        except ImportError:
            raise CommandError(
                "The 'mcp-gate' package is required. Install it with: pip install 'bambu-run[mcp]'"
            )

        from bambu_run.conf import app_settings
        from bambu_run.mcp.toolkit import build_toolkit

        transport = options["transport"]
        kit = build_toolkit()

        if transport == "stdio":
            gate = _build_gate(kit, transport="stdio")
            self.stdout.write(self.style.SUCCESS("Starting Bambu-Run MCP server (stdio)"))
            run_stdio(gate)
            return

        try:
            gate = _build_gate(kit, transport="http", api_key=app_settings.MCP_API_KEY)
        except ValueError as exc:
            raise CommandError(str(exc))

        try:
            import uvicorn
        except ImportError:
            raise CommandError("uvicorn is required for HTTP transport. Install it with: pip install uvicorn")

        asgi_kwargs = {}
        if options["allowed_host"]:
            from mcp.server.transport_security import TransportSecuritySettings
            asgi_kwargs["transport_security"] = TransportSecuritySettings(allowed_hosts=options["allowed_host"])

        app = asgi_app(gate, **asgi_kwargs)
        host, port = options["host"], options["port"]
        self.stdout.write(self.style.SUCCESS(f"Starting Bambu-Run MCP server (HTTP) on {host}:{port}"))
        self.stdout.write(f"Connect with: http://{host}:{port}/mcp  (Authorization: Bearer <key>)")
        uvicorn.run(app, host=host, port=port)
