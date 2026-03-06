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

## Table of Contents

- [Native Setup (Recommended for Raspberry Pi)](#native-setup-recommended-for-raspberry-pi)
  - [What You'll Need](#what-youll-need)
  - [Step 1: Clone and run setup.sh](#step-1-clone-and-run-setupsh)
  - [Step 2: Credentials and .env](#step-2-credentials-and-env)
  - [Step 3: Bambu Cloud authentication](#step-3-bambu-cloud-authentication)
  - [Step 4: Dashboard login](#step-4-dashboard-login)
  - [Step 5: Services start automatically](#step-5-services-start-automatically)
  - [Managing Bambu-Run](#managing-bambu-run)
  - [Troubleshooting (Native)](#troubleshooting-native)
- [Docker Setup](#docker-setup)
- [Batch Importing Filament Colors and Filament Types](#batch-importing-filament-colors-and-filament-types)

---

## Native Setup (Recommended for Raspberry Pi)

No Docker required. Works on any Raspberry Pi (including 32-bit Pi Model B) running Raspberry Pi OS with Python 3.10+.

### What You'll Need

- Raspberry Pi on your local network (Python 3.10+ — ships with Raspberry Pi OS Bookworm by default)
- Bambu Lab printer on the **same local network**
- Bambu Lab account **email and password**

### Step 1: Clone and run setup.sh

```bash
git clone https://github.com/RunLit/Bambu-Run.git
cd Bambu-Run
bash setup.sh
```

The script is fully interactive and idempotent (safe to re-run). It:

1. Checks Python >= 3.10 and installs `python3-venv` if missing
2. Creates `.venv`, stubs opencv to avoid slow ARM compilation, and runs `pip install ".[standalone]"`
3. Prompts for credentials and auto-generates `DJANGO_SECRET_KEY` — writes `.env`
4. Runs `manage.py migrate`
5. Runs `bambu_collector --once` for Bambu Cloud email verification (see Step 3)
6. Runs `manage.py createsuperuser` for your dashboard login
7. Runs `collectstatic`
8. Optionally imports the bundled Bambu filament color catalog
9. Writes and enables `systemd` user services, calls `loginctl enable-linger` so they survive SSH disconnect, and starts them

### Step 2: Credentials and .env

If `.env` doesn't exist, the script prompts for:

| Variable | Description |
|---|---|
| `BAMBU_USERNAME` | Bambu Lab account email |
| `BAMBU_PASSWORD` | Bambu Lab account password |
| `TIMEZONE` | e.g. `America/New_York` (default: `UTC`) |

`DJANGO_SECRET_KEY` is auto-generated. To edit later: `nano .env`, then `./native/bambu-run.sh restart`.

### Step 3: Bambu Cloud authentication

Bambu Lab requires email verification on first login:

1. The script runs `bambu_collector --once` — a 6-digit code is sent to your email
2. Enter the code when prompted
3. A `BAMBU_TOKEN` is printed — paste it when the script asks, and it's appended to `.env`

Future restarts skip verification automatically. To re-authenticate, remove `BAMBU_TOKEN` from `.env` and re-run the script.

### Step 4: Dashboard login

The script runs `manage.py createsuperuser` — choose a username and password for the web dashboard.

### Step 5: Services start automatically

Two systemd user services are installed and started:

| Service | Role |
|---|---|
| `bambu-run-web` | gunicorn on port 8000 (1 worker <1 GB RAM, 2 workers otherwise) |
| `bambu-run-collector` | MQTT poller, restarts on failure |

Both auto-start on boot via `loginctl enable-linger`. Open `http://<pi-ip>:8000` from any device on your network.

### Managing Bambu-Run

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
