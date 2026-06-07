# Expense Tracker Telegram Bot — Requirements

## Overview

A Telegram bot for logging personal expenses in real time, storing data in Google Sheets. Designed for daily use on mobile — fast input, minimal taps, smart categorization based on history. Each user connects their own Google Drive and gets a dedicated Sheet.

---

## Onboarding Flow (`/start`)

1. Bot greets user and sends a link to a **template Google Sheet** (pre-formatted with the data-model columns)
2. User makes a copy in their own Drive, then **shares it as Editor** with the bot's service-account email (`expense-bot@<project>.iam.gserviceaccount.com`) and pastes the sheet link back
3. Bot extracts `sheet_id` from the link, writes a test row via the service account to confirm access
4. Bot asks to select **base currency**: `EUR · USD · RSD · Other`
5. Bot confirms setup and explains how to log expenses
6. User data (`telegram_user_id`, `sheet_id`, `base_currency`) stored in server-side PostgreSQL — **no OAuth tokens needed**

---

## Expense Entry Flow

1. User sends **amount + place name** (e.g. `23000 Ikea`)
2. Bot shows **currency buttons** — default currency pre-selected bold: `RSD · EUR · USD · RUB · Other`
3. Bot suggests **category** based on place history:
   - Known place → suggested category shown as first wide button (e.g. `✓ Housing`)
   - New place → standard category grid
4. User confirms or overrides category
5. Bot optionally asks for a **comment** (skip button available)
6. Bot optionally allows **custom expense date**: `Today · Yesterday · Pick date`
7. Entry saved to user's Google Sheet

---

## Category Buttons

### Quick buttons (top 6, always visible)
- Restaurants
- Grocery
- Housing
- Sport
- Car
- Health & Beauty

### Extended list (shown on "More...")
- Entertainment
- Travel
- Taxi & Transport
- Clothes
- Psychologist
- Business
- Other

---

## Data Model

Each row in Google Sheets:

| Field | Description |
|---|---|
| `recorded_at` | Timestamp when entry was submitted |
| `expense_date` | Date of actual expense (defaults to today) |
| `amount` | Numeric amount as entered |
| `currency` | Currency as entered (RSD, EUR, USD, RUB…) |
| `amount_base` | Converted to user's base currency at the current (latest) rate |
| `base_currency` | User's base currency (set during onboarding) |
| `category` | Selected category |
| `place` | Place name / merchant as entered |
| `comment` | Optional free-text comment |

---

## Smart Categorization

- Bot maintains a per-user **place → category dictionary** in PostgreSQL
- Place name matched case-insensitively (fuzzy match preferred)
- If match found → suggested category shown as first wide button
- User can always override — chosen category saved back to dictionary
- **Seed data:** initial dictionary pre-populated from 2023–2025 historical export to be smart from day one

---

## Currency & Conversion

- **Default input currency: RSD** (shown bold/first)
- User's **base currency** selected during onboarding (e.g. EUR)
- Every entry auto-converted to base currency
- **Rate source:** [ExchangeRate-API open access](https://www.exchangerate-api.com/docs/free) — **no API key**, endpoint `GET https://open.er-api.com/v6/latest/{BASE}`, 165 currencies (incl. **RSD and RUB**), updated once per day
  - Rates fetched once per day and **cached in PostgreSQL**
  - **v1 simplification:** all entries use the **latest (current) rate**, including backdated ones — no historical/date-specific lookups. Good enough for near-real-time logging; revisit if accurate historical conversion is ever needed.
  - Attribution required by their terms — include a "Rates by ExchangeRate-API" line in `/help` or onboarding
  - ⚠️ Frankfurter is **not** usable — it's ECB-only (31 currencies) and supports neither RSD nor RUB
- **Conversion failure:** if the rate fetch fails, fall back to the last cached rate; if none exists, store `amount_base` as `NULL` and never block the entry

---

## Date Handling

- Default expense date = today
- Quick options: `Today · Yesterday · Pick date`
- `recorded_at` always set to submission timestamp automatically

---

## Multi-user Architecture

- All logic keyed by `telegram_user_id` — multi-user from day one
- Each user has their own: Google Sheet, OAuth tokens, base currency, place→category dictionary
- v1 can be invite-only or single-user, but zero refactoring needed to open up

---

## Infrastructure

- **Platform:** Telegram Bot (via BotFather token)
- **Hosting:** Hetzner VPS (existing), deployed via **Docker Compose** (bot + PostgreSQL containers)
- **Language:** Python
- **Libraries:** `python-telegram-bot`, `gspread`, `google-auth`, `httpx`, `asyncpg`
- **Database:** PostgreSQL — users, sheet IDs, place→category dictionary, daily rate cache
- **Sheets access:** single **Google service account**; each user shares their own sheet (Editor) with the service-account email
  - One service-account JSON key for the whole bot — store as a secret (env var / secret store), **never in git**
  - No per-user OAuth flow, no consent screen, no Google app-verification review, no refresh tokens to store

---

## Out of Scope (v1)

- Analytics dashboard inside Telegram
- Receipt photo scanning
- Budget limits / alerts
- Recurring expenses
- Public registration / invite system
