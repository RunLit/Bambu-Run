# Bambu-Run

Unlock richer data access and powerful customization capabilities for your Bambu Lab 3D printer.

Bambu-Run is a self-hosted web dashboard that tracks data of your Bambu Lab printer. It gives you:
- Real-time monitoring and logging (temperatures, fan speeds, print progress etc) 
- Automatic filament inventory tracking and usage monitoring system (AMS required)
all running on hardware you own.

### Hardware Requirement

Recommend a raspberry pi, installed with Raspberry Pi OS (low cost running at the background) or an old PC/Laptop you probably never going to use again (install Linux).

## Getting Started (Beginner Friendly)

This guide walks you through setting up Bambu-Run on a **Raspberry Pi** from scratch. No prior server experience needed.

### What You'll Need

- A Raspberry Pi (3B+, 4, or 5) with Raspberry Pi OS installed and connected to your network
- Your Bambu Lab printer on the **same local network** as the Pi
- Your printer's **IP address**, **access token**, and **serial number** (we'll show you how to find these below)
- A computer on the same network to SSH into the Pi

### Step 1: Find Your Bambu Lab Account Credentials

Bambu-Run connects to your printer through the **Bambu Lab Cloud** using your account login — the same email and password you use for Bambu Handy or Bambu Studio.

You'll need:
- **BAMBU_USERNAME** — Your Bambu Lab account email
- **BAMBU_PASSWORD** — Your Bambu Lab account password

> **First-time login requires email verification.** Bambu Lab will send a 6-digit code to your email. You'll enter this code during Step 5a below. After that, you'll receive a token that skips verification on future startups.

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
Installation issue? check installation methods for raspberry pi: https://docs.docker.com/engine/install/raspberry-pi-os/#installation-methods

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

Fill in your Bambu Lab account credentials from Step 1:

```
BAMBU_USERNAME=your_email@example.com
BAMBU_PASSWORD=your_password
```

Optionally set your timezone (defaults to UTC):

```
TIMEZONE=Australia/Melbourne
```

> You can find your timezone name at https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

To save and exit nano: press `Ctrl + X`, then `Y`, then `Enter`.

### Step 5: Build and Start Bambu-Run

First, build the container:

```bash
docker compose build
```

This downloads all required software (takes a few minutes the first time).

### Step 5a: First-Time Authentication

The first time you connect, Bambu Lab requires email verification. You need to run the collector **interactively** (not in the background) so you can enter the 6-digit code:

```bash
docker compose run --rm bambu-run python standalone/manage.py bambu_collector --once
```

You'll see output like:

```
BambuLab Authentication
Authenticating as: your_email@example.com
...
EMAIL VERIFICATION REQUIRED
A verification code has been sent to your email.
Enter verification code:
```

1. Check your email for the 6-digit code from Bambu Lab
2. Type the code and press Enter
3. On success, you'll see a token printed:
   ```
   Authentication successful!
   Token: eyJhbGciOiJIUzI1N...
   TIP: Save this token to BAMBU_TOKEN env var to skip login next time
   ```

4. **Copy the full token** and paste it into your `.env` file:
   ```bash
   nano .env
   ```
   Add/uncomment the `BAMBU_TOKEN` line:
   ```
   BAMBU_TOKEN=eyJhbGciOiJIUzI1N...paste_full_token_here
   ```

> **Why save the token?** With the token saved, future container restarts authenticate instantly without needing email verification again. Without it, you'd need to repeat this step every time the container restarts.

### Step 5b: Start Bambu-Run

Now start everything in the background:

```bash
docker compose up -d
```

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
- Make sure your printer is turned on and connected to the network
- Check the logs: `docker compose logs -f`
- If you see authentication errors, your token may have expired — re-run Step 5a to get a fresh token

**"Verification code" or "401 Unauthorized" errors:**
- Your `BAMBU_TOKEN` may have expired. Remove it from `.env` and re-run Step 5a
- Make sure `BAMBU_USERNAME` and `BAMBU_PASSWORD` are correct in your `.env` file

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
