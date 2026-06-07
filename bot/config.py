"""Configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    # Optional: load a local .env when developing outside Docker.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    pass


@dataclass(frozen=True)
class Config:
    bot_token: str
    service_account_file: str
    database_url: str
    exchange_rate_base_url: str
    template_sheet_url: str

    @staticmethod
    def load() -> "Config":
        def required(key: str) -> str:
            value = os.environ.get(key)
            if not value:
                raise RuntimeError(f"Missing required environment variable: {key}")
            return value

        return Config(
            bot_token=required("BOT_TOKEN"),
            service_account_file=required("GOOGLE_SERVICE_ACCOUNT_FILE"),
            database_url=required("DATABASE_URL"),
            exchange_rate_base_url=os.environ.get(
                "EXCHANGE_RATE_BASE_URL", "https://open.er-api.com/v6/latest"
            ).rstrip("/"),
            template_sheet_url=os.environ.get("TEMPLATE_SHEET_URL", ""),
        )
