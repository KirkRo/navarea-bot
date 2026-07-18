"""
Точка входа. Запуск: python -m bot.main
(из корня проекта, после того как настроен .env -- см. README.md)
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from .config import config
from .handlers import admin, areas, billing, qa, start, warnings
from .scheduler import poll_sources_job
from .services.claude_qa import ClaudeQA
from .services.db import Database

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка при обработке апдейта %s", update, exc_info=context.error)


def build_application() -> Application:
    problems = config.validate()
    for p in problems:
        logger.warning("Проблема конфигурации: %s", p)

    application = Application.builder().token(config.bot_token).build()

    db = Database(config.db_path)
    qa_client = ClaudeQA(config.anthropic_api_key, config.claude_model, config.claude_max_tokens)
    application.bot_data["db"] = db
    application.bot_data["qa"] = qa_client

    # --- команды ---
    application.add_handler(CommandHandler("start", start.cmd_start))
    application.add_handler(CommandHandler("help", start.cmd_help))
    application.add_handler(CommandHandler("status", start.cmd_status))
    application.add_handler(CommandHandler("areas", areas.cmd_areas))
    application.add_handler(CommandHandler("sources", areas.cmd_sources))
    application.add_handler(CommandHandler("active", warnings.cmd_active))
    application.add_handler(CommandHandler("explain", warnings.cmd_explain))
    application.add_handler(CommandHandler("subscribe", billing.cmd_subscribe))
    application.add_handler(CommandHandler("cancel_subscription", billing.cmd_cancel_subscription))
    application.add_handler(CommandHandler("stats", admin.cmd_stats))
    application.add_handler(CommandHandler("broadcast", admin.cmd_broadcast))

    # --- callback-кнопки выбора районов ---
    application.add_handler(CallbackQueryHandler(areas.on_area_toggle, pattern=f"^{areas.CALLBACK_PREFIX}"))

    # --- оплата Stars ---
    application.add_handler(PreCheckoutQueryHandler(billing.precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, billing.successful_payment_callback))

    # --- свободный текст = вопрос к Claude (должен идти последним) ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, qa.on_text_message))

    application.add_error_handler(on_error)

    # --- фоновый опрос источников ---
    if application.job_queue is not None:
        application.job_queue.run_repeating(
            poll_sources_job,
            interval=config.poll_interval_minutes * 60,
            first=10,
        )
    else:
        logger.warning(
            "JobQueue недоступен -- поставь пакет с extra 'job-queue': "
            "pip install \"python-telegram-bot[job-queue]\""
        )

    return application


def main() -> None:
    app = build_application()
    logger.info("Бот запускается...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
