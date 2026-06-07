# Expense Tracker Telegram Bot

A Telegram bot for logging personal expenses in real time, storing each user's data
in their own Google Sheet. See [`expense_tracker_bot_requirements.md`](./expense_tracker_bot_requirements.md)
for the full product spec.

- **Language:** Python
- **Bot framework:** `python-telegram-bot`
- **Storage:** PostgreSQL (users, sheet IDs, place→category dictionary, daily rate cache) + per-user Google Sheets
- **Sheets access:** one Google **service account** — users share their own sheet with it (no per-user OAuth)
- **Rates:** [ExchangeRate-API](https://www.exchangerate-api.com/docs/free) open access (no API key)

> **Deployment model:** runs **fully self-contained** (its own bot + Postgres
> containers) on the existing Hetzner server, sharing nothing with the Cram stack.
> The only thing it borrows is disk: its Postgres data lives in a subdirectory of the
> attached persistent volume (`/mnt/cram-data/finance/postgres`). A change to one
> project can never affect the other.

> ⚠️ This README documents setup and deployment for the planned stack. The bot's
> entry point is assumed to be `main.py` (`python main.py`) — adjust the commands
> below if your code uses a different module/entry point.

---

## Prerequisites

- A Hetzner VPS (or any Linux box) with **Docker Engine + Docker Compose**
- A **Telegram bot token** (from [@BotFather](https://t.me/BotFather))
- A **Google Cloud service account** with the Sheets + Drive APIs enabled

> Python and PostgreSQL run **inside containers** — you don't install them on the host.

---

## 1. Get a Telegram bot token

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Follow the prompts, copy the token it gives you
3. Put it in `.env` as `BOT_TOKEN`

## 2. Create the Google service account

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) → create (or pick) a project
2. **APIs & Services → Library** → enable **Google Sheets API** and **Google Drive API**
3. **APIs & Services → Credentials → Create credentials → Service account**
4. Create a key for it: **Keys → Add key → JSON** → download the file
5. Copy the service account's email (looks like `expense-bot@your-project.iam.gserviceaccount.com`)
   — this is what users share their sheet with
6. Store the JSON on the server (e.g. `/opt/expense-bot/service_account.json`) and point
   `GOOGLE_SERVICE_ACCOUNT_FILE` at it. **Never commit this file** (already in `.gitignore`).

> **How users connect their sheet:** during `/start` they copy your template sheet,
> click **Share**, add the service-account email as **Editor**, and paste the link back.
> The bot stores the extracted `sheet_id` in Postgres.

## 3. PostgreSQL

No manual install needed — PostgreSQL runs as the `db` service in
`docker-compose.yml` with a persistent named volume (`pgdata`). You only need to set
`POSTGRES_PASSWORD` and `DATABASE_URL` in `.env` (see below). Run your schema
migrations / table creation against the running container as part of app startup.

## 4. Configure environment

```bash
cp .env.example .env
# edit .env: BOT_TOKEN, POSTGRES_PASSWORD, DATABASE_URL, GOOGLE_SERVICE_ACCOUNT_FILE
```

Two Docker-specific gotchas already baked into `.env.example`:
- `DATABASE_URL` host is **`db`** (the compose service name), not `localhost`
- `GOOGLE_SERVICE_ACCOUNT_FILE` is the **in-container** path `/app/service_account.json`
  (mounted from the host by compose)

---

## Run locally with Docker

```bash
cp .env.example .env            # fill in real values
# place service_account.json in the project root
docker compose up --build
```

The bot uses Telegram **long polling**, so no inbound ports or domain are required —
outbound HTTPS is enough.

---

## Deploy on Hetzner (Docker Compose)

Docker is **already installed** on the server (the Cram stack uses it), so there's no
one-time server setup beyond placing this project's files. It runs as its own isolated
Compose project — it does not touch Cram's compose, network, or database.

### 1. Get the project onto the server

The repo is private and the server has no GitHub auth, so the simplest push is
`git archive` from your machine (sends only committed files — no secrets, no `.git`):

```bash
# from your local checkout:
ssh root@<server> 'mkdir -p /opt/finance-tracker'
git archive --format=tar HEAD | ssh root@<server> 'tar xf - -C /opt/finance-tracker'
# copy secrets separately (never committed):
scp .env service_account.json root@<server>:/opt/finance-tracker/
```

Then on the server, lock down the secrets. **Important:** the container runs as a
non-root user (uid 1000), so the service-account file must be *owned* by that uid —
`chmod 600` alone leaves it root-owned and the bot gets `PermissionError`:

```bash
cd /opt/finance-tracker
chmod 600 .env
chown 1000:1000 service_account.json && chmod 600 service_account.json
```

### 2. Create the data directory on the persistent volume

The bot's Postgres stores its data on the attached `/mnt/cram-data` volume so it
survives container rebuilds and lives where backups already run:

```bash
sudo mkdir -p /mnt/cram-data/finance/postgres
```

Make sure `.env` has `POSTGRES_DATA_DIR=/mnt/cram-data/finance/postgres`.

### 3. Build and start (detached)

```bash
docker compose up -d --build
docker compose ps
```

### 4. Logs and updates

```bash
# follow logs
docker compose logs -f bot

# deploy an update (from your local checkout)
git archive --format=tar HEAD | ssh root@<server> 'tar xf - -C /opt/finance-tracker'
ssh root@<server> 'cd /opt/finance-tracker && docker compose up -d --build'
# rebuilds the bot image; the DB data on /mnt/cram-data/finance/postgres is untouched
```

`restart: unless-stopped` means both containers come back automatically after a crash
or server reboot. Because the Postgres data lives on `/mnt/cram-data/finance/postgres`,
you can `docker compose down` (even remove the containers) without losing data.

---

## Operational notes

- **Secrets:** `.env` and `service_account.json` live only on the server and are
  git-ignored. Anyone with the service-account JSON can access every shared sheet —
  lock down file permissions (`chmod 600`).
- **Exchange rates:** fetched once per day and cached in Postgres; the bot uses the
  current rate for all entries (including backdated ones) in v1.
- **Attribution:** ExchangeRate-API's free terms ask for a "Rates by ExchangeRate-API"
  credit — surface it in `/help` or onboarding.
- **No webhook needed:** long polling avoids the need for a public domain, TLS cert,
  or open inbound port. Switch to webhooks later only if you need lower latency at scale.
- **Isolation:** this is a standalone Compose project — its own bot + Postgres
  containers, its own network. It shares only the physical disk (`/mnt/cram-data`) with
  Cram, via a separate `finance/` subdirectory. Nothing in this project can affect Cram.
- **Backups:** the Postgres data persists at `/mnt/cram-data/finance/postgres`. For a
  logical dump: `docker compose exec db pg_dump -U expense_bot expense_bot > backup.sql`.
  User sheets live in the users' own Drives.
