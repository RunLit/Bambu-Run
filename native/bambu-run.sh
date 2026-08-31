#!/usr/bin/env bash
# Bambu-Run convenience wrapper
# Usage: ./native/bambu-run.sh {start|stop|restart|status|logs|update}
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
MANAGE="$VENV_DIR/bin/python $REPO_DIR/standalone/manage.py"
SERVICES="bambu-run-web.service bambu-run-collector.service"

# Include MCP service if installed
SERVICE_DIR="$HOME/.config/systemd/user"
if [ -f "$SERVICE_DIR/bambu-run-mcp.service" ]; then
    SERVICES="$SERVICES bambu-run-mcp.service"
fi

case "${1:-help}" in
    start)
        systemctl --user start $SERVICES
        echo "Bambu-Run started."
        ;;
    stop)
        systemctl --user stop $SERVICES
        echo "Bambu-Run stopped."
        ;;
    restart)
        systemctl --user restart $SERVICES
        echo "Bambu-Run restarted."
        ;;
    status)
        systemctl --user status $SERVICES --no-pager
        ;;
    logs)
        JOURNAL_UNITS="-u bambu-run-web -u bambu-run-collector"
        if [ -f "$SERVICE_DIR/bambu-run-mcp.service" ]; then
            JOURNAL_UNITS="$JOURNAL_UNITS -u bambu-run-mcp"
        fi
        journalctl --user $JOURNAL_UNITS -f --no-hostname
        ;;
    enable-mcp)
        if [ -f "$SERVICE_DIR/bambu-run-mcp.service" ]; then
            echo "MCP server already enabled."
        else
            echo "Installing MCP dependencies..."
            "$VENV_DIR/bin/pip" install --quiet ".[mcp]"

            sed "s|{{REPO_DIR}}|$REPO_DIR|g; s|{{VENV_DIR}}|$VENV_DIR|g" \
                "$REPO_DIR/native/bambu-run-mcp.service" > "$SERVICE_DIR/bambu-run-mcp.service"

            systemctl --user daemon-reload
            systemctl --user enable bambu-run-mcp.service
            systemctl --user start bambu-run-mcp.service

            PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
            echo "MCP server enabled on port 8808."
            echo
            echo "  Claude Desktop config:"
            echo "    {\"mcpServers\":{\"bambu-run\":{\"url\":\"http://${PI_IP:-localhost}:8808/sse\"}}}"
        fi
        ;;
    disable-mcp)
        if [ ! -f "$SERVICE_DIR/bambu-run-mcp.service" ]; then
            echo "MCP server is not enabled."
        else
            systemctl --user stop bambu-run-mcp.service 2>/dev/null || true
            systemctl --user disable bambu-run-mcp.service 2>/dev/null || true
            rm -f "$SERVICE_DIR/bambu-run-mcp.service"
            systemctl --user daemon-reload
            echo "MCP server disabled."
        fi
        ;;
    update)
        echo "Pulling latest code..."
        cd "$REPO_DIR" && git pull

        echo "Installing dependencies..."
        EXTRAS="standalone"
        if [ -f "$SERVICE_DIR/bambu-run-mcp.service" ]; then
            EXTRAS="standalone,mcp"
        fi
        "$VENV_DIR/bin/pip" install --quiet ".[$EXTRAS]"

        echo "Running migrations..."
        $MANAGE migrate --noinput

        echo "Collecting static files..."
        $MANAGE collectstatic --noinput --clear 2>/dev/null

        echo "Restarting services..."
        systemctl --user restart $SERVICES

        echo "Update complete."
        ;;
    help|*)
        echo "Usage: $0 {start|stop|restart|status|logs|update|enable-mcp|disable-mcp}"
        echo
        echo "  start        Start web + collector services"
        echo "  stop         Stop web + collector services"
        echo "  restart      Restart web + collector services"
        echo "  status       Show service status"
        echo "  logs         Tail live logs (Ctrl+C to stop)"
        echo "  update       Pull latest code, install deps, migrate, restart"
        echo "  enable-mcp   Install and start the MCP server for AI agent access"
        echo "  disable-mcp  Stop and remove the MCP server service"
        ;;
esac
