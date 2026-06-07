"""PostgreSQL access via asyncpg."""
from __future__ import annotations

import json
from pathlib import Path

import asyncpg

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)


async def init_schema(pool: asyncpg.Pool) -> None:
    ddl = SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(ddl)


# ── Users ──────────────────────────────────────────────────────────────────

async def get_user(pool: asyncpg.Pool, tg_id: int) -> asyncpg.Record | None:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_user_id = $1", tg_id
        )


async def create_user(
    pool: asyncpg.Pool,
    tg_id: int,
    sheet_id: str,
    base_currency: str,
    default_currency: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (telegram_user_id, sheet_id, base_currency, default_currency)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_user_id)
            DO UPDATE SET sheet_id = EXCLUDED.sheet_id,
                          base_currency = EXCLUDED.base_currency,
                          default_currency = EXCLUDED.default_currency
            """,
            tg_id,
            sheet_id,
            base_currency,
            default_currency,
        )


# ── Place -> category dictionary ─────────────────────────────────────────────

async def get_place_category(
    pool: asyncpg.Pool, tg_id: int, place_norm: str
) -> str | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT category FROM place_category "
            "WHERE telegram_user_id = $1 AND place = $2",
            tg_id,
            place_norm,
        )


async def list_place_categories(
    pool: asyncpg.Pool, tg_id: int
) -> list[tuple[str, str]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT place, category FROM place_category WHERE telegram_user_id = $1",
            tg_id,
        )
    return [(r["place"], r["category"]) for r in rows]


async def upsert_place_category(
    pool: asyncpg.Pool, tg_id: int, place_norm: str, category: str
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO place_category (telegram_user_id, place, category)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_user_id, place)
            DO UPDATE SET category = EXCLUDED.category, updated_at = now()
            """,
            tg_id,
            place_norm,
            category,
        )


# ── Rate cache ───────────────────────────────────────────────────────────────

async def get_cached_rates(
    pool: asyncpg.Pool, base: str, date_str: str
) -> dict | None:
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT rates FROM rate_cache "
            "WHERE base_currency = $1 AND fetched_date = $2",
            base,
            date_str,
        )
    if value is None:
        return None
    return value if isinstance(value, dict) else json.loads(value)


async def save_cached_rates(
    pool: asyncpg.Pool, base: str, date_str: str, rates: dict
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rate_cache (base_currency, fetched_date, rates)
            VALUES ($1, $2, $3)
            ON CONFLICT (base_currency, fetched_date)
            DO UPDATE SET rates = EXCLUDED.rates
            """,
            base,
            date_str,
            json.dumps(rates),
        )
