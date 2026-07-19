from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..config import config
from ..services.db import Database
from ..services.sources.registry import AREAS, POLLABLE_AREAS

CALLBACK_PREFIX = "area:"


def _build_keyboard(subscribed: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for code in POLLABLE_AREAS:
        mark = "✅" if code in subscribed else "▫️"
        info = AREAS[code]
        rows.append([InlineKeyboardButton(f"{mark} NAVAREA {code} — {info.name}", callback_data=f"{CALLBACK_PREFIX}{code}")])
    rows.append([InlineKeyboardButton("Готово", callback_data=f"{CALLBACK_PREFIX}done")])
    return InlineKeyboardMarkup(rows)


async def cmd_areas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user_id = update.effective_user.id
    subscribed = db.get_user_areas(user_id)
    is_premium = db.is_premium_active(user_id)
    limit = config.premium_areas_limit if is_premium else config.free_areas_limit

    await update.message.reply_text(
        f"Отметь районы, за которыми следить (лимит {limit}). "
        f"🟢 -- живой автоматический опрос, 🟡 -- экспериментальный источник, точность ниже.\n"
        f"Полный список всех 21 района с источниками -- /sources",
        reply_markup=_build_keyboard(subscribed),
    )


async def on_area_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    query = update.callback_query
    user_id = query.from_user.id
    code = query.data[len(CALLBACK_PREFIX):]

    if code == "done":
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        return

    subscribed = db.get_user_areas(user_id)
    is_premium = db.is_premium_active(user_id)
    limit = config.premium_areas_limit if is_premium else config.free_areas_limit

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
        await query.answer("Добавлено")

    subscribed = db.get_user_areas(user_id)
    await query.edit_message_reply_markup(reply_markup=_build_keyboard(subscribed))


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
