-- Expense Tracker bot — PostgreSQL schema (idempotent)

CREATE TABLE IF NOT EXISTS users (
    telegram_user_id BIGINT PRIMARY KEY,
    sheet_id         TEXT        NOT NULL,
    base_currency    TEXT        NOT NULL,   -- conversion target (e.g. EUR)
    default_currency TEXT        NOT NULL,   -- pre-selected input currency (e.g. RSD)
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migration for existing installs: default to the base currency if not set.
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_currency TEXT;
UPDATE users SET default_currency = base_currency WHERE default_currency IS NULL;

-- Per-user place -> category dictionary (powers smart categorization).
CREATE TABLE IF NOT EXISTS place_category (
    telegram_user_id BIGINT      NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
    place            TEXT        NOT NULL,   -- normalized (lowercased, trimmed)
    category         TEXT        NOT NULL,
    currency         TEXT,                   -- last currency used here; NULL = unknown
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (telegram_user_id, place)
);

-- Migration for existing installs: unknown for places recorded before this.
ALTER TABLE place_category ADD COLUMN IF NOT EXISTS currency TEXT;

-- Per-user extra categories, on top of the built-in ones in bot/categories.py
-- (defaults live in code, so they are not duplicated per user).
CREATE TABLE IF NOT EXISTS custom_category (
    telegram_user_id BIGINT      NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
    name             TEXT        NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (telegram_user_id, name)
);

-- Daily exchange-rate cache. One row per (base_currency, fetched_date);
-- `rates` holds the full target->rate map returned by the API.
CREATE TABLE IF NOT EXISTS rate_cache (
    base_currency TEXT  NOT NULL,
    fetched_date  DATE  NOT NULL,
    rates         JSONB NOT NULL,
    PRIMARY KEY (base_currency, fetched_date)
);
