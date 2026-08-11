"""
Точка входа. Запуск: python -m bot.main
(из корня проекта, после того как настроен .env -- см. README.md)
"""
from __future__ import annotations

import logging

from telegram import MenuButtonCommands, MenuButtonWebApp, Update, WebAppInfo
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
from .scheduler import daily_job, keep_awake_job, poll_sources_job
from .services.claude_qa import ClaudeQA
from .services.db_factory import build_database
from .webapp import start_web_server

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка при обработке апдейта %s", update, exc_info=context.error)


async def on_startup(application: Application) -> None:
    """Всё, что нужно сделать один раз при запуске: кнопка Mini App и
    подтягивание списка береговых регионов (их состав знает только
    Sealagom, заранее в таблицу не пропишешь)."""
    await setup_menu_button(application)
    try:
        from .services.sources.registry import register_coastal_areas

        added = await register_coastal_areas()
        if added:
            logger.info("Береговые предупреждения доступны: %d регионов", added)
    except Exception:
        logger.exception("Не удалось зарегистрировать береговые регионы")


async def setup_menu_button(application: Application) -> None:
    """Ставит постоянную кнопку слева от поля ввода, которая открывает Mini App.
    Вызывается сама при каждом запуске бота -- руками в BotFather настраивать
    ничего не нужно, и адрес всегда актуальный (на Render он подставляется
    автоматически, см. config.public_url).

    Если публичного адреса нет (например Oracle без домена) -- возвращаем
    обычную кнопку со списком команд, чтобы не оставить битую ссылку."""
    try:
        if config.public_url:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть",
                    web_app=WebAppInfo(url=f"{config.public_url}/app"),
                )
            )
            logger.info("Кнопка меню настроена на Mini App: %s/app", config.public_url)
        else:
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            logger.warning(
                "PUBLIC_URL не задан -- Mini App недоступен, кнопка меню показывает список команд"
            )
    except Exception:
        logger.exception("Не удалось настроить кнопку меню")


def build_application() -> Application:
    problems = config.validate()
    for p in problems:
        logger.warning("Проблема конфигурации: %s", p)

    from .config import BUILD
    logger.info("Сборка: %s", BUILD)
    logger.info(
        "Настройки: публичный адрес=%s | Sealagom=%s | база=%s",
        config.public_url or "НЕ ЗАДАН (Mini App работать не будет)",
        "подключён" if config.sealagom_api_token else "не используется",
        "Postgres" if config.database_url else "SQLite",
    )

    builder = Application.builder().token(config.bot_token).post_init(on_startup)
    if config.telegram_test_env:
        # Тестовый дата-центр Telegram: там звёзды бесплатные и покупку можно
        # прогнать целиком. Аккаунт и токен там отдельные -- см. PAYMENTS.md.
        # Форма адреса с {token} -- документированная, именно для этого случая.
        builder = builder.base_url("https://api.telegram.org/bot{token}/test")
        builder = builder.base_file_url("https://api.telegram.org/file/bot{token}/test")
        logger.warning("ТЕСТОВАЯ СРЕДА Telegram: бот работает не с боевыми аккаунтами")
    application = builder.build()

    db = build_database(config.database_url, config.db_path)
    qa_client = ClaudeQA(config.anthropic_api_key, config.claude_model, config.claude_max_tokens)

    # веб-сервер поднимаем после базы -- Mini App обращается к ней через API
    start_web_server(config.port, db=db, bot_token=config.bot_token, qa=qa_client)
    application.bot_data["db"] = db
    application.bot_data["qa"] = qa_client

    # --- команды ---
    application.add_handler(CommandHandler("start", start.cmd_start))
    application.add_handler(CommandHandler("help", start.cmd_help))
    application.add_handler(CommandHandler("app", start.cmd_app))
    application.add_handler(CommandHandler("tools", start.cmd_tools))
    application.add_handler(CommandHandler("radio", start.cmd_radio))
    application.add_handler(CommandHandler("voyage", start.cmd_voyage))
    application.add_handler(CommandHandler("chart", start.cmd_chart))
    application.add_handler(CommandHandler("status", start.cmd_status))
    application.add_handler(CommandHandler("areas", areas.cmd_areas))
    application.add_handler(CommandHandler("sources", areas.cmd_sources))
    application.add_handler(CommandHandler("active", warnings.cmd_active))
    application.add_handler(CommandHandler("explain", warnings.cmd_explain))
    application.add_handler(CommandHandler("subscribe", billing.cmd_subscribe))
    application.add_handler(CommandHandler("cancel_subscription", billing.cmd_cancel_subscription))
    application.add_handler(CommandHandler("resume_subscription", billing.cmd_resume_subscription))
    application.add_handler(CommandHandler("stats", admin.cmd_stats))
    application.add_handler(CommandHandler("diag", admin.cmd_diag))
    application.add_handler(CommandHandler("broadcast", admin.cmd_broadcast))
    application.add_handler(CommandHandler("notice", admin.cmd_notice))
    application.add_handler(CommandHandler("support", admin.cmd_support_list))
    application.add_handler(CommandHandler("reply", admin.cmd_reply))
    application.add_handler(CommandHandler("multi", admin.cmd_multi))
    application.add_handler(CommandHandler("payments", admin.cmd_payments))
    application.add_handler(CommandHandler("refund", admin.cmd_refund))
    application.add_handler(CommandHandler("balance", admin.cmd_balance))
    application.add_handler(CommandHandler("grant", admin.cmd_grant))
    application.add_handler(CommandHandler("revoke", admin.cmd_revoke))

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
        # Самоподдержка от усыпления на бесплатном тарифе
        if config.public_url:
            application.job_queue.run_repeating(keep_awake_job, interval=600, first=120)
            logger.info("Самопинг включён: %s раз в 10 минут", config.public_url)

        application.job_queue.run_repeating(
            poll_sources_job,
            interval=config.poll_interval_minutes * 60,
            first=10,
        )
        # Напоминания о сертификатах -- раз в сутки, первый прогон через минуту
        # после старта, чтобы не задерживать запуск.
        application.job_queue.run_repeating(daily_job, interval=86400, first=60)
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
