"""Expense Tracker Telegram bot — entry point."""
from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder

from bot import clock, db
from bot.config import Config
from bot.handlers import expense, settings, start
from bot.rates import RateService
from bot.sheets import SheetsService

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:
    config: Config = app.bot_data["config"]
    pool = await db.create_pool(config.database_url)
    await db.init_schema(pool)
    app.bot_data["pool"] = pool
    app.bot_data["rates"] = RateService(config.exchange_rate_base_url, pool)
    app.bot_data["sheets"] = SheetsService(config.service_account_file)
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Set up or reconnect your sheet"),
            BotCommand("settings", "View and change your settings"),
            BotCommand("cancel", "Cancel the current action"),
        ]
    )
    logger.info("Bot initialized; service account: %s",
                app.bot_data["sheets"].client_email)


async def _post_shutdown(app: Application) -> None:
    pool = app.bot_data.get("pool")
    if pool:
        await pool.close()


def main() -> None:
    config = Config.load()
    clock.configure(config.timezone)
    application = (
        ApplicationBuilder()
        .token(config.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.bot_data["config"] = config

    application.add_handler(start.build_handler())
    application.add_handler(settings.build_handler())
    application.add_handler(expense.build_handler())

    logger.info("Starting bot (long polling)…")
    application.run_polling()


if __name__ == "__main__":
    main()
