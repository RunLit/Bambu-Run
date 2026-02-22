# Bambu-Run

<p align="center">
  <img src="docs/BambuRun.png" alt="Bambu-Run Logo" width="300"/>
</p>

Unlock richer data access and powerful customization capabilities for your Bambu Lab 3D printer.

Bambu-Run is a self-hosted web dashboard that tracks data of your Bambu Lab printer. It gives you:
- Real-time monitoring and logging (temperatures, fan speeds, print progress etc) 
- Automatic filament inventory tracking and usage monitoring system (AMS required)
all running on hardware you own.

### Hardware Requirement

Recommend a raspberry pi, installed with Raspberry Pi OS (low cost running at the background) or an old PC/Laptop you probably never going to use again (install Linux).

## Quick Start: One-Click Docker Setup — Beginner Friendly

Get Bambu-Run running on a **Raspberry Pi** in minutes. No prior server experience needed.

### What You'll Need

- A Raspberry Pi (3B+, 4, or 5) with Raspberry Pi OS, connected to your network
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
