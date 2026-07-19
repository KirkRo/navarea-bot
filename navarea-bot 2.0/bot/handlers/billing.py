"""
Платная подписка через Telegram Stars (XTR) -- встроенная валюта Telegram,
не требует своего платёжного провайдера/эквайринга. 150 звёзд (по умолчанию,
меняется в .env как STARS_PRICE_MONTHLY) примерно соответствуют 3$ по
курсу внутренней покупки звёзд в приложении Telegram.

Оформление именно через create_invoice_link(..., subscription_period=2592000)
-- это единственный метод в Bot API, который поддерживает subscription_period
(у send_invoice такого параметра нет). Подписка потом продлевается сама
каждые 30 дней, пока пользователь её не отменит.
"""
from __future__ import annotations

from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import ContextTypes

from ..config import config
from ..services.db import Database

SUBSCRIPTION_PERIOD_SECONDS = 2592000  # 30 дней -- единственное разрешённое значение в Bot API
INVOICE_PAYLOAD = "navarea_premium_monthly"


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id

    if db.is_premium_active(user_id):
        await update.message.reply_text("У тебя уже активна платная подписка ✅. /status покажет детали.")
        return

    link = await context.bot.create_invoice_link(
        title="NAVAREA Bot Premium",
        description=(
            f"Безлимитные районы NAVAREA и вопросы к Claude на месяц. "
            f"Автопродление каждые 30 дней, отменить можно в любой момент через /cancel_subscription."
        ),
        payload=INVOICE_PAYLOAD,
        currency="XTR",
        prices=[LabeledPrice(label="Premium, 1 месяц", amount=config.stars_price_monthly)],
        subscription_period=SUBSCRIPTION_PERIOD_SECONDS,
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"Оплатить {config.stars_price_monthly} ⭐", url=link)]])
    await update.message.reply_text(
        f"Premium даёт:\n"
        f"• до {config.premium_areas_limit} районов NAVAREA одновременно (бесплатно -- {config.free_areas_limit})\n"
        f"• безлимит вопросов к Claude (бесплатно -- {config.free_qa_daily_limit} в день)\n\n"
        f"{config.stars_price_monthly} ⭐ / месяц, оплата прямо в Telegram, без карт и переводов.",
        reply_markup=keyboard,
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload != INVOICE_PAYLOAD:
        await query.answer(ok=False, error_message="Неизвестный товар, попробуй /subscribe заново.")
        return
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    payment = update.message.successful_payment
    user_id = update.effective_user.id

    until = payment.subscription_expiration_date
    if until is None:
        # подстраховка -- на случай не-подписочного платежа
        from datetime import timedelta
        until = datetime.now(timezone.utc) + timedelta(seconds=SUBSCRIPTION_PERIOD_SECONDS)

    db.set_premium(user_id, until.isoformat())
    db.log_payment(
        user_id=user_id,
        charge_id=payment.telegram_payment_charge_id,
        stars_amount=payment.total_amount,
        is_recurring=bool(payment.is_recurring),
    )

    text = (
        "Спасибо, Premium активирован ⭐️\n"
        f"Действует до {until.strftime('%d.%m.%Y')}, дальше продлится автоматически.\n"
        "Отменить автопродление в любой момент -- /cancel_subscription."
    )
    await update.message.reply_text(text)


async def cmd_cancel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user or not user.is_premium:
        await update.message.reply_text("Активной подписки не найдено.")
        return

    charge_id = db.get_last_charge_id(user_id)

    if not charge_id:
        await update.message.reply_text(
            "Не нашёл платёж для отмены автоматически. Отменить можно и вручную: "
            "Настройки Telegram → Мои звёзды → Подписки."
        )
        return

    await context.bot.edit_user_star_subscription(
        user_id=user_id,
        telegram_payment_charge_id=charge_id,
        is_canceled=True,
    )
    await update.message.reply_text(
        "Автопродление отключено. Premium останется активным до конца уже оплаченного периода."
    )
