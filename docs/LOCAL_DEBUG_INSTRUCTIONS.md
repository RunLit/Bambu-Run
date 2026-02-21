# Setup Local Environment for Debug

## Prerequisites

 - Docker Desktop running on macOS
 - Your Bambu Lab account email + password
 - Bambu-Run source at /Users/runnanli/src/Bambu-Run

 ---
### Step 1 — Create .env

 Create /Users/runnanli/src/Bambu-Run/.env:
 BAMBU_USERNAME=your_bambulab_email@example.com
 BAMBU_PASSWORD=your_bambulab_password
 TIMEZONE=Australia/Melbourne
 No DB vars needed — SQLite is the default when DB_NAME is absent.

 ---
### Step 2 — Build the image

 cd /Users/runnanli/src/Bambu-Run
 docker compose build
 Takes a few minutes first time.

 ---
### Step 3 — Run database migrations

 docker compose run --rm bambu-run python standalone/manage.py migrate --noinput

 ---
### Step 4 — First-time Bambu Lab authentication (email verification)

 docker compose run --rm bambu-run python standalone/manage.py bambu_collector --once

 You'll be prompted for a 6-digit code sent to your email. Enter it.
 On success the token is printed:
 Token: eyJhbGci...

 Add it to .env:
 BAMBU_TOKEN=eyJhbGci...paste_full_token_here
 Future restarts will skip email verification.

 ---
### Step 5 — Start everything

 docker compose up -d

 Supervisord starts three processes: migrate (idempotent), web (gunicorn on :8000), collector (polls printer continuously).

 ---
### Step 6 — Create a login account

 docker compose exec bambu-run python standalone/manage.py createsuperuser

 ---
### Step 7 — Open the dashboard

 http://localhost:8000

 ---
### Useful commands

#### Watch live logs
 docker compose logs -f

#### Stop
 docker compose down

#### Rebuild after code changes
 docker compose up -d --build

### Notes

 - SQLite lives inside Docker volume bambu_data — persists across restarts
 - If charts are blank: printer must be on; give collector ~1 minute to start polling
