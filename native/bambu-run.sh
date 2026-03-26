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
        echo "Usage: $0 {start|stop|restart|status|logs|update}"
        echo
        echo "  start    Start web + collector services"
        echo "  stop     Stop web + collector services"
        echo "  restart  Restart web + collector services"
        echo "  status   Show service status"
        echo "  logs     Tail live logs (Ctrl+C to stop)"
        echo "  update   Pull latest code, install deps, migrate, restart"
        ;;
esac
