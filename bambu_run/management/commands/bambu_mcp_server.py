"""
Management command to run the Bambu-Run MCP server.

Supports SSE (network) and stdio (local) transports.

Usage:
    python manage.py bambu_mcp_server
    python manage.py bambu_mcp_server --transport sse --host 0.0.0.0 --port 8808
    python manage.py bambu_mcp_server --transport stdio
"""

import logging

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger("bambu_run.mcp")


class Command(BaseCommand):
    help = "Run the Bambu-Run MCP server for AI agent access"

    def add_arguments(self, parser):
        from bambu_run.conf import app_settings

        parser.add_argument(
            "--transport",
            choices=["sse", "stdio"],
            default="sse",
            help="Transport mode (default: sse)",
        )
        parser.add_argument(
            "--host",
            default=app_settings.MCP_HOST,
            help=f"Host to bind to (default: {app_settings.MCP_HOST})",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=app_settings.MCP_PORT,
            help=f"Port to listen on (default: {app_settings.MCP_PORT})",
        )

    def handle(self, *args, **options):
        try:
            from mcp.server.fastmcp import FastMCP
        except ImportError:
            raise CommandError(
                "The 'mcp' package is required. Install it with: pip install 'bambu-run[mcp]'"
            )

        from asgiref.sync import sync_to_async
        from bambu_run.conf import app_settings
        from bambu_run import mcp_tools

        transport = options["transport"]
        host = options["host"]
        port = options["port"]

        mcp = FastMCP(
            "Bambu-Run",
            instructions=(
                "Bambu-Run MCP server provides read-only access to 3D printer data "
                "including live printer status, filament inventory, print history, "
                "temperature trends, and diagnostics. All data comes from Bambu Lab "
                "printers monitored via MQTT."
            ),
        )

        # ── Register Tools ───────────────────────────────────────────────

        @mcp.tool()
        async def get_printer_status(printer_id: int | None = None) -> str:
            """Get current live status of printer(s) including temperatures, progress, AMS slots, and errors.

            Args:
                printer_id: Optional printer ID to filter. Omit for all printers.
            """
            return await sync_to_async(mcp_tools.get_printer_status)(printer_id=printer_id)

        @mcp.tool()
        async def list_printers() -> str:
            """List all registered printers with their model, serial, IP, and active status."""
            return await sync_to_async(mcp_tools.list_printers)()

        @mcp.tool()
        async def get_print_history(
            status: str | None = None,
            days: int | None = None,
            project_name: str | None = None,
            limit: int = 20,
        ) -> str:
            """Get print job history with optional filters.

            Args:
                status: Filter by status (FINISH, FAILED, CANCELLED).
                days: Only show jobs from the last N days.
                project_name: Filter by project name (partial match).
                limit: Maximum number of results (default 20).
            """
            return await sync_to_async(mcp_tools.get_print_history)(
                status=status, days=days, project_name=project_name, limit=limit
            )

        @mcp.tool()
        async def get_print_job_detail(job_id: int) -> str:
            """Get detailed information about a single print job including filament usage.

            Args:
                job_id: The print job ID.
            """
            return await sync_to_async(mcp_tools.get_print_job_detail)(job_id=job_id)

        @mcp.tool()
        async def list_filaments(
            type: str | None = None,
            brand: str | None = None,
            color: str | None = None,
            loaded_in_ams: bool | None = None,
            low_filament: bool | None = None,
        ) -> str:
            """List filament inventory with optional filters.

            Args:
                type: Filter by material type (PLA, PETG, ABS, etc.).
                brand: Filter by brand name (partial match).
                color: Filter by color name (partial match).
                loaded_in_ams: Filter by whether spool is currently in AMS.
                low_filament: If true, only show spools with <=20% remaining.
            """
            return await sync_to_async(mcp_tools.list_filaments)(
                type=type, brand=brand, color=color,
                loaded_in_ams=loaded_in_ams, low_filament=low_filament,
            )

        @mcp.tool()
        async def get_filament_detail(filament_id: int) -> str:
            """Get detailed information about a single filament spool including usage history.

            Args:
                filament_id: The filament spool ID.
            """
            return await sync_to_async(mcp_tools.get_filament_detail)(filament_id=filament_id)

        @mcp.tool()
        async def get_temperature_history(
            printer_id: int | None = None,
            hours: int = 6,
            metric: str = "all",
        ) -> str:
            """Get temperature trends (avg/min/max) over recent hours.

            Args:
                printer_id: Optional printer ID to filter.
                hours: Number of hours to look back (default 6).
                metric: Which sensor to show: 'all', 'nozzle', 'bed', or 'chamber'.
            """
            return await sync_to_async(mcp_tools.get_temperature_history)(
                printer_id=printer_id, hours=hours, metric=metric
            )

        @mcp.tool()
        async def get_filament_usage_stats(days: int = 30, group_by: str = "type") -> str:
            """Get aggregate filament consumption statistics.

            Args:
                days: Number of days to look back (default 30).
                group_by: Group results by 'type', 'color', or 'spool'.
            """
            return await sync_to_async(mcp_tools.get_filament_usage_stats)(days=days, group_by=group_by)

        @mcp.tool()
        async def get_printer_health(printer_id: int | None = None) -> str:
            """Get printer diagnostics including errors, humidity, WiFi signal, and recent failures.

            Args:
                printer_id: Optional printer ID to filter. Omit for all printers.
            """
            return await sync_to_async(mcp_tools.get_printer_health)(printer_id=printer_id)

        @mcp.tool()
        async def search_print_jobs(query: str) -> str:
            """Search print jobs by project name or gcode filename.

            Args:
                query: Search text (partial match on project name or gcode file).
            """
            return await sync_to_async(mcp_tools.search_print_jobs)(query=query)

        @mcp.tool()
        async def get_printing_summary(days: int = 7) -> str:
            """Get high-level printing activity summary including job counts, success rate, and top projects.

            Args:
                days: Number of days to summarize (default 7).
            """
            return await sync_to_async(mcp_tools.get_printing_summary)(days=days)

        @mcp.tool()
        async def find_compatible_filament(
            type: str,
            min_remaining_percent: int = 10,
            color: str | None = None,
        ) -> str:
            """Find filament spools matching material type and optional criteria.

            Args:
                type: Material type to search for (PLA, PETG, ABS, etc.).
                min_remaining_percent: Minimum remaining percentage (default 10).
                color: Optional color filter (partial match).
            """
            return await sync_to_async(mcp_tools.find_compatible_filament)(
                type=type, min_remaining_percent=min_remaining_percent, color=color
            )

        # ── Register Resources ───────────────────────────────────────────

        @mcp.resource("bambu://printers")
        async def res_printers() -> str:
            """List all registered printers."""
            return await sync_to_async(mcp_tools.resource_printers)()

        @mcp.resource("bambu://printers/{printer_id}/status")
        async def res_printer_status(printer_id: int) -> str:
            """Get latest status for a specific printer."""
            return await sync_to_async(mcp_tools.resource_printer_status)(printer_id)

        @mcp.resource("bambu://filaments")
        async def res_filaments() -> str:
            """Full filament inventory."""
            return await sync_to_async(mcp_tools.resource_filaments)()

        @mcp.resource("bambu://filaments/{filament_id}")
        async def res_filament_detail(filament_id: int) -> str:
            """Single filament spool with usage history."""
            return await sync_to_async(mcp_tools.resource_filament_detail)(filament_id)

        @mcp.resource("bambu://print-jobs/recent")
        async def res_recent_jobs() -> str:
            """Last 20 print jobs."""
            return await sync_to_async(mcp_tools.resource_recent_print_jobs)()

        @mcp.resource("bambu://filament-types")
        async def res_filament_types() -> str:
            """Filament type registry."""
            return await sync_to_async(mcp_tools.resource_filament_types)()

        @mcp.resource("bambu://filament-colors")
        async def res_filament_colors() -> str:
            """Filament color database."""
            return await sync_to_async(mcp_tools.resource_filament_colors)()

        # ── Register Prompts ─────────────────────────────────────────────

        @mcp.prompt()
        async def printer_check_in(printer_id: int | None = None) -> str:
            """Full printer status briefing with health check and recent prints.

            Args:
                printer_id: Optional printer ID. Omit for all printers.
            """
            return await sync_to_async(mcp_tools.prompt_printer_check_in)(printer_id=printer_id)

        @mcp.prompt()
        async def filament_inventory_report() -> str:
            """Comprehensive filament inventory report with low-stock warnings."""
            return await sync_to_async(mcp_tools.prompt_filament_inventory_report)()

        @mcp.prompt()
        async def print_job_review(job_id: int) -> str:
            """Detailed review of a completed print job.

            Args:
                job_id: The print job ID to review.
            """
            return await sync_to_async(mcp_tools.prompt_print_job_review)(job_id)

        @mcp.prompt()
        async def weekly_printing_digest() -> str:
            """Weekly printing activity summary with filament usage breakdown."""
            return await sync_to_async(mcp_tools.prompt_weekly_digest)()

        @mcp.prompt()
        async def troubleshoot_printer(printer_id: int | None = None) -> str:
            """Diagnose printer issues using recent health data, status, and temperatures.

            Args:
                printer_id: Optional printer ID. Omit for all printers.
            """
            return await sync_to_async(mcp_tools.prompt_troubleshoot_printer)(printer_id=printer_id)

        # ── Auth middleware for SSE ───────────────────────────────────────

        api_key = app_settings.MCP_API_KEY
        auth_backend = app_settings.MCP_AUTH_BACKEND

        if api_key or auth_backend:
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.responses import JSONResponse

            class AuthMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request, call_next):
                    # Custom auth backend takes priority
                    if auth_backend:
                        if not auth_backend(request):
                            return JSONResponse(
                                {"error": "Unauthorized"}, status_code=401
                            )
                        return await call_next(request)

                    # API key auth
                    if api_key:
                        auth_header = request.headers.get("Authorization", "")
                        if auth_header == f"Bearer {api_key}":
                            return await call_next(request)
                        return JSONResponse(
                            {"error": "Invalid or missing API key"}, status_code=401
                        )

                    return await call_next(request)

            # Attach middleware — FastMCP's SSE app is a Starlette app
            original_sse_app = mcp.sse_app

            def patched_sse_app():
                app = original_sse_app()
                app.add_middleware(AuthMiddleware)
                return app

            mcp.sse_app = patched_sse_app

        # ── Run ──────────────────────────────────────────────────────────

        if transport == "sse":
            try:
                import uvicorn
            except ImportError:
                raise CommandError(
                    "uvicorn is required for SSE transport. Install it with: pip install uvicorn"
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting Bambu-Run MCP server (SSE) on {host}:{port}"
                )
            )
            self.stdout.write(
                f"Connect with: http://{host}:{port}/sse"
            )
            app = mcp.sse_app()
            uvicorn.run(app, host=host, port=port)
        else:
            self.stdout.write(
                self.style.SUCCESS("Starting Bambu-Run MCP server (stdio)")
            )
            mcp.run(transport="stdio")
