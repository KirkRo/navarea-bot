from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..config import config
from ..scheduler import fetch_and_store_area, format_warning_message
from ..services.access import is_effectively_premium
from ..services.sources.registry import AREAS, POLLABLE_AREAS, area_display_name

logger = logging.getLogger(__name__)

CALLBACK_PREFIX = "area:"
CATCHUP_LIMIT = 15  # чтобы не заспамить при районе с большим числом действующих предупреждений


def _build_keyboard(subscribed: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for code in POLLABLE_AREAS:
        mark = "✅" if code in subscribed else "▫️"
        info = AREAS[code]
        label = f"{mark} {code.replace('COASTAL:', 'Берег ')} — {area_display_name(code)}"
        rows.append([InlineKeyboardButton(label[:62], callback_data=f"{CALLBACK_PREFIX}{code}")])
    rows.append([InlineKeyboardButton("Готово", callback_data=f"{CALLBACK_PREFIX}done")])
    return InlineKeyboardMarkup(rows)


async def cmd_areas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.bot_data["db"]
    user_id = update.effective_user.id
    subscribed = db.get_user_areas(user_id)
    is_premium = is_effectively_premium(db, user_id)
    limit = config.premium_areas_limit if is_premium else config.free_areas_limit

    await update.message.reply_text(
        f"Отметь районы, за которыми следить (лимит {limit}). "
        f"🟢 -- живой автоматический опрос, 🟡 -- экспериментальный источник, точность ниже.\n"
        f"При добавлении района сразу пришлю то, что сейчас действует по нему.\n"
        f"Полный список всех 21 района с источниками -- /sources",
        reply_markup=_build_keyboard(subscribed),
    )


async def on_area_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.bot_data["db"]
    query = update.callback_query
    user_id = query.from_user.id
    code = query.data[len(CALLBACK_PREFIX):]

    if code == "done":
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        return

    subscribed = db.get_user_areas(user_id)
    is_premium = is_effectively_premium(db, user_id)
    limit = config.premium_areas_limit if is_premium else config.free_areas_limit

    just_added = False
    if code in subscribed:
        db.remove_area(user_id, code)
        await query.answer("Убрано")
    else:
        if len(subscribed) >= limit:
            await query.answer(
                f"Лимит {limit} районов на твоём тарифе. Освободи слот или оформи /subscribe.",
                show_alert=True,
            )
            return
        db.add_area(user_id, code)
        just_added = True
        await query.answer("Добавлено, подтягиваю действующие предупреждения…")

    subscribed = db.get_user_areas(user_id)
    await query.edit_message_reply_markup(reply_markup=_build_keyboard(subscribed))

    if just_added:
        await _send_catchup(context, user_id, code)


async def _send_catchup(context: ContextTypes.DEFAULT_TYPE, user_id: int, area_code: str) -> None:
    """Сразу после подписки -- скачать источник и прислать то, что уже действует,
    не дожидаясь планового цикла опроса (который может быть через 30 минут)."""
    db = context.bot_data["db"]

    _new_ids, error = await fetch_and_store_area(db, area_code)  # подтягиваем самое свежее прямо сейчас
    rows = db.active_warnings(area_code, limit=CATCHUP_LIMIT)

    if error and not rows:
        await context.bot.send_message(
            user_id,
            f"Не получилось прямо сейчас достучаться до источника NAVAREA {area_code}. "
            f"Бот попробует ещё раз при следующем плановом опросе.",
        )
        return

    if not rows:
        await context.bot.send_message(
            user_id,
            f"По NAVAREA {area_code} сейчас нет действующих предупреждений в источнике "
            f"(либо источник временно недоступен -- бот попробует ещё раз при следующем опросе).",
        )
        return

    for row in rows:
        text = format_warning_message(area_code, row, is_new=False)
        try:
            await context.bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=True)
            db.mark_notified(user_id, row["id"])
        except Exception:
            logger.exception("Не удалось отправить предупреждение %s пользователю %s", row["id"], user_id)


async def cmd_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status_names = {
        "live": "живой опрос",
        "experimental": "экспериментальный парсер",
        "blocked": "сайт запрещает автодоступ, только ссылка",
        "unknown": "актуальный адрес не подтверждён",
        "none": "координатор не публикует данные онлайн",
    }
    lines = ["Официальные источники по всем районам NAVAREA:\n"]
    for code, info in AREAS.items():
        line = f"NAVAREA {code} ({info.coordinator}) -- {status_names[info.status]}"
        if info.url:
            line += f"\n{info.url}"
        lines.append(line)

    # Telegram режет сообщения по 4096 символов -- бьём на части с запасом
    text = "\n\n".join(lines)
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i + 3500], disable_web_page_preview=True)
