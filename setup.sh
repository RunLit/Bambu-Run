#!/usr/bin/env bash
# Bambu-Run Native Setup — single entry point for Raspberry Pi (or any Linux)
# Usage: git clone ... && cd Bambu-Run && bash setup.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
ENV_FILE="$REPO_DIR/.env"
MANAGE="$VENV_DIR/bin/python $REPO_DIR/standalone/manage.py"
SERVICE_DIR="$HOME/.config/systemd/user"

green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[1;31m%s\033[0m\n' "$*"; }

# ── 1. Pre-flight checks ─────────────────────────────────────────────────────

green "=== Bambu-Run Native Setup ==="
echo

# Acquire sudo upfront and keep it alive for the duration of the script
echo "This script needs sudo for iptables (port redirect) and apt (dependencies)."
sudo -v
while true; do sudo -n true; sleep 50; kill -0 "$$" || exit; done 2>/dev/null &
SUDO_KEEPALIVE_PID=$!
trap 'kill "$SUDO_KEEPALIVE_PID" 2>/dev/null' EXIT
echo

# Python >= 3.10
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major=${ver%%.*}
        minor=${ver##*.}
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    red "Error: Python >= 3.10 is required."
    echo "Install it with: sudo apt install python3"
    exit 1
fi
green "Found $PYTHON ($ver)"

# Ensure python3-venv is available
if ! "$PYTHON" -m venv --help &>/dev/null; then
    yellow "Installing python3-venv..."
    sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv
fi

# Detect RAM for gunicorn worker count
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
if [ "$TOTAL_RAM_KB" -lt 1048576 ]; then
    WORKERS=1
else
    WORKERS=2
fi

# Prompt for access port
while true; do
    read -rp "Choose Bambu-Run Dashboard access port (Default: 80): " ACCESS_PORT
    ACCESS_PORT="${ACCESS_PORT:-80}"
    if [[ "$ACCESS_PORT" =~ ^[0-9]+$ ]] && [ "$ACCESS_PORT" -ge 1 ] && [ "$ACCESS_PORT" -le 65535 ]; then
        break
    else
        red "Invalid port '$ACCESS_PORT'. Please enter a number between 1 and 65535."
    fi
done
green "Dashboard will be accessible on port $ACCESS_PORT."

# ── 2. Venv + install ────────────────────────────────────────────────────────

if [ ! -d "$VENV_DIR" ]; then
    green "Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
else
    yellow "Virtual environment already exists, reusing."
fi

green "Installing dependencies..."

# Stub opencv-python (same trick as Dockerfile — avoids hour-long ARM build)
"$VENV_DIR/bin/python" -c "
import site, pathlib
d = pathlib.Path(site.getsitepackages()[0]) / 'opencv_python-4.99.0.dist-info'
if not d.exists():
    d.mkdir()
    (d / 'METADATA').write_text('Metadata-Version: 2.1\nName: opencv-python\nVersion: 4.99.0\n')
    (d / 'INSTALLER').write_text('pip\n')
    (d / 'RECORD').write_text('')
    print('  opencv stub created')
else:
    print('  opencv stub already exists')
"

"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet ".[standalone]"

# ── 3. Interactive .env ───────────────────────────────────────────────────────

if [ ! -f "$ENV_FILE" ]; then
    green "Setting up .env configuration..."
    echo

    read -rp "Bambu Lab email: " BAMBU_USERNAME
    read -rsp "Bambu Lab password: " BAMBU_PASSWORD
    echo
    while true; do
        read -rp "Timezone [UTC] (e.g. America/Sydney): " TIMEZONE
        TIMEZONE="${TIMEZONE:-UTC}"
        if "$VENV_DIR/bin/python" -c "import zoneinfo; zoneinfo.ZoneInfo('$TIMEZONE')" 2>/dev/null; then
            break
        else
            red "Unknown timezone '$TIMEZONE'. Find yours at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        fi
    done

    # Generate a random Django secret key
    DJANGO_SECRET_KEY=$("$VENV_DIR/bin/python" -c "import secrets; print(secrets.token_urlsafe(50))")

    cat > "$ENV_FILE" <<EOF
BAMBU_USERNAME=$BAMBU_USERNAME
BAMBU_PASSWORD=$BAMBU_PASSWORD
TIMEZONE=$TIMEZONE
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DEBUG=False
EOF
    green ".env created."
else
    yellow ".env already exists, skipping."
fi

# ── 4. Migrate ────────────────────────────────────────────────────────────────

green "Running database migrations..."
$MANAGE migrate --noinput

# ── 5. Bambu authentication ──────────────────────────────────────────────────

if ! grep -q '^BAMBU_TOKEN=' "$ENV_FILE" 2>/dev/null; then
    green "Authenticating with Bambu Lab (email verification required)..."
    echo "A verification code will be sent to your email."
    echo

    # Run collector in --once mode for interactive auth
    $MANAGE bambu_collector --once || true

    echo
    read -rp "Paste your BAMBU_TOKEN from above (or press Enter to skip): " TOKEN
    if [ -n "$TOKEN" ]; then
        echo "BAMBU_TOKEN=$TOKEN" >> "$ENV_FILE"
        green "Token saved to .env."
    else
        yellow "Skipped — you can add BAMBU_TOKEN to .env later."
    fi
else
    yellow "BAMBU_TOKEN already in .env, skipping auth."
fi

# ── 6. Superuser ─────────────────────────────────────────────────────────────

echo
if $MANAGE shell -c "from django.contrib.auth import get_user_model; exit(0 if get_user_model().objects.filter(is_superuser=True).exists() else 1)" 2>/dev/null; then
    yellow "Superuser already exists, skipping. (To add another, run: python standalone/manage.py createsuperuser)"
else
    green "Create your dashboard login (Django superuser):"
    $MANAGE createsuperuser || yellow "Superuser creation skipped."
fi

# ── 7. Collect static files ──────────────────────────────────────────────────

green "Collecting static files..."
$MANAGE collectstatic --noinput --clear 2>/dev/null

# ── 8. Seed filament colors ──────────────────────────────────────────────────

echo
read -rp "Import Bambu Lab filament color catalog? [Y/n] " SEED_COLORS
SEED_COLORS="${SEED_COLORS:-Y}"
if [[ "$SEED_COLORS" =~ ^[Yy] ]]; then
    $MANAGE bambu_import_colors "$REPO_DIR/docs/Bambu_Color_Catalog/"
fi

# ── 9. Install systemd services ──────────────────────────────────────────────

green "Installing systemd user services..."
mkdir -p "$SERVICE_DIR"

# Generate unit files with actual paths substituted
sed "s|{{REPO_DIR}}|$REPO_DIR|g; s|{{VENV_DIR}}|$VENV_DIR|g; s|{{WORKERS}}|$WORKERS|g" \
    "$REPO_DIR/native/bambu-run-web.service" > "$SERVICE_DIR/bambu-run-web.service"

sed "s|{{REPO_DIR}}|$REPO_DIR|g; s|{{VENV_DIR}}|$VENV_DIR|g" \
    "$REPO_DIR/native/bambu-run-collector.service" > "$SERVICE_DIR/bambu-run-collector.service"

systemctl --user daemon-reload
systemctl --user enable bambu-run-web.service bambu-run-collector.service

# ── 9b. Optional MCP server ─────────────────────────────────────────────────

echo
MCP_ENABLED=false
read -rp "Enable MCP server for AI agent access (Claude Desktop, Claude Code, etc.)? [y/N] " ENABLE_MCP
if [[ "$ENABLE_MCP" =~ ^[Yy] ]]; then
    green "Installing MCP dependencies..."
    "$VENV_DIR/bin/pip" install --quiet ".[mcp]"

    sed "s|{{REPO_DIR}}|$REPO_DIR|g; s|{{VENV_DIR}}|$VENV_DIR|g" \
        "$REPO_DIR/native/bambu-run-mcp.service" > "$SERVICE_DIR/bambu-run-mcp.service"

    systemctl --user daemon-reload
    systemctl --user enable bambu-run-mcp.service
    systemctl --user start bambu-run-mcp.service
    MCP_ENABLED=true
    green "MCP server enabled on port 8808."
fi

# Enable linger so services survive SSH logout
loginctl enable-linger "$USER" 2>/dev/null || \
    sudo loginctl enable-linger "$USER" 2>/dev/null || \
    yellow "Warning: Could not enable linger. Services may stop when you disconnect SSH."

systemctl --user start bambu-run-web.service bambu-run-collector.service

# ── 10. Port redirect (ACCESS_PORT → 8000 via iptables if needed) ────────────

PORT_OK=false
if [ "$ACCESS_PORT" -eq 8000 ]; then
    # Gunicorn already on 8000 — no redirect needed
    green "Using port 8000 directly (no redirect needed)."
    PORT_OK=true
else
    if sudo iptables -t nat -C PREROUTING -p tcp --dport "$ACCESS_PORT" -j REDIRECT --to-port 8000 2>/dev/null; then
        yellow "Port $ACCESS_PORT → 8000 redirect already set."
        PORT_OK=true
    else
        # Ensure iptables is available
        if ! command -v iptables &>/dev/null; then
            yellow "Installing iptables..."
            DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq iptables
        fi
        if sudo iptables -t nat -A PREROUTING -p tcp --dport "$ACCESS_PORT" -j REDIRECT --to-port 8000 && \
           sudo iptables -t nat -A OUTPUT -o lo -p tcp --dport "$ACCESS_PORT" -j REDIRECT --to-port 8000; then
            green "Port $ACCESS_PORT → 8000 redirect configured."
            PORT_OK=true
            # Persist so it survives reboot
            if ! command -v netfilter-persistent &>/dev/null; then
                yellow "Installing iptables-persistent to survive reboots..."
                DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq iptables-persistent
            fi
            sudo netfilter-persistent save 2>/dev/null || sudo sh -c 'iptables-save > /etc/iptables/rules.v4'
        else
            yellow "Warning: Could not set port $ACCESS_PORT redirect (sudo required). Access via http://<ip>:8000"
        fi
    fi
fi

# ── 11. Summary ───────────────────────────────────────────────────────────────

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ "$PORT_OK" = true ] && [ "$ACCESS_PORT" -ne 8000 ]; then
    DASHBOARD_URL="http://${PI_IP:-localhost}$([ "$ACCESS_PORT" -eq 80 ] && echo '' || echo ":$ACCESS_PORT")"
else
    DASHBOARD_URL="http://${PI_IP:-localhost}:8000"
fi
echo
green "============================================"
green "  Bambu-Run is running!"
green "============================================"
echo
echo "  Dashboard:  $DASHBOARD_URL"
if [ "$MCP_ENABLED" = true ]; then
    echo "  MCP Server: http://${PI_IP:-localhost}:8808/sse"
fi
echo "  Status:     systemctl --user status bambu-run-web bambu-run-collector"
echo "  Logs:       journalctl --user -u bambu-run-web -u bambu-run-collector -f"
echo "  Helper:     ./native/bambu-run.sh {start|stop|restart|status|logs|update}"
echo
if [ "$MCP_ENABLED" = true ]; then
    echo "  Claude Desktop config:"
    echo "    {\"mcpServers\":{\"bambu-run\":{\"url\":\"http://${PI_IP:-localhost}:8808/sse\"}}}"
    echo
fi
echo "  Services auto-start on boot. Safe to close SSH."
echo
