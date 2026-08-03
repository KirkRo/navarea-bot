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


async def cmd_diag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка всех источников по запросу: что отвечает, что нет и почему.

    Нужна, чтобы не лазить в логи хостинга: команда обходит каждый источник
    и показывает, сколько сообщений он реально отдал прямо сейчас."""
    if not _is_owner(update.effective_user.id):
        return

    from ..config import BUILD, config
    from ..services.sources.registry import SOURCES

    msg = await update.message.reply_text("Проверяю источники…")
    lines = [f"<b>Сборка</b> {BUILD}",
             f"Sealagom: {'подключён' if config.sealagom_api_token else 'не используется'}",
             f"База: {'Postgres' if config.database_url else 'SQLite'}",
             ""]

    checked: set[int] = set()
    for area_code, source in sorted(SOURCES.items()):
        # один и тот же источник может отвечать за несколько районов --
        # проверяем каждый объект один раз, остальное он отдаёт из кэша
        try:
            raw = await source.fetch_raw(area_code)
            parsed = source.parse(area_code, raw)
            lines.append(f"✅ {area_code} — {len(parsed)} сообщ. ({source.source_id})")
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            reason = f"HTTP {code}" if code else type(e).__name__
            lines.append(f"❌ {area_code} — {reason} ({source.source_id})")
        checked.add(id(source))

    db = context.bot_data["db"]
    stats = db.stats()
    lines.append("")
    lines.append(f"В базе: {stats['active_warnings']} действующих, {stats['total_warnings']} всего")

    text = "\n".join(lines)
    for i in range(0, len(text), 3500):
        if i == 0:
            await msg.edit_text(text[:3500], parse_mode="HTML")
        else:
            await update.message.reply_text(text[i:i + 3500], parse_mode="HTML")
