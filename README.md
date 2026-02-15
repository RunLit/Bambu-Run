# Bambu-Run

Unlock deeper control, richer data access, and powerful customization capabilities for your Bambu Lab 3D printer.

Bambu-Run is a self-hosted web dashboard that connects to your Bambu Lab printer over your local network via MQTT. It gives you real-time monitoring (temperatures, fan speeds, print progress) and a full filament inventory system — all running on hardware you own.

## Getting Started (Beginner Friendly)

This guide walks you through setting up Bambu-Run on a **Raspberry Pi** from scratch. No prior server experience needed.

### What You'll Need

- A Raspberry Pi (3B+, 4, or 5) with Raspberry Pi OS installed and connected to your network
- Your Bambu Lab printer on the **same local network** as the Pi
- Your printer's **IP address**, **access token**, and **serial number** (we'll show you how to find these below)
- A computer on the same network to SSH into the Pi

### Step 1: Find Your Printer's Connection Details

You'll need three pieces of information from your printer. Here's how to find them:

**IP Address:**
1. On your printer's touchscreen, go to **Settings** (gear icon)
2. Tap **Network** — your IP address is shown (e.g. `192.168.1.42`)

**Access Token:**
1. On the touchscreen, go to **Settings**
2. Tap **General** > **Access Code** — note down the 8-character code

**Serial Number:**
1. On the touchscreen, go to **Settings**
2. Tap **Device Info** — the serial number is listed at the top

Write all three down. You'll need them in Step 4.

### Step 2: Connect to Your Raspberry Pi

From your computer, open a terminal (Mac/Linux) or PowerShell (Windows) and SSH into the Pi:

```bash
ssh pi@raspberrypi.local
```

> If `raspberrypi.local` doesn't work, use your Pi's IP address instead (check your router's admin page to find it).

The default password is `raspberry` (you should change it after first login with `passwd`).

### Step 3: Install Docker

Docker lets you run Bambu-Run in a container — no need to install Python, databases, or anything else manually.

Run these commands one at a time:

```bash
# Download and run Docker's install script
curl -fsSL https://get.docker.com | sudo sh

# Let your user run Docker without sudo
sudo usermod -aG docker $USER
```

**Important:** Log out and log back in for the group change to take effect:

```bash
exit
```

Then SSH back in:

```bash
ssh pi@raspberrypi.local
```

Verify Docker is working:

```bash
docker --version
```

You should see something like `Docker version 27.x.x` — the exact number doesn't matter.

### Step 4: Download and Configure Bambu-Run

```bash
# Clone the project
git clone https://github.com/RunLit/Bambu-Run.git
cd Bambu-Run

# Create your configuration file
cp .env.example .env
```

Now edit the `.env` file with your printer details:

```bash
nano .env
```

Fill in the three values you noted in Step 1:

```
PRINTER_IP=192.168.1.42
ACCESS_TOKEN=your8char
PRINTER_SERIAL=01P00A000000000
```

Optionally set your timezone (defaults to UTC):

```
TIMEZONE=Australia/Melbourne
```

> You can find your timezone name at https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

To save and exit nano: press `Ctrl + X`, then `Y`, then `Enter`.

### Step 5: Start Bambu-Run

```bash
docker compose up -d
```

This will:
- Download all required software automatically (takes a few minutes the first time)
- Set up the database
- Start the web dashboard and printer data collector in the background

Check that it's running:

```bash
docker compose ps
```

You should see the `bambu-run` service with status `Up`.

### Step 6: Create Your Login Account

```bash
docker compose exec bambu-run python standalone/manage.py createsuperuser
```

You'll be prompted to choose a username, email (optional), and password. This is your login for the dashboard.

### Step 7: Open the Dashboard

On any device connected to your network (phone, tablet, computer), open a browser and go to:

```
http://raspberrypi.local:8000
```

> If that doesn't work, use your Pi's IP address: `http://<pi-ip-address>:8000`

Log in with the account you just created. You should see your printer dashboard with live data flowing in.

### Troubleshooting

**"Cannot connect to printer" or no data showing:**
- Make sure your printer is turned on and connected to the same network
- Double-check the IP address, access token, and serial number in your `.env` file
- Check the logs: `docker compose logs -f`

**"Cannot connect to Docker daemon":**
- Did you log out and back in after Step 3? Docker group changes require a new session

**Dashboard not loading in browser:**
- Verify the container is running: `docker compose ps`
- Try using the Pi's IP address instead of `raspberrypi.local`

**Updating to a newer version:**
```bash
cd ~/Bambu-Run
git pull
docker compose up -d --build
```

**Stopping Bambu-Run:**
```bash
docker compose down
```

Your data is preserved in a Docker volume and will be there when you start it again.
