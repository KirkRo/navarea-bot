from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from ..config import config
from ..services.db import Database


def _is_owner(user_id: int) -> bool:
    return user_id in config.owner_ids


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user.id):
        return
    db: Database = context.bot_data["db"]
    s = db.stats()
    text = (
        f"Пользователей: {s['total_users']}\n"
        f"Premium активных: {s['premium_users']}\n"
        f"Предупреждений в базе: {s['total_warnings']} (действующих: {s['active_warnings']})"
    )
    await update.message.reply_text(text)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user.id):
        return
    db: Database = context.bot_data["db"]

    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Использование: /broadcast текст сообщения")
        return

    user_ids = db.get_all_user_ids()

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # не упираемся в лимиты Telegram (~30 msg/sec)

    await update.message.reply_text(f"Разослано: {sent}, не доставлено: {failed}")
