# Bambu-Run

<p align="center">
  <img src="docs/BambuRun.png" alt="Bambu-Run Logo" width="300"/>
</p>

Richer data, powerful customization for your Bambu Lab 3D printer.

Bambu-Run is a self-hosted web dashboard that gives you:
- Real-time monitoring and logging (temperatures, fan speeds, print progress, and more)
- Automatic filament inventory tracking and usage monitoring (AMS required)

All running on hardware you own.

### What You'll Need

Any always-on device works — a **Raspberry Pi** (3B+, 4, or 5) is ideal: beginner-friendly, runs Raspberry Pi OS out of the box, and quiet enough to tuck behind a desk. An old PC or laptop with Linux works too.

It runs quietly in the background 24/7, capturing every print, filament change, and AMS update the moment it happens. And the power bill? A Raspberry Pi 4 under light load draws about **5W**. That's roughly **43.8 kWh per year**, or the cost of **three cups of coffee**. ☕☕☕ Tuck it out of sight and forget it's there.

---

## What It Looks Like

<table>
  <tr>
    <td width="50%">
      <p align="center"><strong>Live Dashboard</strong><br/>Real-time nozzle temps, bed temp, print progress, and chamber light.</p>
      <img src="https://github.com/user-attachments/assets/169ec3e5-62a9-4e96-afed-dc6ac2647aef" alt="Live Dashboard" width="100%"/>
    </td>
    <td width="50%">
      <p align="center"><strong>Historical Charts</strong><br/>Filament remaining and nozzle temp over time, per printer.</p>
      <img src="https://github.com/user-attachments/assets/11913c62-254f-4ba6-8d93-d5c27a9406be" alt="Historical Charts" width="100%"/>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <p align="center"><strong>Filament Inventory</strong><br/>Every spool you own — brand, type, color, remaining %, current tray.</p>
      <img src="https://github.com/user-attachments/assets/8e472704-a6d8-45e1-93c4-c6f37d0b55a0" alt="Filament Inventory" width="100%"/>
    </td>
    <td width="50%">
      <p align="center"><strong>AMS / Filament Slots</strong><br/>What's loaded right now, grouped by AMS unit, with humidity/temp.</p>
      <img src="https://github.com/user-attachments/assets/200ad65f-a716-4a52-98b2-d5f5ce2445b9" alt="AMS / Filament Slots" width="100%"/>
    </td>
  </tr>
  <tr>
    <td colspan="2">
      <p align="center"><strong>Hotend Wear Tracking</strong><br/>Used time and wear per hotend slot — handy for multi-nozzle / AMS-fed toolhead setups.</p>
      <img src="https://github.com/user-attachments/assets/defee0da-772c-40c2-8dcf-9d3f230cc5ee" alt="Hotend Wear Tracking" width="100%"/>
    </td>
  </tr>
</table>

---

## Table of Contents

- [What It Looks Like](#what-it-looks-like)
- [Native Setup (Recommended for Raspberry Pi)](#native-setup-recommended-for-raspberry-pi)
  - [What You'll Need](#what-youll-need)
  - [Clone and run setup.sh](#clone-and-run-setupsh)
  - [Managing Bambu-Run](#managing-bambu-run)
  - [Troubleshooting (Native)](#troubleshooting-native)
- [Docker Setup](#docker-setup)
- [Batch Importing Filament Colors and Filament Types](#batch-importing-filament-colors-and-filament-types)
- [MCP Server (AI Agent Access)](#mcp-server-ai-agent-access)

---

## Native Setup (Recommended for Raspberry Pi)

No Docker required. Works on any Raspberry Pi (including 32-bit Pi Model B) running Raspberry Pi OS with Python 3.10+.

### What You'll Need

- Raspberry Pi on your local network (Python 3.10+)
- Bambu Lab printer
- Bambu Lab account **email and password**

### Clone and run setup.sh

```bash
git clone https://github.com/RunLit/Bambu-Run.git
cd Bambu-Run
bash setup.sh
```

That's it! The script handles everything interactively, just answer the prompts. When it finishes, open `http://<ip>` from any device on same network.

The script is safe to re-run at any time.

---

**What the script does**:

- **Dependencies**: creates a Python virtual environment, installs all packages
- **Credentials**: prompts for your **BambuLab Cloud account** email, password, and timezone; auto-generates a `DJANGO_SECRET_KEY`; writes `.env`
- **Bambu Cloud auth**: runs `bambu_collector --once`; 
  - Bambu Lab will send a 6-digit code to your email; check you email box and enter it when prompted; 
  - the resulting token is saved to `.env` automatically; future restarts skip this step
- **Dashboard login**: runs `createsuperuser`; choose a username and password for Bambu-Run web UI log in
- **Services**: installs and starts two systemd services (`bambu-run-web` and `bambu-run-collector`), enables linger so they auto-start on boot
- **Port 80**: sets an `iptables` redirect (80 to 8000) so you can reach the dashboard at a plain `http://<pi-ip>` with no port number; persisted via `iptables-persistent` across reboots. 

---

### Managing Bambu-Run

All commands manage Bambu-Run encapsulated in `./native/bambu-run.sh`. Alternatively, you can do it yourself with systemctl commands.
```bash
./native/bambu-run.sh status    # service status
./native/bambu-run.sh logs      # tail live logs (Ctrl+C to stop)
./native/bambu-run.sh restart   # restart both services
./native/bambu-run.sh stop      # stop everything
./native/bambu-run.sh update    # git pull + pip install + migrate + restart
```

### Troubleshooting (Native)

**Services die when SSH disconnects:** `sudo loginctl enable-linger $USER`

**Services not starting:** `./native/bambu-run.sh status` and `./native/bambu-run.sh logs`

**Auth errors / token expired:** Remove `BAMBU_TOKEN` from `.env` and re-run `bash setup.sh`

**Uninstall:**
```bash
systemctl --user disable --now bambu-run-web bambu-run-collector
rm ~/.config/systemd/user/bambu-run-{web,collector}.service
systemctl --user daemon-reload
```

**Wipe everything and start over:**
```bash
# Stop and remove services
systemctl --user stop bambu-run-web bambu-run-collector
systemctl --user disable bambu-run-web bambu-run-collector
rm ~/.config/systemd/user/bambu-run-{web,collector}.service
systemctl --user daemon-reload

# Remove port redirect (replace 80 with whatever port you chose during setup)
sudo iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null || true
sudo iptables -t nat -D OUTPUT -o lo -p tcp --dport 80 -j REDIRECT --to-port 8000 2>/dev/null || true
sudo netfilter-persistent save 2>/dev/null || true

# Delete repo — wipes venv, database, and .env
cd ~
rm -rf ~/Bambu-Run

# Re-clone and run setup from scratch
git clone https://github.com/RunLit/Bambu-Run.git
cd Bambu-Run
bash setup.sh
```

---

## Docker Setup

Requires Docker and Docker Compose installed. Assumes you already know how to get there.

**Clone and configure:**

```bash
git clone https://github.com/RunLit/Bambu-Run.git
cd Bambu-Run
cp .env.example .env
# Edit .env: set BAMBU_USERNAME, BAMBU_PASSWORD, TIMEZONE
```

**First-time auth** (Bambu Lab sends a 6-digit verification code to your email):

```bash
docker compose build
docker compose run --rm bambu-run python standalone/manage.py migrate --noinput
docker compose run --rm bambu-run python standalone/manage.py bambu_collector --once
# Paste the printed token into .env as BAMBU_TOKEN=...
```

**Start and create your dashboard login:**

```bash
docker compose up -d
docker compose exec bambu-run python standalone/manage.py createsuperuser
```

Dashboard is at `http://<host-ip>:8000`.

**Common operations:**

```bash
docker compose logs -f                          # live logs
docker compose down                             # stop (data preserved in volume)
git pull && docker compose up -d --build        # update
```

**Troubleshooting:** Auth errors → remove `BAMBU_TOKEN` from `.env` and re-run the auth step. No data → check `docker compose logs -f` for MQTT connection errors.

---

## Batch Importing Filament Colors and Filament Types

Bambu-Run ships with a full Bambu Lab color catalog under `docs/Bambu_Color_Catalog/` (one `.txt` file per filament sub-type, e.g. `PLA Basic.txt`, `PETG HF.txt`). Importing these populates the **Filament Colors** database so the dashboard shows proper color names instead of raw hex codes.

### Adding your own colors

Need a filament type that isn't in the bundled catalog? Create your own `.txt` file and point the importer at it.

**File naming** — the filename determines the filament type and sub-type:
```
PLA Basic.txt     → type: PLA,  sub-type: PLA Basic
PETG HF.txt       → type: PETG, sub-type: PETG HF
ABS.txt           → type: ABS,  sub-type: ABS
```

**File format** — list each color on its own line, either as two rows (name then hex) or on the same line:
```
Jade White
Hex:#FFFFFF

Black Walnut    #4F3F24
```

Bambu Lab's website filament pages and their downloadable PDF catalogs are a reliable source — both list color names alongside hex codes you can copy directly.

### When to run this

Run the import **once after first setup** to seed the full color catalog in one go, rather than adding colors one by one. Run it again any time you want to add colors for a new filament type. Re-running is always safe — duplicates are detected and skipped automatically.

### Import all colors (recommended)

If the container is already running (`docker compose up -d`):

```bash
docker compose exec bambu-run python standalone/manage.py bambu_import_colors docs/Bambu_Color_Catalog/
```

If the container is not running yet:

```bash
docker compose run --rm bambu-run python standalone/manage.py bambu_import_colors docs/Bambu_Color_Catalog/
```

### Import a file from your computer

If your `.txt` color file lives on your Mac, Pi, or any machine running Docker (i.e. not inside the repo), copy it into the container first, then run the importer:

```bash
# Step 1 — copy the file from your machine into the container
docker compose cp /path/to/your/PLA\ Basic.txt bambu-run:/tmp/

# Step 2 — run the importer against the copied path
docker compose exec bambu-run python standalone/manage.py bambu_import_colors /tmp/PLA\ Basic.txt
```

To import a whole folder of files at once:

```bash
# Step 1 — copy the folder
docker compose cp /path/to/your/color_catalog/ bambu-run:/tmp/color_catalog/

# Step 2 — import everything in it
docker compose exec bambu-run python standalone/manage.py bambu_import_colors /tmp/color_catalog/
```

> **macOS tip:** You can drag a file from Finder into the terminal to paste its full path.

### Import a single filament type

To import only one sub-type from the bundled catalog (e.g. just PLA Basic):

```bash
docker compose exec bambu-run python standalone/manage.py bambu_import_colors "docs/Bambu_Color_Catalog/PLA Basic.txt"
```

### Preview before importing (dry run)

Check what would be added without writing anything to the database:

```bash
docker compose exec bambu-run python standalone/manage.py bambu_import_colors docs/Bambu_Color_Catalog/ --dry-run
```

### What the output means

```
Processing: PLA Basic.txt  →  type='PLA'  sub_type='PLA Basic'
  Parsed 40 color(s).
  + 'Bambu Green' #009F87  (PLA / PLA Basic)
  + 'Jade White'  #FFFFFF  (PLA / PLA Basic)
  ...
──────────────────────────────────────────────────
  Created:              40
  Skipped (duplicate):  0
```

- **Created** — new color entries added to the database
- **Skipped (duplicate)** — already existed, not changed
- **Skipped (no type)** — only shown if `--no-auto-create-filament-type` is used and the filament type isn't in the database yet

## MCP Server (AI Agent Access)

Bambu-Run exposes printer status, print history, and filament inventory as
read-only [MCP](https://modelcontextprotocol.io/) tools, so an AI agent (e.g.
Claude Desktop, Claude Code) can query your printer directly.

Install the extra:

```bash
pip install 'bambu-run[mcp]'
```

**stdio** (for a local agent on the same machine — e.g. Claude Desktop):

```bash
python manage.py bambu_mcp_server --transport stdio
```

**HTTP** (for a remote agent, or multiple callers over the network):

```bash
export BAMBU_RUN_MCP_API_KEY=your-secret-key
python manage.py bambu_mcp_server --transport http --host 0.0.0.0 --port 8808
```

`BAMBU_RUN_MCP_API_KEY` is **required** for HTTP — the server refuses to start
without it, since an unauthenticated network MCP endpoint would expose your
printer and filament data to anyone who can reach the port. stdio needs no key
(the OS process boundary is the trust boundary there).

If serving behind a reverse proxy on a real domain, pass
`--allowed-host your.domain.com` (repeatable) — otherwise the SDK's
DNS-rebinding guard rejects requests with a real `Host` header.
