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
    read -rp "Timezone [UTC] (e.g. America/New_York): " TIMEZONE
    TIMEZONE="${TIMEZONE:-UTC}"

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
green "Create your dashboard login (Django superuser):"
$MANAGE createsuperuser || yellow "Superuser creation skipped."

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

# Enable linger so services survive SSH logout
loginctl enable-linger "$USER" 2>/dev/null || \
    sudo loginctl enable-linger "$USER" 2>/dev/null || \
    yellow "Warning: Could not enable linger. Services may stop when you disconnect SSH."

systemctl --user start bambu-run-web.service bambu-run-collector.service

# ── 10. Summary ───────────────────────────────────────────────────────────────

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
green "============================================"
green "  Bambu-Run is running!"
green "============================================"
echo
echo "  Dashboard:  http://${PI_IP:-localhost}:8000"
echo "  Status:     systemctl --user status bambu-run-web bambu-run-collector"
echo "  Logs:       journalctl --user -u bambu-run-web -u bambu-run-collector -f"
echo "  Helper:     ./native/bambu-run.sh {start|stop|restart|status|logs|update}"
echo
echo "  Services auto-start on boot. Safe to close SSH."
echo
