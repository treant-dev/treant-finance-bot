"""Currency conversion via ExchangeRate-API (no key), cached daily in Postgres."""
from __future__ import annotations

import logging

import asyncpg
import httpx

from . import clock, db

logger = logging.getLogger(__name__)


class RateService:
    def __init__(self, base_url: str, pool: asyncpg.Pool):
        self._base_url = base_url
        self._pool = pool

    async def _rates_for(self, base: str) -> dict | None:
        """Return today's {currency: rate-per-1-base} map for `base`, cached daily."""
        today = clock.today()
        cached = await db.get_cached_rates(self._pool, base, today)
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/{base}")
                resp.raise_for_status()
                payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Rate fetch failed for %s: %s", base, exc)
            # Fall back to the most recent cached rates we have, if any.
            return await self._latest_cached(base)

        rates = payload.get("rates")
        if not isinstance(rates, dict):
            logger.warning("Unexpected rate payload for %s: %s", base, payload)
            return await self._latest_cached(base)

        await db.save_cached_rates(self._pool, base, today, rates)
        return rates

    async def _latest_cached(self, base: str) -> dict | None:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval(
                "SELECT rates FROM rate_cache WHERE base_currency = $1 "
                "ORDER BY fetched_date DESC LIMIT 1",
                base,
            )
        if value is None:
            return None
        import json

        return value if isinstance(value, dict) else json.loads(value)

    async def convert(
        self, amount: float, currency: str, base_currency: str
    ) -> float | None:
        """Convert `amount` in `currency` to `base_currency`. None if not possible."""
        currency = currency.upper()
        base_currency = base_currency.upper()
        if currency == base_currency:
            return round(amount, 2)

        rates = await self._rates_for(base_currency)
        if not rates:
            return None
        # rates[currency] = units of `currency` per 1 base_currency.
        rate = rates.get(currency)
        if not rate:
            return None
        return round(amount / rate, 2)
