from __future__ import annotations

import asyncio
import logging

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


async def cmd_notice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Объявление в колокольчик всем пользователям.

    В отличие от /broadcast ничего не рассылает: запись ложится в ленту
    уведомлений и ждёт, пока человек сам откроет приложение. Так уместнее
    для новостей и обновлений -- они не будят людей на вахте."""
    if not _is_owner(update.effective_user.id):
        return
    db: Database = context.bot_data["db"]

    raw = " ".join(context.args)
    if not raw:
        await update.message.reply_text(
            "Использование: /notice Заголовок | текст\n"
            "Заголовок появится в колокольчике у всех пользователей."
        )
        return

    title, _, body = raw.partition("|")
    db.add_notice(title.strip()[:120], body.strip(), kind="news")
    await update.message.reply_text("Объявление добавлено в ленту уведомлений.")


async def cmd_support_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Владельцу -- список обращений, всем остальным -- как написать."""
    db: Database = context.bot_data["db"]

    if not _is_owner(update.effective_user.id):
        await update.message.reply_text(
            "Написать мне можно прямо в приложении: открой WatchKeeper → "
            "«Моё судно» → «Настройки» → «Написать в поддержку». "
            "Переписка идёт здесь же, ответ придёт сообщением от бота."
        )
        return

    threads = db.support_threads(limit=30)
    if not threads:
        await update.message.reply_text("Обращений пока нет.")
        return

    lines = ["<b>Обращения в поддержку</b>", ""]
    for t in threads:
        mark = f"🔴 {t['unread']}" if t["unread"] else "✅"
        lines.append(f"{mark} id <code>{t['user_id']}</code> · сообщений {t['total']} · "
                     f"{str(t['last_at'])[:16].replace('T', ' ')}")
    lines.append("")
    lines.append("Ответить: <code>/reply id текст</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ответ пользователю в чат поддержки: /reply <id> <текст>.

    Ответ ложится в переписку внутри приложения и одновременно уходит
    человеку сообщением в Telegram -- он может не открывать приложение."""
    if not _is_owner(update.effective_user.id):
        return
    db: Database = context.bot_data["db"]

    if len(context.args) < 2 or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text("Использование: /reply id текста ответа")
        return

    uid = int(context.args[0])
    text = " ".join(context.args[1:]).strip()
    db.add_support_message(uid, "owner", text[:2000])
    db.mark_support_seen(uid, "owner")

    try:
        await context.bot.send_message(uid, f"💬 Ответ поддержки WatchKeeper:\n\n{text}")
        await update.message.reply_text("Отправлено и записано в переписку.")
    except Exception:
        await update.message.reply_text(
            "Записано в переписку, но сообщением не доставлено — "
            "возможно, человек не начинал диалог с ботом."
        )


async def cmd_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Последние платежи со звёздами: кто, сколько и номер операции.

    Номер операции нужен для возврата -- без него refundStarPayment
    вызвать нечем."""
    if not _is_owner(update.effective_user.id):
        return
    db: Database = context.bot_data["db"]

    rows = db.recent_payments(limit=20)
    if not rows:
        await update.message.reply_text("Платежей пока нет.")
        return

    lines = ["<b>Последние платежи</b>", ""]
    for p in rows:
        lines.append(
            f"• {p['stars_amount']} ⭐ · id <code>{p['user_id']}</code> · "
            f"{str(p['created_at'])[:16].replace('T', ' ')}"
            f"{' · автопродление' if p.get('is_recurring') else ''}\n"
            f"  <code>{p['charge_id']}</code>"
        )
    lines.append("")
    lines.append("Возврат: <code>/refund id_пользователя номер_операции</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_refund(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возврат звёзд за платёж: /refund <user_id> <charge_id>.

    Штатный способ, которым проверяют оплату на боевом сервере: покупка
    настоящая, а звёзды возвращаются покупателю полностью. Premium при
    этом снимаем сами -- Telegram об отмене доступа не заботится."""
    if not _is_owner(update.effective_user.id):
        return
    db: Database = context.bot_data["db"]

    if len(context.args) < 2 or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text(
            "Использование: /refund id_пользователя номер_операции\n"
            "Список платежей с номерами -- /payments"
        )
        return

    uid = int(context.args[0])
    charge_id = context.args[1].strip()

    try:
        await context.bot.refund_star_payment(user_id=uid, telegram_payment_charge_id=charge_id)
    except Exception as e:
        await update.message.reply_text(f"Telegram отказал в возврате: {e}")
        return

    # Доступ снимаем сами: возврат денег и отзыв подписки -- разные вещи,
    # и Telegram второе за нас не делает.
    try:
        db.revoke_premium(uid)
    except Exception:
        logging.getLogger(__name__).exception("Не удалось снять Premium после возврата")

    await update.message.reply_text("Звёзды возвращены, Premium снят.")
    try:
        await context.bot.send_message(
            uid, "Оплата возвращена, звёзды снова у тебя на балансе. "
                 "Premium отключён."
        )
    except Exception:
        pass


async def cmd_multi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устройства, на которых побывало несколько аккаунтов.

    Не приговор: одно устройство законно делят курсанты, сменщики и экипаж
    на общем судовом компьютере. Команда показывает, где стоит присмотреться,
    а не кого наказать."""
    if not _is_owner(update.effective_user.id):
        return
    db: Database = context.bot_data["db"]

    rows = db.device_accounts(min_accounts=2, limit=30)
    if not rows:
        await update.message.reply_text("Устройств с несколькими аккаунтами нет.")
        return

    lines = ["<b>Одно устройство — несколько аккаунтов</b>", ""]
    for r in rows:
        users = str(r.get("users") or "").replace(",", ", ")
        lines.append(f"• {r['n']} акк. · <code>{str(r['device_id'])[:12]}…</code>\n"
                     f"  {users}\n"
                     f"  с {str(r['first_seen'])[:10]} по {str(r['last_seen'])[:10]}")
    lines.append("")
    lines.append("Пробный период выдаётся только первому аккаунту устройства. "
                 "Остальные сразу на бесплатном тарифе, ничего не блокируется.")
    text = "\n".join(lines)
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i + 3500], parse_mode="HTML")


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
