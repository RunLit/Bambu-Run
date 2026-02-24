# Bambu-Run

<p align="center">
  <img src="docs/BambuRun.png" alt="Bambu-Run Logo" width="300"/>
</p>

Unlock richer data access and powerful customization capabilities for your Bambu Lab 3D printer.

Bambu-Run is a self-hosted web dashboard that tracks data of your Bambu Lab printer. It gives you:
- Real-time monitoring and logging (temperatures, fan speeds, print progress etc)
- Automatic filament inventory tracking and usage monitoring system (AMS required)
all running on hardware you own.

### What You'll Need

Any always-on device: 
- A **Raspberry Pi** (3B+, 4, or 5) is ideal: beginner-friendly, runs Raspberry Pi OS out of the box, and silent enough to tuck behind a desk. 
- Or an old PC or laptop with Linux works too.

It runs quietly in the background 24/7, capturing every print, filament change, and AMS update the moment it happens. And the power bill? A Raspberry Pi 4 under light load draws about **5W**. That's roughly **43.8 kWh per year**, or the cost of **three cups of coffee**. ☕☕☕ Tuck it out of sight and forget it's there.

---

## Table of Contents

- [Quick Start: One-Click Docker Setup — Beginner Friendly](#quick-start-one-click-docker-setup--beginner-friendly)
  - [What You'll Need](#what-youll-need)
  - [Step 1: Connect to Your Raspberry Pi](#step-1-connect-to-your-raspberry-pi)
  - [Step 2: Install Docker](#step-2-install-docker)
  - [Step 3: Download and Configure](#step-3-download-and-configure)
  - [Step 4: Build the Container](#step-4-build-the-container)
  - [Step 5: First-Time Authentication](#step-5-first-time-authentication)
  - [Step 6: Start Bambu-Run and Create Your Login](#step-6-start-bambu-run-and-create-your-login)
  - [Step 7: Open the Dashboard](#step-7-open-the-dashboard)
  - [Troubleshooting](#troubleshooting)
- [Batch Importing Filament Colors and Filament Types](#batch-importing-filament-colors-and-filament-types)

---

## Quick Start: One-Click Docker Setup — Beginner Friendly

Get Bambu-Run running on a **Raspberry Pi** in minutes. No prior server experience needed.

### What You'll Need

- A Raspberry Pi (3B+, 4, or 5) running Raspberry Pi OS 64-bit, with a 32 GB+ MicroSD card, connected to your network
- Your Bambu Lab printer on the **same local network**
- Your Bambu Lab account **email and password**
- A computer to SSH into the Pi

### Step 1: Connect to Your Raspberry Pi

From your computer, open a terminal (Mac/Linux) or PowerShell (Windows):

```bash
ssh pi@raspberrypi.local
```

> Can't connect? Use your Pi's IP address (find it in your router's admin page). Default password: `raspberry`

### Step 2: Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Log out and back in for the change to take effect, then verify:

```bash
exit
```

```bash
ssh pi@raspberrypi.local
docker --version   # should show Docker version 27.x.x
```

> Installation issues? See: https://docs.docker.com/engine/install/raspberry-pi-os/

### Step 3: Download and Configure

```bash
git clone https://github.com/RunLit/Bambu-Run.git
cd Bambu-Run
cp .env.example .env
nano .env
```

Fill in your Bambu Lab credentials:

```
BAMBU_USERNAME=your_email@example.com
BAMBU_PASSWORD=your_password
TIMEZONE=Australia/Melbourne   # optional — find yours at https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
```

Save: `Ctrl + X`, `Y`, `Enter`

### Step 4: Build the Container

```bash
docker compose build
```

This takes a few minutes the first time — it downloads all required software.

### Step 5: First-Time Authentication

Bambu Lab requires email verification on first login. Run these two commands:

```bash
docker compose run --rm bambu-run python standalone/manage.py migrate --noinput
docker compose run --rm bambu-run python standalone/manage.py bambu_collector --once
```

When prompted, enter the 6-digit code sent to your email. On success you'll see a token printed — copy it and add it to your `.env`:

```bash
nano .env
```

```
BAMBU_TOKEN=eyJhbGciOiJIUzI1N...paste_full_token_here
```

> Saving the token lets future restarts skip re-verification automatically.

### Step 6: Start Bambu-Run and Create Your Login

```bash
docker compose up -d
docker compose exec bambu-run python standalone/manage.py createsuperuser
```

Choose a username and password — this is your dashboard login.

### Step 7: Open the Dashboard

On any device on your network, open a browser and go to:

```
http://raspberrypi.local:8000
```

> If that doesn't work, use your Pi's IP: `http://<pi-ip-address>:8000`

Log in with the account you just created. Your printer dashboard should be live.

### Troubleshooting

**No data / cannot connect to printer:** Make sure the printer is on and on the same network. Check logs: `docker compose logs -f`. If you see auth errors, re-run Step 5 to get a fresh token.

**401 Unauthorized / verification loop:** Remove `BAMBU_TOKEN` from `.env` and re-run Step 5.

**Docker daemon error:** Log out and back in after Step 2 — the group change requires a new session.

**Dashboard not loading:** Run `docker compose ps` to confirm the service is `Up`, then try the Pi's IP address directly.

**Update Bambu-Run:**
```bash
cd ~/Bambu-Run && git pull && docker compose up -d --build
```

**Stop Bambu-Run:**
```bash
docker compose down
```

Your data is preserved in a Docker volume and will be there when you start it again.

---

## Batch Importing Filament Colors and Filament Types

Bambu-Run ships with a full Bambu Lab color catalog under `docs/Bambu_Color_Catalog/` (one `.txt` file per filament sub-type, e.g. `PLA Basic.txt`, `PETG HF.txt`). Importing these populates the **Filament Colors** database so the dashboard can show proper color names instead of raw hex codes. 

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

When you're lazy and don't want to add all possible color by manual input.

Run the import **once after first setup**, and again any time you want to add colors for a new filament type. Re-running is safe — duplicates are detected and skipped automatically.

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
